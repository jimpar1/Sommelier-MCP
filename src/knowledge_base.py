"""OWL ontology + HermiT reasoner for wine variety classification. Requires Java.

Knowledge is retrieved with **SPARQL** (over owlready2's ``default_world``) rather
than the Pythonic API, so the same queries run over both asserted facts and
reasoner-inferred class membership. The reasoner runs once on first query.
"""

import re
from typing import Optional

from owlready2 import default_world, get_ontology, sync_reasoner

from config import ONTOLOGY_PATH

# Prefixes shared by every query. ``:`` is the wine-dss ontology namespace.
_PREFIXES = """
PREFIX : <http://example.org/wine-dss#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
"""

# Local names (e.g. "CabernetSauvignon", "SteakPairing") are interpolated into
# SPARQL as `:Name`. Restrict to this pattern to keep that interpolation safe.
_SAFE_NAME = re.compile(r"[A-Za-z0-9_]+")


class KnowledgeBase:
    """Loads the OWL ontology and runs HermiT on first query (result is cached)."""

    def __init__(self, ontology_path: Optional[str] = None):
        self._path = ontology_path or str(ONTOLOGY_PATH)
        self._onto = None
        self._categories: Optional[list[str]] = None

    def _load(self):
        """Load OWL file and run HermiT reasoner; cached after first call."""
        if self._onto is not None:
            return self._onto

        onto = get_ontology("file://" + self._path).load()
        with onto:
            try:
                sync_reasoner(infer_property_values=True, debug=0)
            except TypeError:
                # older owlready2 doesn't accept the debug kwarg
                sync_reasoner(infer_property_values=True)

        self._onto = onto
        return onto

    def _sparql(self, body: str) -> list[list]:
        """Run a SPARQL query body (prefixes prepended) against the reasoned graph."""
        return list(default_world.sparql(_PREFIXES + body))

    @staticmethod
    def _class_names(rows) -> set[str]:
        """Local names of the named classes in SPARQL `rows` (skips anonymous/blank nodes)."""
        return {
            c.name
            for (c,) in rows
            if getattr(c, "name", None) and _SAFE_NAME.fullmatch(c.name)
        }

    def _variety_exists(self, name: str) -> bool:
        """True if `name` is a safe local name of a variety individual in the ontology."""
        if not _SAFE_NAME.fullmatch(name):
            return False
        return bool(self._sparql(f"SELECT ?n WHERE {{ :{name} :hasVarietyName ?n . }}"))

    def list_categories(self) -> list[str]:
        """All WineVariety subclass names (colour types + pairing classes) plus 'GeneralPairing'.

        Cached after first call — the ontology doesn't change at runtime."""
        self._load()
        if self._categories is None:
            rows = self._sparql("SELECT DISTINCT ?c WHERE { ?c rdfs:subClassOf :WineVariety . }")
            cats = sorted(self._class_names(rows) - {"WineVariety"})
            cats.append("GeneralPairing")
            self._categories = cats
        return self._categories

    def varieties_in_category(self, category: str) -> list[str]:
        """
        Grape variety names the reasoner inferred belong to `category`.

        :param category: ontology class name, e.g. "SteakPairing" or "RedVariety",
                         or "GeneralPairing" for varieties not in any pairing class.
        :returns: variety names sorted alphabetically.
        :raises ValueError: if the class doesn't exist in the ontology.
        """
        self._load()
        if category == "GeneralPairing":
            return self._varieties_without_pairing()
        if category not in self.list_categories():
            raise ValueError(f"Unknown ontology category: {category}")

        # `rdf:type` reads reasoner-inferred membership, and `rdfs:subClassOf*` walks the
        # subclass hierarchy so a variety typed as a more specific class (SteakPairing)
        # still counts under its ancestors (RedVariety).
        rows = self._sparql(
            f"SELECT DISTINCT ?name WHERE {{ "
            f"?v rdf:type ?c . ?c rdfs:subClassOf* :{category} . ?v :hasVarietyName ?name . }}"
        )
        return sorted(n for (n,) in rows)

    def pairing_color(self, category: str) -> Optional[str]:
        """The colour the *finished wine* must be for a pairing class, or None.

        Read from the colour restriction in the class definition so the recommender
        returns correctly-coloured bottles, not just any wine of a matching grape:

        * ``canProduceColor`` (RosePairing) wins when present — rosé pairings use red
          grapes vinified as rosé, so the bottle must be ``Rose`` even though the grape's
          typical colour is Red.
        * otherwise ``hasTypicalColor`` (SteakPairing→Red, SeafoodPairing→White).
        * pairings with no colour restriction (Cheese/Dessert) return None — any colour.

        Returns None for non-class food types (e.g. the synthetic ``GeneralPairing``).
        """
        self._load()
        if (not _SAFE_NAME.fullmatch(category)
                or category == "GeneralPairing"
                or category not in self.list_categories()):
            return None
        for prop in ("canProduceColor", "hasTypicalColor"):
            rows = self._sparql(
                f"SELECT ?col WHERE {{ "
                f":{category} owl:equivalentClass ?c . "
                f"?c owl:intersectionOf ?l . "
                f"?l rdf:rest*/rdf:first ?r . "
                f"?r owl:onProperty :{prop} ; owl:hasValue ?col . }}"
            )
            if rows:
                return rows[0][0].name
        return None

    def classify_variety(self, name: str) -> list[str]:
        """
        All ontology categories the reasoner assigned to a single variety.

        :param name: grape variety individual name, e.g. "Xinomavro".
        :returns: category names sorted alphabetically.
        :raises ValueError: if the variety doesn't exist in the ontology.
        """
        self._load()
        if not self._variety_exists(name):
            raise ValueError(f"Unknown variety: {name}")

        # Walk up the subclass hierarchy from the variety's inferred types so the result
        # includes ancestor classes (e.g. RedVariety above SteakPairing).
        rows = self._sparql(
            f"SELECT DISTINCT ?cls WHERE {{ :{name} rdf:type ?d . ?d rdfs:subClassOf* ?cls . }}"
        )
        skip = {"WineVariety", "NamedIndividual", "Thing"}
        return sorted(self._class_names(rows) - skip)

    def get_specificity_score(self, variety_name: str, target_class: str) -> float:
        """
        How directly a variety belongs to a target class (0.0 - 1.0).

        1.0 = direct rdf:type
        0.6 = via rdfs:subClassOf (any depth)
        0.0 = not a member (shouldn't happen - filtered by varieties_in_category).
        """
        self._load()
        if not _SAFE_NAME.fullmatch(variety_name):
            return 0.0
        if not _SAFE_NAME.fullmatch(target_class):
            return 0.0
        # "GeneralPairing" is a synthetic bucket, not an ontology class, so it has no
        # membership to score (and isn't a valid SPARQL entity).
        if target_class == "GeneralPairing":
            return 0.0

        if self._sparql(
            f"SELECT ?n WHERE {{ "
            f":{variety_name} :hasVarietyName ?n . "
            f":{variety_name} rdf:type :{target_class} . }}"
        ):
            return 1.0

        if self._sparql(
            f"SELECT ?n WHERE {{ "
            f":{variety_name} :hasVarietyName ?n . "
            f":{variety_name} rdf:type ?c . "
            f"?c rdfs:subClassOf+ :{target_class} . "
            f"FILTER(?c != :{target_class}) }}"
        ):
            return 0.6

        return 0.0

    def _pairing_classes(self) -> list[str]:
        """Names of the ontology's pairing classes (WineVariety subclasses named ``*Pairing``).

        Derived from the ontology rather than hardcoded, so adding a pairing class to the
        OWL automatically flows through to GeneralPairing and the tool surface.
        Excludes the synthetic ``GeneralPairing`` (not an ontology class)."""
        return [
            c for c in self.list_categories()
            if c.endswith("Pairing") and c != "GeneralPairing"
        ]

    def _varieties_without_pairing(self) -> list[str]:
        """Varieties not assigned to any pairing class by the reasoner."""
        all_varieties = {
            n for (n,) in self._sparql(
                "SELECT DISTINCT ?name WHERE { ?v :hasVarietyName ?name . }"
            )
        }
        paired: set[str] = set()
        for pc in self._pairing_classes():
            try:
                paired.update(self.varieties_in_category(pc))
            except ValueError:
                pass
        return sorted(all_varieties - paired)

    def get_variety_info(self, name: str) -> dict:
        """
        All ontology properties and inferred classes for a grape variety.

        :returns: dict with keys: name, color, body, sugar, flavor, origin,
                  indigenous_to_greece, is_aromatic, synonyms, sku,
                  can_produce_color, classes.
        """
        self._load()
        if not self._variety_exists(name):
            raise ValueError(f"Unknown variety: {name}")

        # Single-valued (functional) properties only, so the OPTIONAL joins can't
        # multiply rows. Multi-valued properties (synonyms, canProduceColor) are
        # queried separately below to avoid a cartesian product.
        rows = self._sparql(
            f"SELECT ?c ?b ?s ?f ?o ?ind ?aro ?sk WHERE {{ "
            f":{name} :hasVarietyName ?n . "
            f"OPTIONAL {{ :{name} :hasTypicalColor ?c . }} "
            f"OPTIONAL {{ :{name} :hasTypicalBody ?b . }} "
            f"OPTIONAL {{ :{name} :hasTypicalSugar ?s . }} "
            f"OPTIONAL {{ :{name} :hasTypicalFlavor ?f . }} "
            f"OPTIONAL {{ :{name} :originatesFrom ?o . }} "
            f"OPTIONAL {{ :{name} :isIndigenousToGreece ?ind . }} "
            f"OPTIONAL {{ :{name} :isAromatic ?aro . }} "
            f"OPTIONAL {{ :{name} :hasSKU ?sk . }} }}"
        )

        row = rows[0] if rows else (None,) * 8
        c, b, s, f, o, ind, aro, sk = row

        can_rose = sorted(
            r.name for (r,) in
            self._sparql(f"SELECT ?r WHERE {{ :{name} :canProduceColor ?r . }}")
        )
        synonyms = sorted(
            str(syn) for (syn,) in
            self._sparql(f"SELECT ?syn WHERE {{ :{name} :hasSynonym ?syn . }}")
        )

        classes = self.classify_variety(name)

        return {
            "name": name,
            "color": c.name if c else None,
            "body": b.name if b else None,
            "sugar": s.name if s else None,
            "flavor": f.name if f else None,
            "origin": o.name if o else None,
            "indigenous_to_greece": bool(ind) if ind is not None else None,
            "is_aromatic": bool(aro) if aro is not None else None,
            "synonyms": synonyms,
            "sku": str(sk) if sk else None,
            "can_produce_color": can_rose,
            "classes": classes,
        }
