import json
import os
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# CONFIGURATION: Set the active river name here
# ==========================================
ACTIVE_RIVER_NAME = "Sava"
ACTIVE_MODE = "river"  # toggled between "river" and "lake" via SPACE BAR

MAP_DATA_PATH = "map_rough_draft.json"
RIVERS_DATA_PATH = "rivers.json"

# Load core map layout graph node data
try:
    with open(MAP_DATA_PATH, 'r') as f:
        map_raw = json.load(f)
    graph_nodes = map_raw.get("graph_data", map_raw)
except FileNotFoundError:
    print(f"Error: Required baseline layout data '{MAP_DATA_PATH}' not found.")
    graph_nodes = {}

# Load or initialize cumulative rivers state database over multiple runs
rivers_db = {}
if os.path.exists(RIVERS_DATA_PATH):
    try:
        with open(RIVERS_DATA_PATH, 'r') as f:
            rivers_db = json.load(f)
        print(f"💾 Loaded existing river configurations from {RIVERS_DATA_PATH}")
    except json.JSONDecodeError:
        print(f"Warning: {RIVERS_DATA_PATH} was corrupt. Re-initializing empty structure.")

# Migrate old schema: "river_name" -> "name" + "type"
for _, _conns in rivers_db.items():
    for _conn in _conns:
        if "river_name" in _conn and "name" not in _conn:
            _conn["name"] = _conn.pop("river_name")
            _conn.setdefault("type", "river")

def get_neighbor_key(r, c, dq, dr):
    n_r = r + dr
    if dr == 0:
        n_c = c + dq
    elif r % 2 == 0:
        if (dq, dr) == (0, 1):   n_c = c + 1   # Down-Right
        if (dq, dr) == (-1, 1):  n_c = c       # Down-Left
        if (dq, dr) == (0, -1):  n_c = c       # Up-Left
        if (dq, dr) == (1, -1):  n_c = c + 1   # Up-Right
    else:
        if (dq, dr) == (0, 1):   n_c = c       # Down-Right
        if (dq, dr) == (-1, 1):  n_c = c - 1   # Down-Left
        if (dq, dr) == (0, -1):  n_c = c - 1   # Up-Left
        if (dq, dr) == (1, -1):  n_c = c       # Up-Right
    return f"r{n_r}_c{n_c}"

# Pre-calculate spatial layout geometries for analytical calculation 
node_spatial = {}
x_coords, y_coords = [], []

for nid, node in graph_nodes.items():
    if node.get("type") == "space_sea" or not node.get("type"):
        continue
    q = node["axial_q"]
    r = node["axial_r"]
    x = q
    y = -r * (np.sqrt(3) / 2)
    node_spatial[nid] = {"x": x, "y": y, "r": r, "c": node["col"], "type": node["type"]}
    x_coords.append(x)
    y_coords.append(y)

# Generate a canonical master edge checklist structure to match edge clicks 
edges_checklist = {}
DIRECTIONS = [
    {"dq": 1, "dr": 0}, {"dq": 0, "dr": 1}, {"dq": -1, "dr": 1},
    {"dq": -1, "dr": 0}, {"dq": 0, "dr": -1}, {"dq": 1, "dr": -1}
]

for nid, sdata in node_spatial.items():
    for d in DIRECTIONS:
        neigh_id = get_neighbor_key(sdata["r"], sdata["c"], d["dq"], d["dr"])
        if neigh_id in node_spatial:
            canonical_key = "__".join(sorted([nid, neigh_id]))
            if canonical_key not in edges_checklist:
                mx = (sdata["x"] + node_spatial[neigh_id]["x"]) / 2
                my = (sdata["y"] + node_spatial[neigh_id]["y"]) / 2
                edges_checklist[canonical_key] = {
                    "node_a": nid, "node_b": neigh_id, "mid_x": mx, "mid_y": my
                }

_should_save = [True]  # set to False when q or Esc handles the exit

fig, ax = plt.subplots(figsize=(14, 10))
ax.set_aspect('equal')
ax.set_facecolor('#f0f5fa')

river_lines_drawn = {}

def update_visualization():
    # Clear visual lines safely without resetting global plot callbacks
    for l_obj in list(river_lines_drawn.values()):
        l_obj.remove()
    river_lines_drawn.clear()
    
    # Redraw active edge links matching entries in rivers_db structure
    seen_edges = set()
    for n_src, connections in rivers_db.items():
        for conn in connections:
            n_dst = conn["neighbor"]
            r_type = conn.get("type", "river")
            edge_signature = "__".join(sorted([n_src, n_dst]))

            if edge_signature not in seen_edges and n_src in node_spatial and n_dst in node_spatial:
                seen_edges.add(edge_signature)
                x1, y1 = node_spatial[n_src]["x"], node_spatial[n_src]["y"]
                x2, y2 = node_spatial[n_dst]["x"], node_spatial[n_dst]["y"]
                xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
                dx, dy = x2 - x1, y2 - y1
                L = (dx**2 + dy**2) ** 0.5
                px, py = -dy / L, dx / L
                half_s = (1 / np.sqrt(3)) / 2
                color = '#002266' if r_type == "lake" else '#0066cc'
                lw = 6 if r_type == "lake" else 4
                line, = ax.plot(
                    [xm + px * half_s, xm - px * half_s],
                    [ym + py * half_s, ym - py * half_s],
                    color=color, linewidth=lw, alpha=0.8, zorder=1
                )
                river_lines_drawn[edge_signature] = line

def on_canvas_click(event):
    if event.inaxes is not ax:
        return
        
    closest_edge = None
    min_dist = float('inf')
    
    for e_key, edata in edges_checklist.items():
        dist = ((event.xdata - edata["mid_x"])**2 + (event.ydata - edata["mid_y"])**2)**0.5
        if dist < min_dist:
            min_dist = dist
            closest_edge = e_key
            
    EDGE_MATCH_THRESHOLD = 0.25
    if closest_edge and min_dist < EDGE_MATCH_THRESHOLD:
        node_a = edges_checklist[closest_edge]["node_a"]
        node_b = edges_checklist[closest_edge]["node_b"]
        
        # Find existing entry for this edge under the active river name
        existing_entry_a = None
        existing_entry_b = None
        if node_a in rivers_db:
            for entry in rivers_db[node_a]:
                if entry["neighbor"] == node_b and entry.get("name") == ACTIVE_RIVER_NAME:
                    existing_entry_a = entry
                    break
        if node_b in rivers_db:
            for entry in rivers_db[node_b]:
                if entry["neighbor"] == node_a and entry.get("name") == ACTIVE_RIVER_NAME:
                    existing_entry_b = entry
                    break

        if existing_entry_a is not None:
            if existing_entry_a.get("type") == ACTIVE_MODE:
                # Same type — remove both directional entries
                rivers_db[node_a].remove(existing_entry_a)
                if existing_entry_b is not None:
                    rivers_db[node_b].remove(existing_entry_b)
                print(f"🛑 Removed link: {node_a} <-> {node_b} ({ACTIVE_RIVER_NAME}, {ACTIVE_MODE})")
            else:
                # Different type — overwrite both directional entries
                existing_entry_a["type"] = ACTIVE_MODE
                if existing_entry_b is not None:
                    existing_entry_b["type"] = ACTIVE_MODE
                print(f"🔄 Updated link: {node_a} <-> {node_b} ({ACTIVE_RIVER_NAME} → {ACTIVE_MODE})")
        else:
            # No existing entry — add symmetrically
            if node_a not in rivers_db: rivers_db[node_a] = []
            if node_b not in rivers_db: rivers_db[node_b] = []
            rivers_db[node_a].append({"neighbor": node_b, "name": ACTIVE_RIVER_NAME, "type": ACTIVE_MODE})
            rivers_db[node_b].append({"neighbor": node_a, "name": ACTIVE_RIVER_NAME, "type": ACTIVE_MODE})
            print(f"✅ Tagged link: {node_a} <-> {node_b} ({ACTIVE_RIVER_NAME}, {ACTIVE_MODE})")
            
        # Clean up empty records from structure database footprint
        if node_a in rivers_db and not rivers_db[node_a]: del rivers_db[node_a]
        if node_b in rivers_db and not rivers_db[node_b]: del rivers_db[node_b]
            
        update_visualization()
        fig.canvas.draw_idle()

# Draw static node markers layout mapping configurations
for nid, node in node_spatial.items():
    ntype = node["type"]
    if ntype == "clear": ax.plot(node["x"], node["y"], 'ko', markersize=2, zorder=2)
    elif ntype == "mountain": ax.plot(node["x"], node["y"], '^', color='#e6b800', markersize=3, zorder=2)
    elif ntype == "alpine": ax.plot(node["x"], node["y"], '^', color='#ff3333', markersize=4, zorder=2)
    elif ntype == "small_city": ax.plot(node["x"], node["y"], 'o', color='#00cccc', markersize=5, zorder=2)
    elif ntype == "medium_city": ax.plot(node["x"], node["y"], 's', color='#ff9900', markersize=5, zorder=2)
    elif ntype == "large_city": ax.plot(node["x"], node["y"], 'h', color='#cc00cc', markersize=6, zorder=2)
    elif ntype == "ferry": ax.plot(node["x"], node["y"], 'd', color='#009999', markersize=4, zorder=2)

if x_coords and y_coords:
    ax.set_xlim(min(x_coords) - 1, max(x_coords) + 1)
    ax.set_ylim(min(y_coords) - 1, max(y_coords) + 1)

def update_title():
    mode_label = "RIVER" if ACTIVE_MODE == "river" else "LAKE"
    plt.title(
        f"Eurorails Tagger — [{ACTIVE_RIVER_NAME}] | Mode: {mode_label}",
        fontsize=12, fontweight='bold'
    )

update_title()
ax.axis('off')
plt.tight_layout()

# Run preliminary structural layout validation refresh pass
update_visualization()

def on_key_press(event):
    global ACTIVE_MODE
    if event.key == ' ':
        ACTIVE_MODE = "lake" if ACTIVE_MODE == "river" else "river"
        update_title()
        fig.canvas.draw_idle()
        print(f"🔀 Mode switched to: {ACTIVE_MODE.upper()}")
    elif event.key == 'q':
        _should_save[0] = False
        with open(RIVERS_DATA_PATH, 'w') as f:
            json.dump(rivers_db, f, indent=4)
        print(f"💾 Saved to '{RIVERS_DATA_PATH}'. Closing...")
        plt.close(fig)
    elif event.key == 'escape':
        _should_save[0] = False
        print("🚪 Exiting without saving.")
        plt.close(fig)

# Connect interface execution triggers
fig.canvas.mpl_connect('button_press_event', on_canvas_click)
fig.canvas.mpl_connect('key_press_event', on_key_press)

print(f"\n🚀 Interface Active! Click intermediate edges to register the river: {ACTIVE_RIVER_NAME}")
print("⌨️  Press Q to save and close. Press Esc to exit without saving.")
plt.show()

if _should_save[0]:
    with open(RIVERS_DATA_PATH, 'w') as f:
        json.dump(rivers_db, f, indent=4)
    print(f"💾 File updates successfully written to storage index: '{RIVERS_DATA_PATH}'")