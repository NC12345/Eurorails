from __future__ import annotations

from game_state import (
    CITY_TYPES,
    FERRY_TYPES,
    LOCO_STATS,
    MAJOR_CITY_TYPE,
    CommitFerry,
    Deliver,
    DropOff,
    GamePhase,
    GameState,
    MoveTo,
    OperateAction,
    OperateResult,
    PickUp,
    PlayerState,
    TrainState,
    draw_route_card,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute_operate(
    game_state: GameState,
    player_id: str,
    actions: list[OperateAction],
) -> OperateResult:
    """
    Execute the operate phase for a player.

    Validates and applies each action in sequence. On the first failure
    the function returns an error result; state may be partially mutated up
    to that point (incremental apply model).
    """
    if game_state.phase != GamePhase.NORMAL_PLAY:
        return OperateResult(
            ok=False,
            error="cannot operate during initial build phase",
            payout_log=[],
            fees_charged={},
        )

    player = _find_player(game_state, player_id)
    if player is None:
        return OperateResult(ok=False, error=f"unknown player: {player_id}", payout_log=[], fees_charged={})

    train = player.train
    player.track_fees_owed = {}

    # Ferry arrival setup — teleport and apply half speed
    if train.committed_to_ferry:
        _apply_ferry_arrival(game_state.map_data, train)
    else:
        train.remaining_movement = train.max_speed()

    payout_log: list[str] = []

    for action in actions:
        if isinstance(action, MoveTo):
            error = _execute_move_to(game_state.map_data, player, game_state.players, action)
        elif isinstance(action, PickUp):
            error = _execute_pickup(game_state.map_data, player, game_state.resource_index, action)
        elif isinstance(action, DropOff):
            error = _execute_dropoff(player, action)
        elif isinstance(action, Deliver):
            error, log_entry = _execute_deliver(game_state.map_data, player, game_state, action)
            if log_entry:
                payout_log.append(log_entry)
        elif isinstance(action, CommitFerry):
            error = _execute_commit_ferry(game_state.map_data, player, action)
        else:
            error = f"unknown action type: {type(action).__name__}"

        if error:
            return OperateResult(ok=False, error=error, payout_log=payout_log, fees_charged={})

    # Settle track usage fees
    fees_charged = _settle_fees(player, game_state.players)

    return OperateResult(ok=True, error=None, payout_log=payout_log, fees_charged=fees_charged)


# ---------------------------------------------------------------------------
# Ferry arrival (called at start of turn if committed_to_ferry=True)
# ---------------------------------------------------------------------------

def _apply_ferry_arrival(map_data: dict, train: TrainState) -> None:
    """Teleport to ferry destination and apply half speed for this turn."""
    ferry_link = map_data[train.current_node].get("ferry_link")
    if ferry_link:
        train.current_node = ferry_link["to"]
    base_speed = LOCO_STATS[train.loco_type][0]
    train.remaining_movement = base_speed // 2
    train.committed_to_ferry = False
    # previous_node intentionally NOT updated: teleport is not an edge traversal


# ---------------------------------------------------------------------------
# Per-action executors
# ---------------------------------------------------------------------------

def _execute_move_to(
    map_data: dict,
    player: PlayerState,
    all_players: list[PlayerState],
    action: MoveTo,
) -> str | None:
    train = player.train

    # Node exists
    if action.node_id not in map_data:
        return f"unknown node: {action.node_id}"

    # Not sea
    if map_data[action.node_id]["type"] == "space_sea":
        return "cannot move to sea node"

    # Adjacent
    neighbors = map_data[train.current_node].get("neighbors", {})
    if action.node_id not in neighbors:
        return f"{action.node_id} is not adjacent to {train.current_node}"

    # Movement points
    if train.remaining_movement < 1:
        return "no movement remaining"

    # Track access
    edge = frozenset({train.current_node, action.node_id})
    if _is_major_city_interior(map_data, train.current_node, action.node_id):
        pass  # universal free access inside major city
    elif edge in player.owned_edges:
        pass  # own track — free
    else:
        opponent = _find_opponent_owner(edge, player.player_id, all_players)
        if opponent is None:
            return "no track on this edge"
        # Must be able to afford the usage fee (4M per turn total)
        fees_so_far = sum(player.track_fees_owed.values())
        if player.ecu - fees_so_far < 4:
            return "insufficient funds for track usage fee"
        player.track_fees_owed[opponent] = player.track_fees_owed.get(opponent, 0) + 4

    # Reversing rule: blocked on non-city nodes
    if (
        map_data[train.current_node]["type"] not in CITY_TYPES
        and train.previous_node is not None
        and action.node_id == train.previous_node
    ):
        return "cannot reverse direction on non-city node"

    # Apply
    train.previous_node = train.current_node
    train.current_node = action.node_id
    train.remaining_movement -= 1
    return None


def _execute_commit_ferry(
    map_data: dict,
    player: PlayerState,
    action: CommitFerry,
) -> str | None:
    train = player.train
    node = map_data.get(train.current_node, {})

    if node.get("type") not in FERRY_TYPES:
        return "not at a ferry node"
    if not node.get("ferry_link"):
        return "ferry node has no link"

    # No ECU deduction — ferry passage cost is paid at build time
    train.committed_to_ferry = True
    train.remaining_movement = 0
    return None


def _execute_pickup(
    map_data: dict,
    player: PlayerState,
    city_index: dict[str, list[str]],
    action: PickUp,
) -> str | None:
    train = player.train
    node = map_data.get(train.current_node, {})

    if node.get("type") not in CITY_TYPES:
        return "not at a city node"

    city_name = node.get("city_name")
    if not city_name:
        return "city node has no city_name"

    # city_index is the resource index (city_name -> resources).
    if action.resource not in city_index.get(city_name, []):
        return f"{action.resource} not available at {city_name}"

    if len(train.cargo) >= train.cargo_capacity():
        return "cargo full"

    # No ECU deduction — pickup is free
    train.cargo.append(action.resource)
    return None


def _execute_dropoff(
    player: PlayerState,
    action: DropOff,
) -> str | None:
    train = player.train
    if action.resource not in train.cargo:
        return f"{action.resource} not in cargo"
    train.cargo.remove(action.resource)
    return None


def _execute_deliver(
    map_data: dict,
    player: PlayerState,
    game_state: GameState,
    action: Deliver,
) -> tuple[str | None, str]:
    train = player.train
    node = map_data.get(train.current_node, {})

    if node.get("type") not in CITY_TYPES:
        return "not at a city node", ""

    city_name = node.get("city_name")
    if not city_name:
        return "city node has no city_name", ""

    if action.resource not in train.cargo:
        return f"{action.resource} not in cargo", ""

    # Find matching demand card
    matched_card = None
    matched_route = None
    for card in player.hand:
        for route in card.routes:
            if route.city_name == city_name and route.resource_name == action.resource:
                matched_card = card
                matched_route = route
                break
        if matched_card:
            break

    if matched_card is None:
        return f"no demand card for {action.resource} → {city_name}", ""

    # Apply delivery
    train.cargo.remove(action.resource)
    log_entry = (
        f"{player.player_id} delivered {action.resource} to {city_name} "
        f"for {matched_route.amount}M ECU"
    )
    # ECU payout stubbed — log only (economy deferred to future phase)

    # Discard card and draw replacement
    player.hand.remove(matched_card)
    game_state.route_discard.append(matched_card)
    new_card = draw_route_card(game_state.route_deck, game_state.route_discard)
    if new_card:
        player.hand.append(new_card)

    return None, log_entry


# ---------------------------------------------------------------------------
# Fee settlement
# ---------------------------------------------------------------------------

def _settle_fees(
    player: PlayerState,
    all_players: list[PlayerState],
) -> dict[str, int]:
    """Deduct accumulated track fees from player and credit opponents."""
    fees_charged: dict[str, int] = {}
    for opponent_id, amount in player.track_fees_owed.items():
        opponent = next((p for p in all_players if p.player_id == opponent_id), None)
        if opponent:
            player.ecu -= amount
            opponent.ecu += amount
            fees_charged[opponent_id] = amount
    player.track_fees_owed = {}
    return fees_charged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_player(game_state: GameState, player_id: str) -> PlayerState | None:
    return next((p for p in game_state.players if p.player_id == player_id), None)


def _find_opponent_owner(
    edge: frozenset[str],
    self_id: str,
    all_players: list[PlayerState],
) -> str | None:
    """Return player_id of the opponent who owns this edge, or None."""
    for p in all_players:
        if p.player_id != self_id and edge in p.owned_edges:
            return p.player_id
    return None


def _is_major_city_interior(map_data: dict, node_a: str, node_b: str) -> bool:
    """True if both nodes are large_city nodes sharing the same city_name."""
    na = map_data.get(node_a, {})
    nb = map_data.get(node_b, {})
    return (
        na.get("type") == "large_city"
        and nb.get("type") == "large_city"
        and na.get("city_name") is not None
        and na.get("city_name") == nb.get("city_name")
    )
