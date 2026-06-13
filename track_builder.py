from __future__ import annotations

from game_state import (
    TERRAIN_BUILD_COST,
    WATER_SURCHARGE,
    UPGRADE_COST,
    VALID_UPGRADE_PATHS,
    BuildEdge,
    BuildResult,
    GamePhase,
    GameState,
    HexNode,
    PlayerState,
    UpgradeTrain,
    BuildAction,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute_build(
    game_state: GameState,
    player_id: str,
    builds: list[BuildAction],
) -> BuildResult:
    """
    Execute the build phase for a player.

    Staging pass: all builds are validated before any are applied.
    Returns error on first violation. Applies atomically on full success.
    """
    player = next((p for p in game_state.players if p.player_id == player_id), None)
    if player is None:
        return BuildResult(ok=False, error=f"unknown player: {player_id}", total_cost=0, edges_built=[])

    has_edge    = any(isinstance(a, BuildEdge)    for a in builds)
    has_upgrade = any(isinstance(a, UpgradeTrain) for a in builds)

    if game_state.phase in (GamePhase.INITIAL_BUILD_1, GamePhase.INITIAL_BUILD_2):
        if has_upgrade:
            return BuildResult(ok=False, error="cannot upgrade train during initial build phase", total_cost=0, edges_built=[])
    else:
        if has_edge and has_upgrade:
            return BuildResult(ok=False, error="cannot build track and upgrade train in the same turn", total_cost=0, edges_built=[])

    staged_edges: set[frozenset[str]] = set()
    major_city_touches = dict(player.major_city_touches_this_turn)
    total_cost = 0
    pending_upgrade: UpgradeTrain | None = None

    for action in builds:
        if isinstance(action, BuildEdge):
            error, edge_cost, major_city_touches = validate_build_edge(
                game_state.map_data,
                player,
                game_state.players,
                action,
                staged_edges,
                major_city_touches,
            )
            if error:
                return BuildResult(ok=False, error=error, total_cost=0, edges_built=[])
            if total_cost + edge_cost > 20:
                return BuildResult(ok=False, error="build budget exceeded (max 20M ECU per turn)", total_cost=0, edges_built=[])
            total_cost += edge_cost
            staged_edges.add(frozenset({action.from_node, action.to_node}))

        elif isinstance(action, UpgradeTrain):
            if pending_upgrade is not None:
                return BuildResult(ok=False, error="cannot upgrade train twice in one turn", total_cost=0, edges_built=[])
            error, upgrade_cost = _validate_upgrade_train(player, action, 20 - total_cost)
            if error:
                return BuildResult(ok=False, error=error, total_cost=0, edges_built=[])
            total_cost += upgrade_cost
            pending_upgrade = action

        else:
            return BuildResult(ok=False, error=f"unknown build action: {type(action).__name__}", total_cost=0, edges_built=[])

    # Verify player has enough ECU
    if player.ecu < total_cost:
        return BuildResult(ok=False, error=f"insufficient funds: need {total_cost}M ECU, have {player.ecu}M ECU", total_cost=0, edges_built=[])

    # Apply atomically
    player.owned_edges |= staged_edges
    player.ecu -= total_cost
    player.major_city_touches_this_turn = major_city_touches
    if pending_upgrade:
        player.train.loco_type = pending_upgrade.loco_type

    return BuildResult(ok=True, error=None, total_cost=total_cost, edges_built=list(staged_edges))


# ---------------------------------------------------------------------------
# Build edge validators
# ---------------------------------------------------------------------------

def check_node_valid(map_data: dict[str, HexNode], node: str) -> str | None:
    if node not in map_data:
        return f"unknown node: {node}"
    if map_data[node].is_sea():
        return f"{node} is a sea node"
    return None


def check_adjacency(map_data: dict[str, HexNode], a: str, b: str) -> str | None:
    if not map_data[a].has_neighbor(b):
        return f"{b} is not adjacent to {a}"
    return None


def check_right_of_way(
    map_data: dict[str, HexNode],
    all_players: list[PlayerState],
    edge: frozenset[str],
    staged_edges: set[frozenset[str]],
) -> str | None:
    node_a, node_b = tuple(edge)
    if map_data[node_a].is_major_city_interior_with(map_data[node_b]):
        return "cannot build inside major city (red area)"
    if edge in staged_edges:
        return "edge already built this turn"
    for p in all_players:
        if edge in p.owned_edges:
            return f"right-of-way conflict: {p.player_id} already owns this edge"
    return None


def check_major_city_touch_limit(
    map_data: dict[str, HexNode],
    from_node: str,
    to_node: str,
    touches: dict[str, int],
) -> tuple[str | None, dict[str, int]]:
    major_node = from_node if map_data[from_node].is_major_city() else to_node
    is_border = map_data[major_node].is_major_city() and not (
        map_data[from_node].is_major_city() and map_data[to_node].is_major_city()
    )
    if not is_border:
        return None, touches
    city = map_data[major_node].city_name
    count = touches.get(city, 0)
    if count >= 2:
        return f"exceeded 2 major-city touches for {city} this turn", touches
    return None, {**touches, city: count + 1}


def validate_build_edge(
    map_data: dict[str, HexNode],
    player: PlayerState,
    all_players: list[PlayerState],
    action: BuildEdge,
    staged_edges: set[frozenset[str]],
    major_city_touches: dict[str, int],
) -> tuple[str | None, int, dict[str, int]]:
    """Returns (error_or_None, edge_cost, updated_major_city_touches)."""
    from_node, to_node = action.from_node, action.to_node
    edge = frozenset({from_node, to_node})

    if err := check_node_valid(map_data, from_node):
        return err, 0, major_city_touches
    if err := check_node_valid(map_data, to_node):
        return err, 0, major_city_touches
    if err := check_adjacency(map_data, from_node, to_node):
        return err, 0, major_city_touches
    if err := check_right_of_way(map_data, all_players, edge, staged_edges):
        return err, 0, major_city_touches

    # Connectivity: from_node must be a major city or in existing network (ferry pair included)
    all_owned = player.owned_edges | staged_edges
    reachable_nodes = _ferry_expanded_reachable(map_data, all_owned)
    if not map_data[from_node].is_major_city() and from_node not in reachable_nodes:
        return f"{from_node} must be a major city or connected to your existing track", 0, major_city_touches

    err, major_city_touches = check_major_city_touch_limit(map_data, from_node, to_node, major_city_touches)
    if err:
        return err, 0, major_city_touches

    # Ferry port capacity
    if map_data[to_node].is_ferry():
        if _count_ferry_players(to_node, player.player_id, all_players, staged_edges) >= 2:
            return "ferry line at player capacity (max 2)", 0, major_city_touches

    if err := check_city_access(map_data, player, all_players, to_node, staged_edges):
        return err, 0, major_city_touches
    if err := check_blocking(map_data, all_players, staged_edges, from_node, to_node, player.player_id):
        return err, 0, major_city_touches

    edge_cost = map_data[from_node].build_cost_to(map_data[to_node])
    if map_data[to_node].is_ferry() and map_data[to_node].ferry_link:
        partner = map_data[to_node].ferry_link.to
        if any(to_node in e or partner in e for e in all_owned):
            edge_cost = 0
    return None, edge_cost, major_city_touches


# ---------------------------------------------------------------------------
# Upgrade validator
# ---------------------------------------------------------------------------

def _validate_upgrade_train(
    player: PlayerState,
    action: UpgradeTrain,
    budget_remaining: int,
) -> tuple[str | None, int]:
    current = player.train.loco_type
    valid_targets = VALID_UPGRADE_PATHS.get(current, set())
    if action.loco_type not in valid_targets:
        return f"invalid upgrade path: {current.name} → {action.loco_type.name}", 0
    cost = UPGRADE_COST.get(action.loco_type, 0)
    if budget_remaining < cost:
        return f"insufficient build budget for upgrade (need {cost}M, have {budget_remaining}M remaining)", 0
    return None, cost


# ---------------------------------------------------------------------------
# City access limits
# ---------------------------------------------------------------------------

def check_city_access(
    map_data: dict[str, HexNode],
    player: PlayerState,
    all_players: list[PlayerState],
    to_node: str,
    staged_edges: set[frozenset[str]],
) -> str | None:
    node_type = map_data[to_node].terrain_type
    if node_type not in ("medium_city", "small_city"):
        return None

    max_players = 3 if node_type == "medium_city" else 2
    max_sections = 3  # per player, both city types

    # Count distinct players already connected
    connected_players: set[str] = set()
    for p in all_players:
        for e in p.owned_edges:
            if to_node in e:
                connected_players.add(p.player_id)
                break
    # Also count staged edges for this player
    for e in staged_edges:
        if to_node in e:
            connected_players.add(player.player_id)
            break

    is_new_player = player.player_id not in connected_players
    current_count = len(connected_players)

    if is_new_player and current_count >= max_players:
        return f"{node_type} at player capacity (max {max_players} players)"

    # Per-player section limit
    player_sections = sum(1 for e in (player.owned_edges | staged_edges) if to_node in e)
    if player_sections >= max_sections:
        return f"exceeded {max_sections} track sections into/out of this {node_type}"

    return None


# ---------------------------------------------------------------------------
# Blocking rule — tier-1 local saturation check
# ---------------------------------------------------------------------------

def check_blocking(
    map_data: dict[str, HexNode],
    all_players: list[PlayerState],
    staged_edges: set[frozenset[str]],
    from_node: str,
    to_node: str,
    building_player_id: str,
) -> str | None:
    """
    Tier-1: reject if this edge is the last unowned entry point into a
    protected node and at least one other player has no connection to it yet.

    TODO: implement full blocking check (BFS over hex graph) for tier-2.
    """
    to = map_data[to_node]
    if not to.is_city() and not to.is_ferry():
        return None

    all_owned: set[frozenset[str]] = set()
    for p in all_players:
        all_owned |= p.owned_edges
    all_owned |= staged_edges

    neighbor_ids = list(to.neighbors.keys())
    candidate_edges = [frozenset({to_node, nb}) for nb in neighbor_ids]
    unowned_entries = [e for e in candidate_edges if e not in all_owned]

    proposed_edge = frozenset({from_node, to_node})
    remaining_after = [e for e in unowned_entries if e != proposed_edge]

    if len(remaining_after) <= 1:
        players_without_connection = [
            p for p in all_players
            if p.player_id != building_player_id
            and not any(to_node in e for e in p.owned_edges)
        ]
        if players_without_connection:
            return f"placement would block other players from connecting to {to.city_name or to_node}"

    return None


# ---------------------------------------------------------------------------
# Ferry helpers
# ---------------------------------------------------------------------------

def _count_ferry_players(
    ferry_node: str,
    self_id: str,
    all_players: list[PlayerState],
    staged_edges: set[frozenset[str]],
) -> int:
    """Count distinct players (excluding self) already connected to this ferry node."""
    connected: set[str] = set()
    for p in all_players:
        if p.player_id == self_id:
            continue
        if any(ferry_node in e for e in p.owned_edges):
            connected.add(p.player_id)
    return len(connected)


def _ferry_expanded_reachable(
    map_data: dict[str, HexNode],
    owned_edges: set[frozenset[str]],
) -> set[str]:
    """Reachable nodes from owned_edges, plus ferry-pair destinations for any owned ferry endpoint."""
    nodes = {n for e in owned_edges for n in e}
    for node in list(nodes):
        n = map_data.get(node)
        if n and n.is_ferry() and n.ferry_link:
            nodes.add(n.ferry_link.to)
    return nodes
