# Wine DSS

Wine pairing decision support system exposed as an MCP server.  
Uses an OWL ontology + HermiT reasoner to match dishes to grape varieties, then queries a shop catalogue (SQLite).

## Requirements

- **Docker** + **Docker Compose**

Nothing else is needed on the host. Python 3.12, the Java runtime (for the HermiT
reasoner), all dependencies, the OWL ontology and the SQLite database are bundled
inside the image.

## Run

```bash
docker compose up --build
# server listening on http://localhost:8000/mcp
```

Stop with `Ctrl+C`, or `docker compose down`.

The container runs `python -m server` and serves the MCP endpoint over
**streamable-http** on port 8000.

### Configuration

Set via the `environment:` block in `docker-compose.yml`:

| Variable | Default (in image) | Purpose |
|---|---|---|
| `MCP_HOST` | `0.0.0.0` | bind address |
| `MCP_PORT` | `8000` | port (also update the `ports:` mapping if you change it) |
| `WINE_DSS_DATA_DIR` | `/app/data` | ontology + database location inside the container |

## SPARQL queries

Knowledge retrieval is done with **SPARQL**, not the owlready2 Python API. After the
HermiT reasoner runs, [knowledge_base.py](src/knowledge_base.py) queries
`default_world` with SPARQL — so every recommendation (`varieties_in_category`,
`classify_variety`, `list_categories`) runs over both asserted facts and
reasoner-inferred class membership (via `rdfs:subClassOf*` and `owl:equivalentClass`).

## Connect a client

The server speaks **streamable-http** at `http://localhost:8000/mcp`. A client only
needs that URL; the AI agent talks to the running server over HTTP and **does not need
this source code**. So you don't have to clone the repo to use the tools; just run the
container (or point at wherever it's hosted) and register the URL with your client.

> The config files committed in this repo (`.opencode/opencode.json`, `.mcp.json`,
> `.claude/settings.json`) are **examples** scoped to this project. For day-to-day use,
> prefer adding the server to your client's **global** config so it's available in every
> project without copying files around.

Register the server (name `wine-dss`, URL `http://localhost:8000/mcp`) in your client's
global config (see each tool's MCP docs):

- **OpenCode**: https://opencode.ai/docs/mcp-servers/
- **Claude Code**: https://docs.claude.com/en/docs/claude-code/mcp

## Available Tools

| Tool | Description |
|---|---|
| `list_dishes` | All menu dishes (name, section, food_type) |
| `search_dishes` | Search dishes by name, section, or food_type |
| `list_categories` | Ontology classes (colour types + pairing classes) |
| `varieties_in_category` | Varieties the reasoner placed in a class |
| `recommend_wine_for_dish` | Wines for a named dish |
| `recommend_wine_for_food_type` | Wines for a pairing class (e.g. `SteakPairing`) |
| `classify_variety` | All classes a grape variety belongs to |
| `variety_info` | Full ontology profile for a grape variety |
| `search_catalogue` | Free-form catalogue search |
