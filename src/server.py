"""FastMCP server — exposes the Wine DSS as tools (streamable-http, 0.0.0.0:8000)."""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from config import MCP_HOST, MCP_PORT
from recommender import Recommender

mcp = FastMCP("wine-dss", host=MCP_HOST, port=MCP_PORT)
_recommender = Recommender()


@mcp.tool()
def list_dishes() -> list[dict]:
    """Quick list of all menu dishes (name, section, food_type). Use search_dishes for filtering and descriptions."""
    return _recommender.cat.list_dishes()


@mcp.tool()
def search_dishes(
    name: Optional[str] = None,
    section: Optional[str] = None,
    food_type: Optional[str] = None,
) -> list[dict]:
    """Search dishes with optional filters. Returns name, section, food_type, description."""
    return _recommender.cat.search_dishes(
        name=name, section=section, food_type=food_type,
    )


@mcp.tool()
def list_categories() -> list[str]:
    """List the ontology wine categories (colour types + pairing classes)."""
    return _recommender.kb.list_categories()


@mcp.tool()
def varieties_in_category(category: str) -> list[str]:
    """Grape varieties the reasoner places in an ontology class (e.g. SteakPairing, RedVariety)."""
    return _recommender.kb.varieties_in_category(category)


@mcp.tool()
def recommend_wine_for_dish(
    dish: str,
    max_price: Optional[float] = None,
    color: Optional[str] = None,
    style: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    Recommend in-stock wines for a dish on the menu.

    Looks up the dish's pairing class and returns scored, ranked wines (top K=10 by default).
    By default wines of any style are considered; pass style to restrict (e.g. "Still").
    """
    return _recommender.recommend(
        dish=dish,
        max_price=max_price,
        color=color,
        style=style,
        limit=limit,
    )


@mcp.tool()
def recommend_wine_for_food_type(
    food_type: str,
    max_price: Optional[float] = None,
    color: Optional[str] = None,
    style: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    Recommend wines for a pairing class directly.

    Accepts any pairing class from list_categories (e.g. SteakPairing, SeafoodPairing,
    CheesePairing, DessertPairing, SpicyFoodPairing, RosePairing, PoultryPairing), plus
    GeneralPairing for varieties in no pairing class.
    By default wines of any style are considered; pass style to restrict (e.g. "Still").
    """
    return _recommender.recommend(
        food_type=food_type,
        max_price=max_price,
        color=color,
        style=style,
        limit=limit,
    )


@mcp.tool()
def classify_variety(variety: str) -> list[str]:
    """
    All ontology categories a grape variety belongs to (inferred by the reasoner).

    E.g. classify_variety("Xinomavro") -> ["CheesePairing", "RedVariety", "SteakPairing", ...]
    """
    return _recommender.kb.classify_variety(variety)


@mcp.tool()
def variety_info(variety: str) -> dict:
    """
    Full ontology profile for a grape variety.

    Returns: name, color, body, sugar, flavor, origin, indigenous_to_greece,
    is_aromatic, synonyms, sku, can_produce_color, classes.
    """
    return _recommender.kb.get_variety_info(variety)


@mcp.tool()
def search_catalogue(
    variety: Optional[str] = None,
    varieties: Optional[list[str]] = None,
    color: Optional[str] = None,
    style: Optional[str] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = True,
    limit: Optional[int] = None,
) -> list[dict]:
    """Free-form catalogue search without pairing logic. Returns all matches by default; set limit to cap results.
    Use 'variety' for a single variety or 'varieties' for a list."""
    return _recommender.cat.search_wines(
        variety=variety,
        varieties=varieties,
        color=color,
        style=style,
        max_price=max_price,
        in_stock_only=in_stock_only,
        limit=limit,
    )


def main() -> None:
    """Start the MCP server (run with `python -m server`, PYTHONPATH=src)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
