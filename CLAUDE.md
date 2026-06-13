### Issue tracker

Issues live in GitHub Issues (`github.com/NC12345/Eurorails`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — one `CONTEXT.md` + `docs/adr/` at the root. See `docs/agents/domain.md`.

---

## Project overview

A Python toolkit for digitizing and visualizing the **Eurorails** board game map as a hex-grid graph. The pipeline converts a physical map image into a queryable JSON node graph with terrain types, city names, and water obstacle (river/lake) data on each edge.

## Environment setup

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Python 3.14 is used (`.venv` targets `/Library/Frameworks/Python.framework/Versions/3.14`).

## Running the tools

```bash
# Visualize the final master map (interactive — click nodes for details)
python master_map_visualization.py
```

## master_map.json schema

Each key is a node ID with the form `r{row}_c{col}`. Node fields:

| Field | Description |
|---|---|
| `id` | Node ID string (`r21_c36`) |
| `row`, `col` | Grid row/column integers |
| `axial_q`, `axial_r` | Axial hex coordinates (odd rows offset by −0.5 in q) |
| `type` | Terrain: `clear`, `mountain`, `alpine`, `small_city`, `medium_city`, `large_city`, `ferry`, `ferry_small_city`, `space_sea` |
| `city_name` | String or null |
| `neighbors` | Map of neighbor node IDs → `{river, river_name, lake, lake_name}` |
| `ferry_link` | `{"to": node_id, "cost_ecu": int}` or `null`; present only on `ferry` / `ferry_small_city` nodes |

`space_sea` nodes exist in the data but are skipped during rendering and pathfinding.

## Coordinate system

- **Axial hex grid**: `axial_q` = column index (even rows: integer, odd rows: `col − 0.5`), `axial_r` = row index.
- **Screen projection**: `x = axial_q`, `y = −axial_r × (√3 / 2)`.
- **Neighbor directions** (6 hex directions): `(±1, 0)`, `(±0.5, ±1)`.
- Water obstacles (rivers/lakes) live on **edges** between node pairs, stored bidirectionally.
