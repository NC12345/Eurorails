# Eurorails — Domain Context

## Purpose

A Python toolkit that digitizes the **Eurorails** board game map into a queryable hex-grid JSON graph. The pipeline converts a physical map photograph into `master_map.json`, a node graph encoding terrain types, city names, and water obstacle data on edges.

## Domain model

### Hex node

Fundamental unit. Each node maps to one hex cell on the physical board. Stored in `master_map.json` under key `r{row}_c{col}`.

Key fields: `type` (terrain), `city_name` (string or null), `neighbors` (map of node IDs → edge obstacle data).

**Terrain types:** `clear`, `mountain`, `alpine`, `small_city`, `medium_city`, `large_city`, `ferry`, `ferry_small_city`, `space_sea`.

`space_sea` nodes exist in the data but are skipped during rendering and pathfinding.

### City node

A hex node whose `type` is `small_city`, `medium_city`, `large_city`, or `ferry_small_city`. Has an associated `city_name` string. The city name editor (`city_adder.py`) assigns these names interactively.

### Ferry node

A hex node that is a ferry terminal but not a city. Type value `ferry`. Has a `ferry_link` field (see below).

### Ferry-city node

A hex node that is both a small city and a ferry terminal. Type value `ferry_small_city`. Has a `city_name` and a `ferry_link` field (see below). Currently two exist: Dublin (`r10_c22`) and Belfast (`r7_c25`). Rendered as a cyan circle with a black center dot to distinguish from plain `small_city` nodes.

### Ferry link

Ferry terminals come in pairs connected by a traversable sea crossing. Each ferry node stores `ferry_link: {"to": node_id, "cost_ecu": int}` pointing to its partner, or `null` if unlinked. The link is stored bidirectionally (both nodes reference each other). Crossing costs ECU and differs per pair. The `ferry_linker.py` editor assigns and saves these links interactively.

### Water obstacle (river / lake edge)

An obstacle that lives on the **edge** between two adjacent nodes, stored bidirectionally in each node's `neighbors` map as `{river, river_name, lake, lake_name}`. Crossing a water obstacle during gameplay has a movement cost.

### Axial coordinates

Each node has `axial_q` (column) and `axial_r` (row) in an axial hex coordinate system. Odd rows are offset by −0.5 in q. Screen projection: `x = axial_q`, `y = −axial_r × (√3 / 2)`.

## Resource data

Game route cards reference resources that cities produce. Two JSON files encode this mapping:

- **`resources_to_cities.json`** — Each resource entry has `name`, `amount` (loading cost in ECU), and `cities` (list of producing cities). 29 resources total; amounts are 3 ECU (most) or 4 ECU (Beer, Cheese, Machinery, Oil, Wine).
- **`cities_to_resources.json`** — inverse index. Maps each city name → list of resources it produces. Includes cities with no resources (empty list: Berlin, Madrid, Milano, Paris, Roma, Venezia). Derived from `resources_to_cities.json`; must stay in sync with it.

### Route card

A game card holding exactly 3 routes. All route cards are stored in `route_cards.json` as an array of arrays. Use `route_card_adder.py` (reads stdin) to append cards.

### Route

One entry on a route card: `{city_name, resource_name, amount}`. `amount` is an integer in millions of ECU — the payout earned for delivering that resource to that city. Distinct from the resource loading cost stored in `resources_to_cities.json`.

When updating resource/city data, edit `resources_to_cities.json` first, then update `cities_to_resources.json` to match.

## Tool taxonomy

### Interactive editors (project root)

Read `master_map.json`, allow edits, write back.

- `city_adder.py` — assign city names to city nodes; keyboard-driven text entry
- `master_map_visualization.py` — read-only map viewer with click tooltips

## UI conventions

**Editing state display:** Shown as an axes-space overlay text element (`ax.text` with `transform=ax.transAxes`), anchored to the top-left corner of the map viewport. Must not affect figure layout or map axes geometry. Never use `fig.text()` for dynamic status — it lives in the figure margin and triggers `tight_layout` recalculations on redraw.

**Node selection:** Click within `DISTANCE_THRESHOLD = 0.4` map units of a node center. Selected city nodes enter edit mode; all other nodes show a tooltip annotation.

**Save / exit:** `q` saves pending changes and closes. `Esc` closes without saving (or cancels the current edit if in edit mode).
