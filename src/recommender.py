"""Wine recommendation pipeline: dish/food_type → pairing class → varieties → catalogue."""

from typing import Any, Optional

from knowledge_base import KnowledgeBase
from catalogue import Catalogue


class Recommender:
    """Runs the full recommendation pipeline (dish or pairing class → wines)."""

    def __init__(
        self,
        kb: Optional[KnowledgeBase] = None,
        catalogue: Optional[Catalogue] = None,
    ):
        self.kb = kb or KnowledgeBase()
        self.cat = catalogue or Catalogue()

    @staticmethod
    def _score_wines(wines: list[dict], food_type: str, kb: KnowledgeBase, k: int = 10) -> list[dict]:
        """Score wines by specificity + diversity + price, return top K.

        Scoring formula (per wine):
            score = specificity × 100 − diversity_penalty + price_factor

        specificity  : how directly the variety belongs to the pairing class (0.0-1.0).
        diversity    : repeated varieties incur a −15 penalty per extra occurrence.
        price_factor : cheaper wines get a small boost relative to the most expensive match.
        """
        if not wines:
            return wines

        max_price = max((w["price_bottle"] or 0) for w in wines) or 1
        seen: dict[str, int] = {}

        for w in wines:
            variety = w["variety"]
            sp = kb.get_specificity_score(variety, food_type)
            seen[variety] = seen.get(variety, 0) + 1
            div_penalty = (seen[variety] - 1) * 15
            price_factor = (1 - (w["price_bottle"] or 0) / max_price) * 10

            w["_score"] = sp * 100 - div_penalty + price_factor
            w["_specificity"] = sp

        wines.sort(key=lambda w: w["_score"], reverse=True)
        return wines[:k]

    def recommend(
        self,
        food_type: Optional[str] = None,
        dish: Optional[str] = None,
        **filters,
    ) -> dict[str, Any]:
        """
        Return matched wines for a dish or pairing class.

        :param dish: partial dish name (looked up in the menu).
        :param food_type: OWL pairing class name, e.g. "SteakPairing".
        :param filters: forwarded to Catalogue.search_wines (max_price, color, style, limit).
        :returns: dict — keys: dish?, food_type, varieties, wines, note?.
        :raises ValueError: if neither argument is given or the dish is not found.
        """
        if dish is None and food_type is None:
            raise ValueError("Provide either 'dish' or 'food_type'.")

        limit = filters.pop("limit", 10)
        result: dict[str, Any] = {}

        if dish:
            dish_info = self.cat.lookup_dish(dish)
            if dish_info is None:
                raise ValueError(f"Dish '{dish}' not found.")
            food_type = dish_info["food_type"]
            result["dish"] = dish_info

        result["food_type"] = food_type

        if food_type is None:
            result["varieties"] = []
            result["wines"] = []
            result["note"] = "No wine pairing defined for this food type."
            return result

        varieties = self.kb.varieties_in_category(food_type)
        available = set(self.cat.get_available_varieties())
        varieties = [v for v in varieties if v in available]
        result["varieties"] = varieties

        # A pairing may require the finished wine to be a specific colour even though its
        # grapes are typically another colour (RosePairing: red grapes vinified as rosé).
        # Apply that as a default colour the caller can still override.
        if filters.get("color") is None:
            implied_color = self.kb.pairing_color(food_type)
            if implied_color:
                filters["color"] = implied_color

        all_wines = self.cat.search_wines(varieties=varieties, limit=None, **filters)
        result["wines"] = self._score_wines(all_wines, food_type, self.kb, k=limit)

        return result
