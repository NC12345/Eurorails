from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Node-related constants (authoritative source; re-exported by game_state.py)
# ---------------------------------------------------------------------------

CITY_TYPES: frozenset[str] = frozenset({
    "small_city", "medium_city", "large_city", "ferry_small_city"
})
FERRY_TYPES: frozenset[str] = frozenset({"ferry", "ferry_small_city"})
MAJOR_CITY_TYPE = "large_city"

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


# ---------------------------------------------------------------------------
# Typed edge obstacle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EdgeObstacle:
    river: bool = False
    river_name: str | None = None
    lake: bool = False
    lake_name: str | None = None


# ---------------------------------------------------------------------------
# Typed ferry link
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FerryLink:
    to: str       # destination node ID
    cost_ecu: int


# ---------------------------------------------------------------------------
# Hex node
# ---------------------------------------------------------------------------

@dataclass
class HexNode:
    id: str
    row: int
    col: int
    axial_q: float
    axial_r: int
    terrain_type: str          # "type" in JSON — renamed to avoid shadowing builtin
    city_name: str | None
    neighbors: dict[str, EdgeObstacle]   # neighbor_id → obstacle data
    ferry_link: FerryLink | None

    # -- Terrain predicates --------------------------------------------------

    def is_sea(self) -> bool:
        return self.terrain_type == "space_sea"

    def is_city(self) -> bool:
        return self.terrain_type in CITY_TYPES

    def is_major_city(self) -> bool:
        return self.terrain_type == MAJOR_CITY_TYPE

    def is_ferry(self) -> bool:
        return self.terrain_type in FERRY_TYPES

    def is_major_city_interior_with(self, other: HexNode) -> bool:
        """True if both nodes are large_city nodes sharing the same city_name."""
        return (
            self.is_major_city()
            and other.is_major_city()
            and self.city_name is not None
            and self.city_name == other.city_name
        )

    # -- Navigation ----------------------------------------------------------

    def has_neighbor(self, node_id: str) -> bool:
        return node_id in self.neighbors

    def neighbor_edge(self, node_id: str) -> EdgeObstacle | None:
        return self.neighbors.get(node_id)

    def build_cost_to(self, to_node: HexNode) -> int:
        if to_node.is_ferry():
            return to_node.ferry_link.cost_ecu if to_node.ferry_link else 0
        base = TERRAIN_BUILD_COST.get(to_node.terrain_type, 1)
        obs = self.neighbor_edge(to_node.id)
        if obs and obs.lake:
            surcharge = WATER_SURCHARGE["lake"]
        elif obs and obs.river:
            surcharge = WATER_SURCHARGE["river"]
        else:
            surcharge = 0
        return base + surcharge

    # -- Construction --------------------------------------------------------

    @classmethod
    def from_dict(cls, node_id: str, data: dict) -> HexNode:
        neighbors = {
            nb_id: EdgeObstacle(
                river=bool(obs.get("river", False)),
                river_name=obs.get("river_name"),
                lake=bool(obs.get("lake", False)),
                lake_name=obs.get("lake_name"),
            )
            for nb_id, obs in data.get("neighbors", {}).items()
        }
        ferry_link = None
        if fl := data.get("ferry_link"):
            ferry_link = FerryLink(to=fl["to"], cost_ecu=fl["cost_ecu"])
        return cls(
            id=node_id,
            row=data["row"],
            col=data["col"],
            axial_q=data["axial_q"],
            axial_r=data["axial_r"],
            terrain_type=data["type"],
            city_name=data.get("city_name"),
            neighbors=neighbors,
            ferry_link=ferry_link,
        )
