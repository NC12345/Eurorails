import json
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import tkinter as tk

matplotlib.rcParams['keymap.quit'] = []

MASTER_MAP_PATH = "master_map.json"

try:
    with open(MASTER_MAP_PATH, 'r') as f:
        master_map = json.load(f)
    print(f"Loaded {len(master_map)} nodes.")
except FileNotFoundError:
    print(f"Error: '{MASTER_MAP_PATH}' not found.")
    master_map = {}

FERRY_TYPES = {'ferry', 'ferry_small_city'}

# Ensure all ferry nodes have ferry_link field
for node_data in master_map.values():
    if node_data.get('type') in FERRY_TYPES and 'ferry_link' not in node_data:
        node_data['ferry_link'] = None

fig, ax = plt.subplots(figsize=(14, 10))
ax.set_aspect('equal')
ax.set_facecolor('#f0f5fa')

x_coords = []
y_coords = []
plotted_nodes = []
rendered_edges = set()
ferry_link_artists = []

# --- LAYER 1: RIVER/LAKE EDGES ---
for node_id, node_data in master_map.items():
    q1 = node_data["axial_q"]
    r1 = node_data["axial_r"]
    x1, y1 = q1, -r1 * (np.sqrt(3) / 2)

    for neighbor_id, connection in node_data.get("neighbors", {}).items():
        edge_sig = "__".join(sorted([node_id, neighbor_id]))
        if edge_sig in rendered_edges:
            continue
        if neighbor_id in master_map:
            is_river = connection.get("river", False)
            is_lake = connection.get("lake", False)
            if is_river or is_lake:
                rendered_edges.add(edge_sig)
                q2 = master_map[neighbor_id]["axial_q"]
                r2 = master_map[neighbor_id]["axial_r"]
                x2, y2 = q2, -r2 * (np.sqrt(3) / 2)
                xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
                dx, dy = x2 - x1, y2 - y1
                L = (dx**2 + dy**2) ** 0.5
                px, py = -dy / L, dx / L
                half_hex_wall = (1 / np.sqrt(3)) / 2
                color = '#002266' if is_lake else '#0066cc'
                ax.plot(
                    [xm + px * half_hex_wall, xm - px * half_hex_wall],
                    [ym + py * half_hex_wall, ym - py * half_hex_wall],
                    color=color, linewidth=3.0, alpha=0.8, zorder=1
                )

# --- LAYER 2: NODES ---
for node_id, node_data in master_map.items():
    node_type = node_data.get("type")
    if node_type == "space_sea" or not node_type:
        continue

    q = node_data["axial_q"]
    r = node_data["axial_r"]
    x_graph = q
    y_graph = -r * (np.sqrt(3) / 2)
    x_coords.append(x_graph)
    y_coords.append(y_graph)

    if node_type == "clear":
        ax.plot(x_graph, y_graph, 'ko', markersize=2, zorder=2)
    elif node_type == "mountain":
        ax.plot(x_graph, y_graph, marker='^', color='#e6b800', markersize=3, linestyle='None', zorder=2)
    elif node_type == "alpine":
        ax.plot(x_graph, y_graph, marker='^', color='#ff3333', markersize=4, linestyle='None', zorder=2)
    elif node_type == "small_city":
        ax.plot(x_graph, y_graph, marker='o', color='#00cccc', markersize=5, linestyle='None', zorder=2)
    elif node_type == "medium_city":
        ax.plot(x_graph, y_graph, marker='s', color='#ff9900', markersize=5, linestyle='None', zorder=2)
    elif node_type == "large_city":
        ax.plot(x_graph, y_graph, marker='h', color='#cc00cc', markersize=6, linestyle='None', zorder=2)
    elif node_type == "ferry":
        ax.plot(x_graph, y_graph, marker='d', color='#009999', markersize=6, linestyle='None', zorder=2)
    elif node_type == "ferry_small_city":
        ax.plot(x_graph, y_graph, marker='o', color='#00cccc', markersize=5, linestyle='None', zorder=2)
        ax.plot(x_graph, y_graph, marker='o', color='black', markersize=2, linestyle='None', zorder=3)

    plotted_nodes.append((x_graph, y_graph, q, r, node_type, node_id, node_data))

if x_coords and y_coords:
    ax.set_xlim(min(x_coords) - 1.5, max(x_coords) + 1.5)
    ax.set_ylim(min(y_coords) - 1.5, max(y_coords) + 1.5)

plt.title("Eurorails — Ferry Linker", fontsize=13, fontweight='bold', pad=15)
ax.axis('off')
plt.tight_layout()


def draw_ferry_links():
    for artist in ferry_link_artists:
        artist.remove()
    ferry_link_artists.clear()

    rendered_pairs = set()
    for node_id, node_data in master_map.items():
        fl = node_data.get('ferry_link')
        if not isinstance(fl, dict):
            continue
        partner_id = fl.get('to')
        if not partner_id or partner_id not in master_map:
            continue
        pair_key = "__".join(sorted([node_id, partner_id]))
        if pair_key in rendered_pairs:
            continue
        rendered_pairs.add(pair_key)

        q1 = node_data["axial_q"]
        r1 = node_data["axial_r"]
        x1, y1 = q1, -r1 * (np.sqrt(3) / 2)
        q2 = master_map[partner_id]["axial_q"]
        r2 = master_map[partner_id]["axial_r"]
        x2, y2 = q2, -r2 * (np.sqrt(3) / 2)

        line, = ax.plot([x1, x2], [y1, y2], color='#00aa44', linewidth=1.5,
                        linestyle='--', alpha=0.8, zorder=1)
        cost = fl.get('cost_ecu', '?')
        label = ax.text((x1 + x2) / 2, (y1 + y2) / 2, f"{cost} ECU",
                        fontsize=7, color='#00aa44', ha='center', va='bottom', zorder=3)
        ferry_link_artists.extend([line, label])


draw_ferry_links()

# --- UI ---
tooltip = ax.annotate(
    "", xy=(0, 0), xytext=(10, 10),
    textcoords="offset points",
    bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="gray", alpha=0.9),
    fontsize=9, visible=False, zorder=5
)
_last_clicked = [None]

IDLE_MSG = "Click a ferry node to select  |  q = save & quit  |  Esc = cancel / quit"
status_text = ax.text(
    0.01, 0.99, IDLE_MSG,
    transform=ax.transAxes, va='top', ha='left',
    fontsize=9, color='#333333', zorder=5,
    bbox=dict(boxstyle='round,pad=0.4', fc='white', ec='gray', alpha=0.85)
)

_first = [None]       # (node_id, x, y) of first selected ferry
_highlight_a = [None]
_highlight_b = [None]
pending_changes = {}  # node_id -> ferry_link value (dict or None)

DISTANCE_THRESHOLD = 0.4


def _clear_first():
    _first[0] = None
    if _highlight_a[0] is not None:
        _highlight_a[0].remove()
        _highlight_a[0] = None


def open_cost_dialog(nid_a, nid_b):
    root = fig.canvas.manager.window
    result = [None]

    dialog = tk.Toplevel(root)
    dialog.title("Ferry Link")
    dialog.resizable(False, False)

    tk.Label(dialog, text=f"{nid_a}  ↔  {nid_b}", font=("Helvetica", 11)).pack(padx=16, pady=(12, 4))
    tk.Label(dialog, text="Cost (ECU):", font=("Helvetica", 10)).pack(padx=16)

    entry = tk.Entry(dialog, width=10, font=("Helvetica", 12))
    # Pre-fill from either node's existing link
    for nid in (nid_a, nid_b):
        fl = master_map[nid].get('ferry_link')
        if isinstance(fl, dict) and fl.get('cost_ecu') is not None:
            entry.insert(0, str(fl['cost_ecu']))
            break
    entry.select_range(0, tk.END)
    entry.pack(padx=16, pady=(0, 12))
    entry.focus_set()

    def _save(event=None):
        try:
            result[0] = int(entry.get().strip())
        except ValueError:
            pass
        dialog.destroy()

    def _cancel(event=None):
        dialog.destroy()

    entry.bind("<Return>", _save)
    entry.bind("<Escape>", _cancel)

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=(0, 12))
    tk.Button(btn_frame, text="Link", command=_save, width=8).pack(side=tk.LEFT, padx=6)
    tk.Button(btn_frame, text="Cancel", command=_cancel, width=8).pack(side=tk.LEFT, padx=6)

    dialog.wait_window()
    return result[0]


def apply_link(nid_a, nid_b, cost_ecu):
    # Clear stale back-links on any previously linked partners
    for nid in (nid_a, nid_b):
        fl = master_map[nid].get('ferry_link')
        if isinstance(fl, dict):
            old_partner = fl.get('to')
            if old_partner and old_partner in master_map and old_partner not in (nid_a, nid_b):
                master_map[old_partner]['ferry_link'] = None
                pending_changes[old_partner] = None

    master_map[nid_a]['ferry_link'] = {"to": nid_b, "cost_ecu": cost_ecu}
    master_map[nid_b]['ferry_link'] = {"to": nid_a, "cost_ecu": cost_ecu}
    pending_changes[nid_a] = master_map[nid_a]['ferry_link']
    pending_changes[nid_b] = master_map[nid_b]['ferry_link']


def save_changes():
    with open(MASTER_MAP_PATH, 'w') as f:
        json.dump(master_map, f, indent=2)
    print(f"Saved {len(pending_changes)} ferry link change(s) to {MASTER_MAP_PATH}.")


def on_click(event):
    if event.inaxes is not ax:
        tooltip.set_visible(False)
        fig.canvas.draw_idle()
        return

    best_dist = float('inf')
    best_node = None
    for entry in plotted_nodes:
        x, y = entry[0], entry[1]
        d = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5
        if d < best_dist:
            best_dist = d
            best_node = entry

    if best_node and best_dist < DISTANCE_THRESHOLD:
        x, y, q, r, ntype, nid, ndata = best_node

        if ntype in FERRY_TYPES:
            tooltip.set_visible(False)
            _last_clicked[0] = None

            if _first[0] is None:
                _first[0] = (nid, x, y)
                _highlight_a[0], = ax.plot(x, y, marker='o', color='white', markersize=14,
                                           markeredgecolor='#ff6600', markeredgewidth=2,
                                           linestyle='None', zorder=4)
                fl = ndata.get('ferry_link')
                linked_to = fl.get('to') if isinstance(fl, dict) else None
                status_text.set_text(
                    f"Selected: {nid}  (linked to: {linked_to})  |  Click second ferry to link  |  same node = cancel"
                )
                fig.canvas.draw_idle()

            elif _first[0][0] == nid:
                _clear_first()
                status_text.set_text(IDLE_MSG)
                fig.canvas.draw_idle()

            else:
                nid_a, xa, ya = _first[0]
                nid_b = nid

                _highlight_b[0], = ax.plot(x, y, marker='o', color='white', markersize=14,
                                           markeredgecolor='#ff6600', markeredgewidth=2,
                                           linestyle='None', zorder=4)
                fig.canvas.draw_idle()

                cost = open_cost_dialog(nid_a, nid_b)

                if _highlight_b[0] is not None:
                    _highlight_b[0].remove()
                    _highlight_b[0] = None

                if cost is not None:
                    apply_link(nid_a, nid_b, cost)
                    draw_ferry_links()
                    status_text.set_text(f"Linked {nid_a} ↔ {nid_b} ({cost} ECU)  |  Click next ferry or q to save")
                else:
                    status_text.set_text(IDLE_MSG)

                _clear_first()
                fig.canvas.draw_idle()
            return

        # Non-ferry: cancel selection, show tooltip
        if _first[0] is not None:
            _clear_first()
            status_text.set_text(IDLE_MSG)

        if _last_clicked[0] == nid and tooltip.get_visible():
            tooltip.set_visible(False)
            _last_clicked[0] = None
        else:
            fl = ndata.get('ferry_link')
            fl_str = f"\nFerry link: {fl}" if fl else ""
            obs = []
            for n_id, conn in ndata.get("neighbors", {}).items():
                if conn.get("river"):
                    obs.append(f" -> {n_id}: River ({conn.get('river_name')})")
                elif conn.get("lake"):
                    obs.append(f" -> {n_id}: Lake ({conn.get('lake_name')})")
            obs_str = "\n".join(obs) if obs else " None"
            tooltip.set_text(f"ID: {nid} ({ntype}){fl_str}\nq={q}, r={r}\nObstacles:\n{obs_str}")
            tooltip.xy = (x, y)
            tooltip.set_visible(True)
            _last_clicked[0] = nid
    else:
        if _first[0] is not None:
            _clear_first()
            status_text.set_text(IDLE_MSG)
        tooltip.set_visible(False)
        _last_clicked[0] = None

    fig.canvas.draw_idle()


def on_key(event):
    if event.key == 'q':
        save_changes()
        plt.close()
    elif event.key == 'escape':
        if _first[0] is not None:
            _clear_first()
            status_text.set_text(IDLE_MSG)
            fig.canvas.draw_idle()
        else:
            plt.close()


fig.canvas.mpl_connect('button_press_event', on_click)
fig.canvas.mpl_connect('key_press_event', on_key)
print("Ferry Linker active. Click two ferry nodes to link them. q = save & quit, Esc = cancel selection or quit.")
plt.show()
