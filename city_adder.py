import json
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import tkinter as tk

matplotlib.rcParams['keymap.quit'] = []  # prevent default q-to-close so we can handle saves

# --- CONFIGURATION CONFIG PASS ---
MASTER_MAP_PATH = "master_map.json"

# Load the comprehensive map database
try:
    with open(MASTER_MAP_PATH, 'r') as f:
        master_map = json.load(f)
    print(f"📖 Successfully loaded master map database containing {len(master_map)} nodes.")
except FileNotFoundError:
    print(f"Error: Unified map file '{MASTER_MAP_PATH}' was not found. Please run your merge script first.")
    master_map = {}

# Setup plotting canvas
fig, ax = plt.subplots(figsize=(14, 10))
ax.set_aspect('equal')
ax.set_facecolor('#f0f5fa')  # Light blue background matching sea layout aesthetic

# Analytics track arrays for automatic scaling pass
x_coords = []
y_coords = []
plotted_nodes = []
rendered_edges = set()

# --- LAYER 1: RENDER NATURAL OBSTACLE EDGES (RIVERS & LAKES) ---
for node_id, node_data in master_map.items():
    q1 = node_data["axial_q"]
    r1 = node_data["axial_r"]

    # Calculate grid projection math
    x1 = q1
    y1 = -r1 * (np.sqrt(3) / 2)

    neighbors = node_data.get("neighbors", {})
    for neighbor_id, connection in neighbors.items():
        # Prevent rendering duplicate overlaps by checking a unified canonical signature
        edge_signature = "__".join(sorted([node_id, neighbor_id]))
        if edge_signature in rendered_edges:
            continue

        # Ensure the destination node actually exists in our grid configuration
        if neighbor_id in master_map:
            is_river = connection.get("river", False)
            is_lake = connection.get("lake", False)

            if is_river or is_lake:
                # Track this structural link index
                rendered_edges.add(edge_signature)

                # Retrieve coordinates of neighbor node
                q2 = master_map[neighbor_id]["axial_q"]
                r2 = master_map[neighbor_id]["axial_r"]
                x2 = q2
                y2 = -r2 * (np.sqrt(3) / 2)

                # Math projection to draw intermediate hex wall boundaries perpendicular to node links
                xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
                dx, dy = x2 - x1, y2 - y1
                L = (dx**2 + dy**2) ** 0.5

                # Get normal vector parameters
                px, py = -dy / L, dx / L
                half_hex_wall = (1 / np.sqrt(3)) / 2

                # Determine color and profile specs matching original configurations
                color = '#002266' if is_lake else '#0066cc'
                linewidth = 3.0

                ax.plot(
                    [xm + px * half_hex_wall, xm - px * half_hex_wall],
                    [ym + py * half_hex_wall, ym - py * half_hex_wall],
                    color=color, linewidth=linewidth, alpha=0.8, zorder=1
                )

# --- LAYER 2: PROCESS GRAPH LANDMARK NODES ---
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

    # Custom rendering rules per requirement specifications (Using zorder=2 to sit cleanly over hex walls)
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
        ax.plot(x_graph, y_graph, marker='d', color='#009999', markersize=4, linestyle='None', zorder=2)
    elif node_type == "ferry_small_city":
        ax.plot(x_graph, y_graph, marker='o', color='#00cccc', markersize=5, linestyle='None', zorder=2)
        ax.plot(x_graph, y_graph, marker='o', color='black', markersize=2, linestyle='None', zorder=3)

    plotted_nodes.append((x_graph, y_graph, q, r, node_type, node_id, node_data))

# Dynamic adjustment of layout bounds based on calculated nodes
if x_coords and y_coords:
    ax.set_xlim(min(x_coords) - 1.5, max(x_coords) + 1.5)
    ax.set_ylim(min(y_coords) - 1.5, max(y_coords) + 1.5)

plt.title("Eurorails — City Name Editor", fontsize=13, fontweight='bold', pad=15)
ax.axis('off')
plt.tight_layout()

# --- LAYER 3: INTERACTIVE TOOLTIP SELECTION COMPONENT ---
tooltip = ax.annotate(
    "", xy=(0, 0), xytext=(10, 10),
    textcoords="offset points",
    bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="gray", alpha=0.9),
    fontsize=9, visible=False, zorder=3
)
_last_clicked = [None]

IDLE_MSG = "Click a city to name it  |  q = save & quit  |  Esc = quit without saving"
status_text = ax.text(
    0.01, 0.99, IDLE_MSG,
    transform=ax.transAxes, va='top', ha='left',
    fontsize=9, color='#333333', zorder=5,
    bbox=dict(boxstyle='round,pad=0.4', fc='white', ec='gray', alpha=0.85)
)

CITY_TYPES = {'small_city', 'medium_city', 'large_city', 'ferry_small_city'}

# --- EDITING STATE ---
_selected = [None]        # node_id of city being edited, or None
_highlight = [None]       # highlight artist over selected city
pending_changes = {}      # node_id → city_name confirmed or in-progress


def _clear_selection():
    _selected[0] = None
    if _highlight[0] is not None:
        _highlight[0].remove()
        _highlight[0] = None


def open_city_editor(nid, existing_name):
    root = fig.canvas.manager.window  # TkAgg Tk root

    dialog = tk.Toplevel(root)
    dialog.title("Name City")
    dialog.resizable(False, False)

    ntype = master_map[nid].get('type', '')
    tk.Label(dialog, text=f"{nid}  ({ntype})", font=("Helvetica", 11)).pack(padx=16, pady=(12, 4))

    entry = tk.Entry(dialog, width=28, font=("Helvetica", 12))
    entry.insert(0, existing_name)
    entry.select_range(0, tk.END)
    entry.pack(padx=16, pady=(0, 12))
    entry.focus_set()

    def _save_and_close(event=None):
        pending_changes[nid] = entry.get().strip()
        dialog.destroy()

    def _cancel(event=None):
        dialog.destroy()

    def _save_all_and_quit(event=None):
        pending_changes[nid] = entry.get().strip()
        dialog.destroy()   # destroy before plt.close() so wait_window unwinds cleanly
        save_changes()
        plt.close()

    entry.bind("<Return>", _save_and_close)
    entry.bind("<Escape>", _cancel)
    entry.bind("<KeyPress-q>", _save_all_and_quit)

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=(0, 12))
    tk.Button(btn_frame, text="Save",   command=_save_and_close, width=8).pack(side=tk.LEFT, padx=6)
    tk.Button(btn_frame, text="Cancel", command=_cancel,         width=8).pack(side=tk.LEFT, padx=6)

    dialog.wait_window()  # safe: TkAgg shares Tk event loop with matplotlib


def save_changes():
    for node_id, name in pending_changes.items():
        master_map[node_id]['city_name'] = name
    with open(MASTER_MAP_PATH, 'w') as f:
        json.dump(master_map, f, indent=2)
    print(f"Saved {len(pending_changes)} city name(s) to {MASTER_MAP_PATH}.")


def on_click(event):
    if event.inaxes is not ax:
        tooltip.set_visible(False)
        fig.canvas.draw_idle()
        return

    # Find nearest plotted node map match
    best_dist = float('inf')
    best_node = None
    for (x, y, q, r, ntype, nid, ndata) in plotted_nodes:
        d = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5
        if d < best_dist:
            best_dist = d
            best_node = (x, y, q, r, ntype, nid, ndata)

    DISTANCE_THRESHOLD = 0.4
    if best_node and best_dist < DISTANCE_THRESHOLD:
        x, y, q, r, ntype, nid, ndata = best_node

        if ntype in CITY_TYPES:
            _clear_selection()
            tooltip.set_visible(False)
            _last_clicked[0] = None
            _selected[0] = nid
            existing = pending_changes.get(nid) or ndata.get('city_name') or ''
            _highlight[0], = ax.plot(x, y, marker='o', color='white', markersize=14,
                                     markeredgecolor='red', markeredgewidth=2,
                                     linestyle='None', zorder=4)
            fig.canvas.draw_idle()            # render highlight before dialog opens
            open_city_editor(nid, existing)   # blocks until dialog closes
            _clear_selection()                # remove highlight after dialog
            status_text.set_text(IDLE_MSG)
            fig.canvas.draw_idle()
            return

        # Non-city node: clear any active edit and show tooltip
        if _selected[0] is not None:
            _clear_selection()
            status_text.set_text(IDLE_MSG)

        if _last_clicked[0] == nid and tooltip.get_visible():
            tooltip.set_visible(False)
            _last_clicked[0] = None
        else:
            obs_details = []
            for n_id, conn in ndata.get("neighbors", {}).items():
                if conn.get("river"):
                    obs_details.append(f" -> {n_id}: River ({conn.get('river_name')})")
                elif conn.get("lake"):
                    obs_details.append(f" -> {n_id}: Lake ({conn.get('lake_name')})")

            obs_string = "\n".join(obs_details) if obs_details else " No adjacent river/lake blocks"
            label_text = f"ID: {nid} ({ntype})\nq={q}, r={r}\n\nObstacles:\n{obs_string}"
            tooltip.set_text(label_text)
            tooltip.xy = (x, y)
            tooltip.set_visible(True)
            _last_clicked[0] = nid
    else:
        if _selected[0] is not None:
            _clear_selection()
            status_text.set_text(IDLE_MSG)
        tooltip.set_visible(False)
        _last_clicked[0] = None

    fig.canvas.draw_idle()


def on_key(event):
    key = event.key
    if key == 'q':
        save_changes()
        plt.close()
    elif key == 'escape':
        plt.close()


fig.canvas.mpl_connect('button_press_event', on_click)
fig.canvas.mpl_connect('key_press_event', on_key)
print("🗺️  City Name Editor Active. Click a city node to name it. q = save & quit, Esc = quit without saving.")
plt.show()
