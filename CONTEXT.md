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

- **`resources_to_cities.json`** — Each resource entry has `name`, `amount` (global supply count — how many instances of this resource exist across the entire game), and `cities` (list of producing cities). 29 resources total; amounts are 3 (most) or 4 (Beer, Cheese, Machinery, Oil, Wine).
- **`cities_to_resources.json`** — inverse index. Maps each city name → list of resources it produces. Includes cities with no resources (empty list: Berlin, Madrid, Milano, Paris, Roma, Venezia). Derived from `resources_to_cities.json`; must stay in sync with it.

### Route card

A game card holding exactly 3 routes. All route cards are stored in `route_cards.json` as an array of arrays. Use `route_card_adder.py` (reads stdin) to append cards.

### Route

One entry on a route card: `{city_name, resource_name, amount}`. `amount` is an integer in millions of ECU — the payout earned for delivering that resource to that city. Distinct from the global supply count stored in `resources_to_cities.json`.

When updating resource/city data, edit `resources_to_cities.json` first, then update `cities_to_resources.json` to match.

## Pathfinding

Graph traversal algorithms in `pathfinding.py`. No external libraries — raw `dict[str, HexNode]` + stdlib `heapq`/`collections.deque`.

### build path

A planned sequence of nodes from a player's existing network to a target, minimising remaining ECU build cost. Owned edges cost 0; opponent-owned edges are impassable; unowned edges cost terrain + water surcharge (`build_cost_to()`). Computed by `cheapest_build_path()` (Dijkstra).

### pathfinding queries

Three public functions:

- `cheapest_build_path(map_data, player_owned_edges, blocked_edges, from_node, to_node)` — Dijkstra on build costs. Returns `(path, total_cost)` or `None`.
- `reachable_nodes(map_data, owned_edges, start_node, movement_points)` — BFS returning all node IDs reachable within the movement budget on owned track + major city interiors.
- `shortest_move_path(map_data, owned_edges, start_node, target_node, movement_points)` — BFS with path reconstruction. Returns ordered node list (inclusive) or `None`.

All three accept `include_ferries: bool = False` (ferry support not yet implemented).

## Rules engine

The rules engine is implemented across three modules: `game_state.py`, `movement.py`, and `track_builder.py`.

### GamePhase

Enum controlling which actions are legal. Values: `INITIAL_BUILD_1` (snake round 1, clockwise, build only), `INITIAL_BUILD_2` (snake round 2, counter-clockwise, build only), `NORMAL_PLAY`.

### LocoType

Enum for train types: `FREIGHT` (speed 9, capacity 2), `FAST_FREIGHT` (speed 12, capacity 2), `HEAVY_FREIGHT` (speed 9, capacity 3), `SUPERFREIGHT` (speed 12, capacity 3).

### TrainState

Runtime per-train fields: `current_node` (node ID), `previous_node` (node ID or None — used for reversing rule), `remaining_movement` (int, decrements each `MoveTo`), `cargo` (list of resource name strings, bounded by loco capacity), `loco_type` (LocoType), `committed_to_ferry` (bool — if True at end of operate phase, next turn teleports train to ferry destination and halves movement allowance for that turn).

### PlayerState

Runtime per-player fields: `player_id`, `ecu` (M ECU balance), `train` (TrainState), `owned_edges` (set of `frozenset({node_a, node_b})` — see owned edge), demand `hand` (list of 3 RouteCards during NORMAL_PLAY), `track_fees_owed` (dict of player_id → M ECU accumulated this turn, settled at end of `execute_operate`).

### owned edge

A `frozenset({node_a, node_b})` stored in `PlayerState.owned_edges`. Direction-independent. Represents one built track section between two adjacent nodes.

### operate phase

First half of a normal turn. Player submits a sequence of actions: `MoveTo`, `PickUp`, `DropOff`, `Deliver`, `CommitFerry`. Processed by `execute_operate()` in `movement.py`. Track usage fees accumulate and are settled at the end of this call.

### build phase

Second half of a normal turn. Player submits either `BuildEdge` actions (to lay track) **or** a single `UpgradeTrain` action — not both. During `INITIAL_BUILD_1` and `INITIAL_BUILD_2`, only `BuildEdge` actions are legal. Processed by `execute_build()` in `track_builder.py`. Track built this turn is NOT available for movement in the same turn.

### major city interior

Edges between two `large_city` nodes sharing the same `city_name`. Train traversal is free (no track ownership required, no movement cost beyond the 1-milepost count). No track may be built on these edges. All players share this universal access.

### reversing rule

A train may not execute `MoveTo(previous_node)` when `current_node` is not a city type. Represents the constraint that trains cannot reverse on open track; they may only reverse direction while at a city.

### committed_to_ferry

Boolean flag on `TrainState`. When `CommitFerry` is executed: flag set to True, movement stopped for that turn. No ECU fee at crossing time — the `ferry_link.cost_ecu` is paid once at build time when building track to the ferry terminal. At the start of the next operate phase, the train teleports to `ferry_link.to` and `remaining_movement` is set to `floor(max_speed / 2)`.

### track usage fee

4M ECU paid per turn to an opponent for using their track, regardless of how many of their edges were traversed in that turn. Accumulated in `track_fees_owed` during `execute_operate`, settled at the end of the call.

### milepost touch

A `BuildEdge` where one endpoint is a `large_city` (outer-border edge into or out of a major city cluster). Maximum 2 such edges per build phase per player.

### blocking rule

A `BuildEdge` is rejected if it would prevent another player from establishing any path to a guaranteed-access node (major city, second slot of a medium/small city, English Channel ferry terminal). Tier-1 local saturation check is implemented. Full BFS reachability check is stubbed (`# TODO: implement full blocking check`).

## Tool taxonomy

### Interactive editors (project root)

Read `master_map.json`, allow edits, write back.

- `city_adder.py` — assign city names to city nodes; keyboard-driven text entry
- `master_map_visualization.py` — read-only map viewer with click tooltips

## UI conventions

**Editing state display:** Shown as an axes-space overlay text element (`ax.text` with `transform=ax.transAxes`), anchored to the top-left corner of the map viewport. Must not affect figure layout or map axes geometry. Never use `fig.text()` for dynamic status — it lives in the figure margin and triggers `tight_layout` recalculations on redraw.

**Node selection:** Click within `DISTANCE_THRESHOLD = 0.4` map units of a node center. Selected city nodes enter edit mode; all other nodes show a tooltip annotation.

**Save / exit:** `q` saves pending changes and closes. `Esc` closes without saving (or cancels the current edit if in edit mode).
