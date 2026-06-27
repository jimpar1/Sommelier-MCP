"""SQLite catalogue: wines and dishes for a single shop."""

import sqlite3
import unicodedata
from typing import Optional

from config import DB_PATH


def _fold(s: str) -> str:
    """Casefold and strip accents for accent-insensitive matching."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.casefold())
        if not unicodedata.combining(c)
    )

_WINE_COLS = [
    "label", "variety", "winery", "country", "region",
    "color", "style", "price_takeaway", "price_bottle",
    "price_glass", "stock",
]


class Catalogue:
    """Thin wrapper around the shop's SQLite database."""

    def __init__(self, db_path: str | None = None):
        self._db = str(db_path or DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        return conn

    def search_wines(
        self,
        varieties: Optional[list[str]] = None,
        variety: Optional[str] = None,
        color: Optional[str] = None,
        style: Optional[str] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = True,
        limit: Optional[int] = 10,
    ) -> list[dict]:
        """
        Search wines with optional filters.

        :param varieties: OR list of variety names (takes priority over `variety`).
        :param variety: single variety name shorthand.
        :param color: "Red" | "White" | "Rose".
        :param style: "Still" | "Sparkling" | "Dessert" | "Fortified". None = any style
                      (important for pairings like DessertPairing whose wines are not Still).
        :param max_price: inclusive bottle price ceiling (EUR).
        :param in_stock_only: filter to stock > 0.
        :param limit: max rows returned.
        :returns: list of dicts — keys: label, variety, winery, country, region,
                  color, style, price_takeaway, price_bottle, price_glass, stock.
        """
        if varieties:
            variety_list = list(varieties)
        elif variety:
            variety_list = [variety]
        else:
            variety_list = None

        conditions: list[str] = []
        params: list = []

        if variety_list:
            placeholders = ",".join("?" * len(variety_list))
            conditions.append(f"variety IN ({placeholders})")
            params += variety_list

        if in_stock_only:
            conditions.append("stock > 0")

        if max_price is not None:
            conditions.append("price_bottle IS NOT NULL AND price_bottle <= ?")
            params.append(max_price)

        if color:
            conditions.append("color = ?")
            params.append(color)

        if style:
            conditions.append("style = ?")
            params.append(style)

        columns = ", ".join(_WINE_COLS)
        query = f"SELECT {columns} FROM wines"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if limit is not None:
            query += " ORDER BY price_bottle ASC LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def lookup_dish(self, name: str) -> dict | None:
        """Partial case-insensitive dish lookup with accent folding."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, section, food_type, description FROM dishes"
            ).fetchall()
        folded = _fold(name)
        for row in rows:
            if folded in _fold(row["name"]):
                return dict(row)
        return None

    def list_dishes(self) -> list[dict]:
        """All menu dishes ordered by section, name. Keys: name, section, food_type."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, section, food_type FROM dishes ORDER BY section, name"
            ).fetchall()
        return [dict(row) for row in rows]

    def search_dishes(
        self,
        name: Optional[str] = None,
        section: Optional[str] = None,
        food_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Search dishes with optional filters.

        :param name: case-insensitive partial match with accent folding.
        :param section: exact section match.
        :param food_type: exact food_type match.
        :returns: list of dicts — keys: name, section, food_type, description.
        """
        conditions: list[str] = []
        params: list = []

        if section:
            conditions.append("section = ?")
            params.append(section)
        if food_type:
            conditions.append("food_type = ?")
            params.append(food_type)

        query = (
            "SELECT name, section, food_type, description FROM dishes"
            + (" WHERE " + " AND ".join(conditions) if conditions else "")
            + " ORDER BY section, name"
        )

        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]

        if name:
            folded = _fold(name)
            rows = [r for r in rows if folded in _fold(r["name"])]

        return rows

    def get_available_varieties(self) -> list[str]:
        """Variety names that have at least one wine in stock."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT variety FROM wines "
                "WHERE stock > 0 AND variety IS NOT NULL ORDER BY variety"
            ).fetchall()
        return [row[0] for row in rows]
