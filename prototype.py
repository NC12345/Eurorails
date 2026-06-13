#!/usr/bin/env python3
"""
Eurorails pygame prototype — single-player.

Keys:
  O       Switch to Operate mode (move / cargo)
  B       Switch to Build mode (lay track / upgrade)
  P       Pick up resource at current city
  D       Deliver resource matching a demand card
  X       Drop off first cargo item (no payout)
  U       Upgrade train (Build mode only)
  Enter   End turn
  Esc     Cancel current selection
  Q       Quit
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field

import pygame

from game_state import (
    BuildEdge,
    GamePhase,
    GameState,
    LocoType,
    LOCO_STATS,
    UPGRADE_COST,
    VALID_UPGRADE_PATHS,
    PlayerState,
    RouteCard,
    TrainState,
    UpgradeTrain,
    build_city_index,
    draw_route_card,
    load_map,
    load_resource_index,
    load_resource_supply,
    load_route_deck,
)
from track_builder import execute_build
from pathfinding import reachable_nodes, shortest_move_path


# ── Screen constants ───────────────────────────────────────────────────────────

SCREEN_W  = 1500
SCREEN_H  = 880
SIDEBAR_W = 340
MAP_W     = SCREEN_W - SIDEBAR_W
FPS       = 60

# ── Colors ────────────────────────────────────────────────────────────────────

BG_MAP      = (18,  28,  48)
BG_SIDEBAR  = (12,  18,  32)
C_CLEAR     = (90,  90,  90)
C_MOUNTAIN  = (190, 150,  50)
C_ALPINE    = (210,  50,  50)
C_SMALL     = (0,   200, 200)
C_MEDIUM    = (255, 155,   0)
C_LARGE     = (200,   0, 200)
C_FERRY_N   = (0,   155, 155)
C_RIVER     = (30,  100, 220)
C_LAKE      = (10,   40, 150)
C_FERRY_L   = (0,   170,  70)
C_TRACK     = (255, 215,  50)
C_REACHABLE = (50,  200, 100)
C_PATH      = (0,   220, 255)
C_BUILD_HL  = (255, 230, 100)
C_BUILD_SRC = (255, 200,  50)
C_TRAIN     = (255, 255, 255)
C_TEXT      = (210, 210, 210)
C_HEADER    = (255, 200,  50)
C_ERROR     = (255,  80,  80)
C_SUCCESS   = (80,  230, 120)
C_DIM       = (130, 130, 130)
C_DIVIDER   = (50,   55,  75)
C_OP_MODE   = (50,  200, 100)
C_BLD_MODE  = (255, 160,   0)

NODE_COLOR = {
    "clear":            C_CLEAR,
    "mountain":         C_MOUNTAIN,
    "alpine":           C_ALPINE,
    "small_city":       C_SMALL,
    "medium_city":      C_MEDIUM,
    "large_city":       C_LARGE,
    "ferry":            C_FERRY_N,
    "ferry_small_city": C_SMALL,
}

NODE_RADIUS = {
    "clear":            2,
    "mountain":         3,
    "alpine":           3,
    "small_city":       5,
    "medium_city":      5,
    "large_city":       7,
    "ferry":            5,
    "ferry_small_city": 5,
}


# ── Projection ────────────────────────────────────────────────────────────────

def compute_projection(map_data, map_w: int, map_h: int, margin: int = 25):
    xs, ys = [], []
    for node in map_data.values():
        if node.is_sea():
            continue
        xs.append(node.axial_q)
        ys.append(node.axial_r * math.sqrt(3) / 2)  # positive: row 0 = top, row N = bottom
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    scale = min(
        (map_w - 2 * margin) / (xmax - xmin),
        (map_h - 2 * margin) / (ymax - ymin),
    )
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    ox = map_w / 2 - cx * scale
    oy = map_h / 2 - cy * scale  # subtract because pygame y increases downward
    return scale, ox, oy


def node_to_screen(node, scale: float, ox: float, oy: float) -> tuple[int, int]:
    x = node.axial_q * scale + ox
    y = node.axial_r * (math.sqrt(3) / 2) * scale + oy  # positive: larger r = lower on screen
    return int(x), int(y)


def build_screen_pos(map_data, scale, ox, oy) -> dict[str, tuple[int, int]]:
    return {
        nid: node_to_screen(node, scale, ox, oy)
        for nid, node in map_data.items()
        if not node.is_sea()
    }


# ── Hit detection ─────────────────────────────────────────────────────────────

def nearest_node(mx: int, my: int, screen_pos: dict, threshold: float) -> str | None:
    best_d = threshold
    best_id = None
    for nid, (sx, sy) in screen_pos.items():
        d = math.hypot(mx - sx, my - sy)
        if d < best_d:
            best_d = d
            best_id = nid
    return best_id


# ── Static map rendering (pre-baked to a surface) ─────────────────────────────

def _dashed_line(surf, color, p1, p2, dash=6, gap=4, w=1):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    total = math.hypot(dx, dy)
    if total < 1:
        return
    ux, uy = dx / total, dy / total
    pos, drawing = 0.0, True
    while pos < total:
        end = min(pos + (dash if drawing else gap), total)
        if drawing:
            x1 = int(p1[0] + ux * pos);  y1 = int(p1[1] + uy * pos)
            x2 = int(p1[0] + ux * end);  y2 = int(p1[1] + uy * end)
            pygame.draw.line(surf, color, (x1, y1), (x2, y2), w)
        pos = end
        drawing = not drawing


def draw_water_obstacles(surf, map_data, screen_pos, scale):
    done: set[frozenset] = set()
    half_wall = scale / (2 * math.sqrt(3))
    for nid, node in map_data.items():
        if node.is_sea() or nid not in screen_pos:
            continue
        sx1, sy1 = screen_pos[nid]
        for nb_id, obs in node.neighbors.items():
            if not (obs.river or obs.lake):
                continue
            sig = frozenset({nid, nb_id})
            if sig in done or nb_id not in screen_pos:
                continue
            done.add(sig)
            sx2, sy2 = screen_pos[nb_id]
            xm = (sx1 + sx2) / 2
            ym = (sy1 + sy2) / 2
            dx = sx2 - sx1
            dy = sy2 - sy1
            L = math.hypot(dx, dy)
            if L < 1:
                continue
            px = -dy / L
            py = dx / L
            color = C_LAKE if obs.lake else C_RIVER
            p1 = (int(xm + px * half_wall), int(ym + py * half_wall))
            p2 = (int(xm - px * half_wall), int(ym - py * half_wall))
            pygame.draw.line(surf, color, p1, p2, 2)


def draw_ferry_links(surf, map_data, screen_pos):
    done: set[frozenset] = set()
    for nid, node in map_data.items():
        if not node.ferry_link or nid not in screen_pos:
            continue
        partner = node.ferry_link.to
        sig = frozenset({nid, partner})
        if sig in done or partner not in screen_pos:
            continue
        done.add(sig)
        _dashed_line(surf, C_FERRY_L, screen_pos[nid], screen_pos[partner], dash=6, gap=4, w=1)


def draw_nodes(surf, map_data, screen_pos):
    for nid, node in map_data.items():
        if node.is_sea() or nid not in screen_pos:
            continue
        sx, sy = screen_pos[nid]
        color  = NODE_COLOR.get(node.terrain_type, C_CLEAR)
        radius = NODE_RADIUS.get(node.terrain_type, 2)
        pygame.draw.circle(surf, color, (sx, sy), radius)
        if node.terrain_type == "ferry_small_city":
            pygame.draw.circle(surf, (0, 0, 0), (sx, sy), max(1, radius // 2))


# ── Dynamic overlay rendering ─────────────────────────────────────────────────

def draw_owned_track(surf, owned_edges, screen_pos):
    for edge in owned_edges:
        a, b = tuple(edge)
        if a in screen_pos and b in screen_pos:
            pygame.draw.line(surf, C_TRACK, screen_pos[a], screen_pos[b], 3)


def draw_highlighted_path(surf, path, screen_pos):
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        if a in screen_pos and b in screen_pos:
            pygame.draw.line(surf, C_PATH, screen_pos[a], screen_pos[b], 4)


def draw_reachable_overlay(surf, reachable, screen_pos, scale):
    r = max(int(scale * 0.45), 5)
    for nid in reachable:
        if nid not in screen_pos:
            continue
        sx, sy = screen_pos[nid]
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*C_REACHABLE, 70), (r, r), r)
        surf.blit(s, (sx - r, sy - r))


def draw_build_overlay(surf, neighbors, src, screen_pos, scale):
    r = max(int(scale * 0.45), 5)
    for nid in neighbors:
        if nid not in screen_pos:
            continue
        sx, sy = screen_pos[nid]
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*C_BUILD_HL, 90), (r, r), r)
        surf.blit(s, (sx - r, sy - r))
    if src and src in screen_pos:
        sx, sy = screen_pos[src]
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*C_BUILD_SRC, 140), (r, r), r)
        surf.blit(s, (sx - r, sy - r))


def draw_train_marker(surf, train_node, screen_pos, scale):
    if train_node not in screen_pos:
        return
    sx, sy = screen_pos[train_node]
    r = max(int(scale * 0.38), 5)
    pygame.draw.circle(surf, C_TRAIN, (sx, sy), r)
    pygame.draw.circle(surf, (40, 40, 40), (sx, sy), r, 2)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def draw_sidebar(surf, ui, player, turn_number, fsm, fmd, flg):
    x0 = MAP_W
    pygame.draw.rect(surf, BG_SIDEBAR, (x0, 0, SIDEBAR_W, SCREEN_H))
    pygame.draw.line(surf, C_DIVIDER, (x0, 0), (x0, SCREEN_H), 2)

    x = x0 + 14
    y = 12
    rw = SIDEBAR_W - 24  # usable text width

    def txt(s, font, color, indent=0):
        nonlocal y
        surf.blit(font.render(s, True, color), (x + indent, y))
        y += font.get_linesize() + 2

    def div():
        nonlocal y
        pygame.draw.line(surf, C_DIVIDER, (x0 + 8, y + 3), (x0 + SIDEBAR_W - 8, y + 3), 1)
        y += 10

    mode_color = C_OP_MODE if ui.mode == "OPERATE" else C_BLD_MODE
    txt(f"MODE: {ui.mode}", flg, mode_color)
    txt(f"Turn {turn_number}", fsm, C_DIM)
    div()

    loco = player.train.loco_type.name.replace("_", " ")
    txt("TRAIN", fsm, C_HEADER)
    txt(f"  {loco}", fsm, C_TEXT)
    txt(f"  Movement: {player.train.remaining_movement}/{player.train.max_speed()}", fsm, C_TEXT)
    txt(f"  ECU: {player.ecu}M", fmd, C_HEADER)
    div()

    cap = player.train.cargo_capacity()
    txt(f"CARGO  ({len(player.train.cargo)}/{cap})", fsm, C_HEADER)
    if player.train.cargo:
        for item in player.train.cargo:
            txt(f"  • {item}", fsm, C_TEXT)
    else:
        txt("  (empty)", fsm, C_DIM)
    div()

    txt("ROUTE CARDS", fsm, C_HEADER)
    for i, card in enumerate(player.hand):
        txt(f"  [{i + 1}]", fsm, C_DIM)
        for route in card.routes:
            txt(f"    {route.resource_name} → {route.city_name}  +{route.amount}M", fsm, C_TEXT)
    div()

    for line in ["O:Operate  B:Build", "P:Pickup  D:Deliver  X:Drop", "U:Upgrade  Enter:End Turn", "Esc:Cancel  Q:Quit"]:
        txt(line, fsm, C_DIM)
    div()

    if ui.message:
        color = C_SUCCESS if ui.message_ok else C_ERROR
        words = ui.message.split()
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if fsm.size(test)[0] > rw:
                if cur:
                    txt(cur, fsm, color)
                cur = word
            else:
                cur = test
        if cur:
            txt(cur, fsm, color)


# ── UI state ──────────────────────────────────────────────────────────────────

@dataclass
class UIState:
    mode: str = "OPERATE"
    selected_node: str | None = None
    highlighted_path: list[str] = field(default_factory=list)
    highlighted_neighbors: set[str] = field(default_factory=set)
    reachable: set[str] = field(default_factory=set)
    message: str = ""
    message_ok: bool = True

    def msg(self, s: str, ok: bool = True):
        self.message = s
        self.message_ok = ok

    def clear(self):
        self.selected_node = None
        self.highlighted_path.clear()
        self.highlighted_neighbors.clear()


# ── Game actions ──────────────────────────────────────────────────────────────

def do_move(game, player, path, ui):
    steps = len(path) - 1
    if steps <= 0:
        return
    if steps > player.train.remaining_movement:
        ui.msg(f"Need {steps} moves, only {player.train.remaining_movement} left.", ok=False)
        return
    for i in range(1, len(path)):
        src_id, dst_id = path[i - 1], path[i]
        src = game.map_data[src_id]
        dst = game.map_data[dst_id]
        if not src.has_neighbor(dst_id):
            ui.msg(f"Not adjacent: {src_id} → {dst_id}", ok=False)
            return
        edge = frozenset({src_id, dst_id})
        is_interior = (
            src.is_major_city() and dst.is_major_city()
            and src.city_name == dst.city_name
        )
        if not is_interior and edge not in player.owned_edges:
            ui.msg(f"No track on {src_id}—{dst_id}.", ok=False)
            return
        if dst_id == player.train.previous_node and not src.is_city():
            ui.msg("Can't reverse here — not at a city.", ok=False)
            return
        player.train.previous_node = player.train.current_node
        player.train.current_node = dst_id
        player.train.remaining_movement -= 1
    dest = game.map_data[path[-1]]
    name = dest.city_name or path[-1]
    ui.msg(f"Moved to {name}. ({player.train.remaining_movement} moves left)", ok=True)


def do_pickup(game, player, ui):
    node = game.map_data[player.train.current_node]
    city = node.city_name
    if not city:
        ui.msg("Not at a city.", ok=False)
        return
    if len(player.train.cargo) >= player.train.cargo_capacity():
        ui.msg("Cargo full.", ok=False)
        return
    for res in game.resource_index.get(city, []):
        if game.resource_supply.get(res, 0) > 0:
            player.train.cargo.append(res)
            game.resource_supply[res] -= 1
            ui.msg(f"Picked up {res} at {city}.", ok=True)
            return
    ui.msg(f"No resources available at {city}.", ok=False)


def do_deliver(game, player, ui):
    node = game.map_data[player.train.current_node]
    city = node.city_name
    if not city:
        ui.msg("Not at a city.", ok=False)
        return
    for card in player.hand:
        for route in card.routes:
            if route.city_name == city and route.resource_name in player.train.cargo:
                player.train.cargo.remove(route.resource_name)
                player.ecu += route.amount
                player.hand.remove(card)
                game.route_discard.append(card)
                new = draw_route_card(game.route_deck, game.route_discard)
                if new:
                    player.hand.append(new)
                ui.msg(f"Delivered {route.resource_name} to {city}! +{route.amount}M ECU", ok=True)
                return
    ui.msg("No matching demand card for this city/cargo.", ok=False)


def do_dropoff(game, player, ui):
    if not player.train.cargo:
        ui.msg("Nothing to drop off.", ok=False)
        return
    res = player.train.cargo.pop(0)
    game.resource_supply[res] = game.resource_supply.get(res, 0) + 1
    ui.msg(f"Dropped off {res}.", ok=True)


def do_upgrade(game, player, ui):
    options = sorted(
        VALID_UPGRADE_PATHS.get(player.train.loco_type, set()),
        key=lambda l: l.name,
    )
    if not options:
        ui.msg("No upgrade available for this locomotive.", ok=False)
        return
    target = options[0]
    result = execute_build(game, player.player_id, [UpgradeTrain(target)])
    if result.ok:
        ui.msg(
            f"Upgraded to {target.name.replace('_', ' ')}! -{result.total_cost}M ECU",
            ok=True,
        )
    else:
        ui.msg(result.error or "Upgrade failed.", ok=False)


def buildable_neighbors(game, player, src_id) -> set[str]:
    src = game.map_data[src_id]
    result = set()
    for nb_id in src.neighbors:
        nb = game.map_data.get(nb_id)
        if nb is None or nb.is_sea():
            continue
        if frozenset({src_id, nb_id}) in player.owned_edges:
            continue
        if src.is_major_city() and nb.is_major_city() and src.city_name == nb.city_name:
            continue
        result.add(nb_id)
    return result


def refresh_reachable(game, player):
    return reachable_nodes(
        game.map_data, player.owned_edges,
        player.train.current_node, player.train.remaining_movement,
    )


# ── Game initialization ───────────────────────────────────────────────────────

def make_game(start_city: str = "Paris") -> tuple[GameState, PlayerState]:
    map_data = load_map()
    city_index = build_city_index(map_data)
    resource_index = load_resource_index()
    resource_supply = load_resource_supply()
    route_deck = load_route_deck()
    route_discard: list[RouteCard] = []

    nodes = city_index.get(start_city)
    if not nodes:
        raise ValueError(f"City not found: {start_city!r}")
    start_node = nodes[0]

    hand = []
    for _ in range(3):
        card = draw_route_card(route_deck, route_discard)
        if card:
            hand.append(card)

    train = TrainState(
        current_node=start_node,
        previous_node=None,
        remaining_movement=LOCO_STATS[LocoType.FREIGHT][0],
        cargo=[],
        loco_type=LocoType.FREIGHT,
        committed_to_ferry=False,
    )
    player = PlayerState(
        player_id="p1",
        ecu=50,
        train=train,
        owned_edges=set(),
        hand=hand,
        track_fees_owed={},
    )
    game = GameState(
        map_data=map_data,
        city_index=city_index,
        resource_index=resource_index,
        resource_supply=resource_supply,
        players=[player],
        current_player_index=0,
        phase=GamePhase.NORMAL_PLAY,
        route_deck=route_deck,
        route_discard=route_discard,
        turn_number=1,
    )
    return game, player


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Eurorails Prototype")
    clock = pygame.time.Clock()

    fsm = pygame.font.SysFont("monospace", 12)
    fmd = pygame.font.SysFont("monospace", 14, bold=True)
    flg = pygame.font.SysFont("monospace", 16, bold=True)

    print("Loading map…")
    game, player = make_game("Paris")
    print(f"Loaded {len(game.map_data)} nodes. Building screen positions…")

    scale, ox, oy = compute_projection(game.map_data, MAP_W, SCREEN_H)
    screen_pos = build_screen_pos(game.map_data, scale, ox, oy)
    click_threshold = max(scale * 0.7, 8)

    print("Pre-rendering static map…")
    map_surf = pygame.Surface((MAP_W, SCREEN_H))
    map_surf.fill(BG_MAP)
    draw_water_obstacles(map_surf, game.map_data, screen_pos, scale)
    draw_ferry_links(map_surf, game.map_data, screen_pos)
    draw_nodes(map_surf, game.map_data, screen_pos)
    print("Ready.")

    ui = UIState()
    ui.reachable = refresh_reachable(game, player)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                k = event.key

                if k == pygame.K_q:
                    pygame.quit()
                    sys.exit()

                elif k == pygame.K_ESCAPE:
                    ui.clear()
                    ui.msg("Cancelled.")

                elif k == pygame.K_o:
                    ui.mode = "OPERATE"
                    ui.clear()
                    ui.reachable = refresh_reachable(game, player)
                    ui.msg("Operate mode.")

                elif k == pygame.K_b:
                    ui.mode = "BUILD"
                    ui.clear()
                    ui.reachable = set()
                    ui.msg("Build mode.")

                elif k == pygame.K_RETURN:
                    game.turn_number += 1
                    player.train.remaining_movement = player.train.max_speed()
                    player.train.previous_node = None
                    player.track_fees_owed.clear()
                    player.major_city_touches_this_turn = {}
                    player.actions_taken_this_turn = False
                    ui.mode = "OPERATE"
                    ui.clear()
                    ui.reachable = refresh_reachable(game, player)
                    ui.msg(f"Turn {game.turn_number}. Movement reset to {player.train.max_speed()}.")

                elif k == pygame.K_p and ui.mode == "OPERATE":
                    do_pickup(game, player, ui)

                elif k == pygame.K_d and ui.mode == "OPERATE":
                    do_deliver(game, player, ui)

                elif k == pygame.K_x and ui.mode == "OPERATE":
                    do_dropoff(game, player, ui)

                elif k == pygame.K_u and ui.mode == "BUILD":
                    do_upgrade(game, player, ui)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mx >= MAP_W:
                    continue

                clicked = nearest_node(mx, my, screen_pos, click_threshold)
                if clicked is None:
                    continue

                if ui.mode == "OPERATE":
                    if clicked == player.train.current_node:
                        ui.clear()
                        continue

                    if ui.selected_node is None:
                        if clicked in ui.reachable:
                            path = shortest_move_path(
                                game.map_data, player.owned_edges,
                                player.train.current_node, clicked,
                                player.train.remaining_movement,
                            )
                            if path:
                                ui.selected_node = clicked
                                ui.highlighted_path = path
                                dest = game.map_data[clicked]
                                name = dest.city_name or clicked
                                ui.msg(f"Path to {name} ({len(path)-1} moves). Click again to confirm.")
                            else:
                                ui.msg("No path found.", ok=False)
                        else:
                            ui.msg("Node not reachable with current movement.", ok=False)

                    elif clicked == ui.selected_node:
                        path = list(ui.highlighted_path)
                        ui.clear()
                        do_move(game, player, path, ui)
                        ui.reachable = refresh_reachable(game, player)

                    else:
                        if clicked in ui.reachable:
                            path = shortest_move_path(
                                game.map_data, player.owned_edges,
                                player.train.current_node, clicked,
                                player.train.remaining_movement,
                            )
                            if path:
                                ui.selected_node = clicked
                                ui.highlighted_path = path
                                dest = game.map_data[clicked]
                                name = dest.city_name or clicked
                                ui.msg(f"Path to {name} ({len(path)-1} moves). Click again to confirm.")
                            else:
                                ui.msg("No path found.", ok=False)
                        else:
                            ui.msg("Node not reachable with current movement.", ok=False)

                elif ui.mode == "BUILD":
                    node = game.map_data.get(clicked)
                    if node is None or node.is_sea():
                        continue

                    if ui.selected_node is None:
                        ui.selected_node = clicked
                        ui.highlighted_neighbors = buildable_neighbors(game, player, clicked)
                        name = node.city_name or clicked
                        ui.msg(f"Build from {name}. Click a yellow node to build edge.")

                    elif clicked == ui.selected_node:
                        ui.clear()
                        ui.msg("Deselected.")

                    elif clicked in ui.highlighted_neighbors:
                        result = execute_build(game, player.player_id, [BuildEdge(ui.selected_node, clicked)])
                        if result.ok:
                            ui.msg(f"Built! -{result.total_cost}M ECU. Balance: {player.ecu}M", ok=True)
                            ui.highlighted_neighbors = buildable_neighbors(game, player, ui.selected_node)
                        else:
                            ui.msg(result.error or "Build failed.", ok=False)

                    else:
                        ui.selected_node = clicked
                        ui.highlighted_neighbors = buildable_neighbors(game, player, clicked)
                        name = node.city_name or clicked
                        ui.msg(f"Build from {name}. Click a yellow node to build edge.")

        # ── Draw ──────────────────────────────────────────────────────────────
        screen.blit(map_surf, (0, 0))

        if ui.mode == "OPERATE":
            draw_reachable_overlay(screen, ui.reachable, screen_pos, scale)

        draw_owned_track(screen, player.owned_edges, screen_pos)

        if ui.highlighted_path:
            draw_highlighted_path(screen, ui.highlighted_path, screen_pos)

        if ui.mode == "BUILD":
            draw_build_overlay(screen, ui.highlighted_neighbors, ui.selected_node, screen_pos, scale)

        draw_train_marker(screen, player.train.current_node, screen_pos, scale)

        draw_sidebar(screen, ui, player, game.turn_number, fsm, fmd, flg)

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
