from __future__ import annotations

import heapq
from collections import deque

from hex_node import HexNode


def cheapest_build_path(
    map_data: dict[str, HexNode],
    player_owned_edges: set[frozenset[str]],
    blocked_edges: set[frozenset[str]],
    from_node: str,
    to_node: str,
    include_ferries: bool = False,  # TODO: ferry support — ferries are non-adjacent teleports
) -> tuple[list[str], int] | None:
    """
    Dijkstra: cheapest track to build from from_node to to_node.

    Edge costs: owned → 0; blocked (opponent-owned) → impassable;
    major city interior → 0; otherwise → cost_of_edge().

    # Future optimization (A* + cost shift): adding +1 to every edge makes
    # h = hex_distance(n, goal) admissible for A*. This changes the objective
    # from pure ECU minimisation to ECU + hop_count, penalising longer routes
    # even when free. On this 2,094-node graph Dijkstra is ~1–3 ms, so A* gives
    # no speedup today. If the graph grows, the +1 shift variant is worth
    # revisiting: it naturally balances cheapest build cost against shortest route
    # (fewer hops = less build time). Implement as cheapest_build_path_balanced()
    # or an alpha weight parameter at that point.
    """
    if from_node not in map_data or to_node not in map_data:
        return None

    heap: list[tuple[int, str]] = [(0, from_node)]
    dist: dict[str, int] = {from_node: 0}
    prev: dict[str, str | None] = {from_node: None}

    while heap:
        cost, node = heapq.heappop(heap)
        if cost > dist.get(node, float("inf")):
            continue
        if node == to_node:
            path: list[str] = []
            cur: str | None = node
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            return list(reversed(path)), cost

        current = map_data[node]
        for neighbor_id in current.neighbors:
            neighbor = map_data.get(neighbor_id)
            if neighbor is None or neighbor.is_sea():
                continue
            edge = frozenset({node, neighbor_id})
            if edge in blocked_edges:
                continue
            if edge in player_owned_edges or current.is_major_city_interior_with(neighbor):
                edge_cost = 0
            else:
                edge_cost = current.build_cost_to(neighbor)
            new_cost = cost + edge_cost
            if new_cost < dist.get(neighbor_id, float("inf")):
                dist[neighbor_id] = new_cost
                prev[neighbor_id] = node
                heapq.heappush(heap, (new_cost, neighbor_id))

    return None


def _movement_traversable(
    map_data: dict[str, HexNode],
    owned_edges: set[frozenset[str]],
    a: str,
    b: str,
) -> bool:
    if frozenset({a, b}) in owned_edges:
        return True
    na, nb = map_data.get(a), map_data.get(b)
    return bool(na and nb and na.is_major_city_interior_with(nb))


def reachable_nodes(
    map_data: dict[str, HexNode],
    owned_edges: set[frozenset[str]],
    start_node: str,
    movement_points: int,
    include_ferries: bool = False,  # TODO: ferry support
) -> set[str]:
    """
    BFS: all nodes reachable from start_node within movement_points hops.
    Only traverses owned edges and major city interiors.
    """
    if start_node not in map_data:
        return set()

    visited: set[str] = {start_node}
    queue: deque[tuple[str, int]] = deque([(start_node, 0)])

    while queue:
        node, hops = queue.popleft()
        if hops >= movement_points:
            continue
        for neighbor_id in map_data[node].neighbors:
            if neighbor_id in visited:
                continue
            neighbor = map_data.get(neighbor_id)
            if neighbor is None or neighbor.is_sea():
                continue
            if _movement_traversable(map_data, owned_edges, node, neighbor_id):
                visited.add(neighbor_id)
                queue.append((neighbor_id, hops + 1))

    return visited


def shortest_move_path(
    map_data: dict[str, HexNode],
    owned_edges: set[frozenset[str]],
    start_node: str,
    target_node: str,
    movement_points: int,
    include_ferries: bool = False,  # TODO: ferry support
) -> list[str] | None:
    """
    BFS with path reconstruction: fewest-hop path from start_node to target_node.
    Only traverses owned edges and major city interiors.
    Returns node list (inclusive) or None if unreachable within movement_points.

    # Future optimization (A*): movement is uniform cost (1/hop) so
    # h = hex_distance(n, goal) is admissible — A* would be correct here.
    # The owned-track subgraph is sparse (10–200 edges in practice) so BFS is
    # fast enough. If a full-graph movement query is needed (e.g. reachability
    # ignoring ownership), switch to A* with hex distance: uniform cost +
    # admissible heuristic + 2,094-node graph is exactly where it pays off.
    """
    if start_node not in map_data or target_node not in map_data:
        return None
    if start_node == target_node:
        return [start_node]

    prev: dict[str, str | None] = {start_node: None}
    queue: deque[tuple[str, int]] = deque([(start_node, 0)])

    while queue:
        node, hops = queue.popleft()
        if hops >= movement_points:
            continue
        for neighbor_id in map_data[node].neighbors:
            if neighbor_id in prev:
                continue
            neighbor = map_data.get(neighbor_id)
            if neighbor is None or neighbor.is_sea():
                continue
            if _movement_traversable(map_data, owned_edges, node, neighbor_id):
                prev[neighbor_id] = node
                if neighbor_id == target_node:
                    path: list[str] = []
                    cur: str | None = neighbor_id
                    while cur is not None:
                        path.append(cur)
                        cur = prev[cur]
                    return list(reversed(path))
                queue.append((neighbor_id, hops + 1))

    return None
