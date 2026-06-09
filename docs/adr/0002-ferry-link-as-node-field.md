# ferry_link stored as node field rather than neighbor edge

Ferry pairs are non-adjacent nodes connected by a sea crossing. We store the link as `ferry_link: {"to": node_id, "cost_ecu": int}` directly on each ferry node rather than injecting a non-adjacent entry into the `neighbors` map.

## Considered Options

- **`ferry_link` node field (chosen)** — ferry nodes already dispatch on `type`; a dedicated field is consistent with that pattern. The `neighbors` map preserves its geometric invariant (only hex-adjacent nodes). Pathfinding special-cases ferry nodes anyway (different cost model — ECU fee, future movement debuff), so checking `ferry_link` alongside `neighbors` is natural rather than extra complexity.
- **Non-adjacent entry in `neighbors`** — rejected because it breaks the invariant that every neighbor entry corresponds to a hex-adjacent node. Every tool that walks `neighbors` (visualizer, grid builder, pathfinding) would need to handle an unexpected long-range pointer.
