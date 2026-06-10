from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Union


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LocoType(Enum):
    FREIGHT       = auto()  # max_speed=9,  capacity=2
    FAST_FREIGHT  = auto()  # max_speed=12, capacity=2
    HEAVY_FREIGHT = auto()  # max_speed=9,  capacity=3
    SUPERFREIGHT  = auto()  # max_speed=12, capacity=3


class GamePhase(Enum):
    INITIAL_BUILD_1 = auto()  # snake round 1 — clockwise, build only
    INITIAL_BUILD_2 = auto()  # snake round 2 — counter-clockwise, build only
    NORMAL_PLAY     = auto()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCO_STATS: dict[LocoType, tuple[int, int]] = {
    LocoType.FREIGHT:       (9,  2),
    LocoType.FAST_FREIGHT:  (12, 2),
    LocoType.HEAVY_FREIGHT: (9,  3),
    LocoType.SUPERFREIGHT:  (12, 3),
}

TERRAIN_BUILD_COST: dict[str, int] = {
    "clear":       1,
    "mountain":    2,
    "alpine":      5,
    "small_city":  3,
    "medium_city": 3,
    "large_city":  5,
}

# lake also covers ocean_inlet per CLAUDE.md
WATER_SURCHARGE: dict[str, int] = {
    "river": 2,
    "lake":  3,
}

UPGRADE_COST: dict[LocoType, int] = {
    LocoType.FAST_FREIGHT:  20,
    LocoType.HEAVY_FREIGHT: 20,
    LocoType.SUPERFREIGHT:  20,
}

VALID_UPGRADE_PATHS: dict[LocoType, set[LocoType]] = {
    LocoType.FREIGHT:       {LocoType.FAST_FREIGHT, LocoType.HEAVY_FREIGHT},
    LocoType.FAST_FREIGHT:  {LocoType.SUPERFREIGHT},
    LocoType.HEAVY_FREIGHT: {LocoType.SUPERFREIGHT},
    LocoType.SUPERFREIGHT:  set(),
}

CITY_TYPES: frozenset[str] = frozenset({
    "small_city", "medium_city", "large_city", "ferry_small_city"
})
FERRY_TYPES: frozenset[str] = frozenset({"ferry", "ferry_small_city"})
MAJOR_CITY_TYPE = "large_city"


# ---------------------------------------------------------------------------
# Route / demand card dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Route:
    city_name: str
    resource_name: str
    amount: int  # M ECU payout on Deliver


@dataclass
class RouteCard:
    routes: list[Route]  # exactly 3


# ---------------------------------------------------------------------------
# Train and player state
# ---------------------------------------------------------------------------

@dataclass
class TrainState:
    current_node: str
    previous_node: str | None   # None = hasn't moved yet; used for reversing rule
    remaining_movement: int
    cargo: list[str]            # resource names loaded, max len = loco capacity
    loco_type: LocoType
    committed_to_ferry: bool    # if True at end of operate: teleport + half-speed next turn

    def max_speed(self) -> int:
        return LOCO_STATS[self.loco_type][0]

    def cargo_capacity(self) -> int:
        return LOCO_STATS[self.loco_type][1]


@dataclass
class PlayerState:
    player_id: str
    ecu: int                          # M ECU balance
    train: TrainState
    owned_edges: set[frozenset[str]]  # frozenset({node_a, node_b}) per section
    hand: list[RouteCard]             # demand hand, 3 cards during NORMAL_PLAY
    track_fees_owed: dict[str, int]   # player_id -> M ECU owed this turn; settled at end of operate


@dataclass
class GameState:
    map_data: dict[str, dict]          # master_map.json loaded once
    city_index: dict[str, list[str]]   # city_name -> [node_ids]
    resource_index: dict[str, list[str]]  # city_name -> [resource_names]
    players: list[PlayerState]         # ordered by turn order
    current_player_index: int
    phase: GamePhase
    route_deck: list[RouteCard]        # shuffled draw pile
    route_discard: list[RouteCard]
    turn_number: int                   # 1-based


# ---------------------------------------------------------------------------
# Action types (frozen — safe to use in sets / as dict keys)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MoveTo:
    node_id: str

@dataclass(frozen=True)
class PickUp:
    resource: str

@dataclass(frozen=True)
class DropOff:
    resource: str   # discard without payout

@dataclass(frozen=True)
class Deliver:
    resource: str   # fulfill demand card, draw replacement

@dataclass(frozen=True)
class CommitFerry:
    pass            # commit to crossing; stops movement this turn

@dataclass(frozen=True)
class BuildEdge:
    from_node: str
    to_node: str

@dataclass(frozen=True)
class UpgradeTrain:
    loco_type: LocoType


OperateAction = Union[MoveTo, PickUp, DropOff, Deliver, CommitFerry]
BuildAction   = Union[BuildEdge, UpgradeTrain]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class OperateResult:
    ok: bool
    error: str | None
    payout_log: list[str]
    fees_charged: dict[str, int]  # {opponent_player_id: M ECU charged}


@dataclass
class BuildResult:
    ok: bool
    error: str | None
    total_cost: int
    edges_built: list[frozenset[str]]


# ---------------------------------------------------------------------------
# Map / deck helpers
# ---------------------------------------------------------------------------

def load_map(path: str = "master_map.json") -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_city_index(map_data: dict[str, dict]) -> dict[str, list[str]]:
    """city_name -> [node_id, ...] for all city-type nodes."""
    index: dict[str, list[str]] = {}
    for node_id, node in map_data.items():
        name = node.get("city_name")
        if name:
            index.setdefault(name, []).append(node_id)
    return index


def load_resource_index(path: str = "cities_to_resources.json") -> dict[str, list[str]]:
    """city_name -> [resource_name, ...] from cities_to_resources.json."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_route_deck(path: str = "route_cards.json") -> list[RouteCard]:
    """Load and shuffle the full route deck."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    deck = [
        RouteCard(routes=[Route(**r) for r in card])
        for card in raw
    ]
    random.shuffle(deck)
    return deck


def draw_route_card(
    deck: list[RouteCard],
    discard: list[RouteCard],
) -> RouteCard | None:
    """Draw from deck; reshuffle discard into deck if deck is empty."""
    if not deck:
        if not discard:
            return None
        deck.extend(discard)
        discard.clear()
        random.shuffle(deck)
    return deck.pop()
