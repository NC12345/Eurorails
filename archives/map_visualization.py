import json
import numpy as np
import matplotlib.pyplot as plt

# Load core graph node data
try:
    with open('map_rough_draft.json', 'r') as f:
        graph_nodes = json.load(f)
except FileNotFoundError:
    graph_nodes = {
        "r0_c28": {"axial_q": 28, "axial_r": 0, "type": "clear"},
        "r1_c28": {"axial_q": 27.5, "axial_r": 1, "type": "mountain"},
        "r2_c29": {"axial_q": 29, "axial_r": 2, "type": "alpine"},
        "r3_c29": {"axial_q": 28.5, "axial_r": 3, "type": "small_city"},
        "r4_c30": {"axial_q": 30, "axial_r": 4, "type": "medium_city"},
        "r5_c30": {"axial_q": 29.5, "axial_r": 5, "type": "large_city"},
        "r6_c31": {"axial_q": 31, "axial_r": 6, "type": "ferry"}
    }

# Load optional static vector border layers
borders_data = None
try:
    with open('map_borders.json', 'r') as f:
        borders_data = json.load(f)
except FileNotFoundError:
    print("Warning: 'map_borders.json' not found. Visualization will render without background water borders.")

# Setup plotting canvas
fig, ax = plt.subplots(figsize=(14, 10))
ax.set_aspect('equal')
ax.set_facecolor('#f0f5fa') # Light blue background matching sea layout aesthetic

# Track limits to auto-scale the pure geometric canvas
x_coords = []
y_coords = []
plotted_nodes = []

# --- LAYER 1: RENDER BACKGROUND WATER BORDERS (IF AVAILABLE) ---
if borders_data and "water_borders" in borders_data:
    for segment in borders_data["water_borders"]:
        coords = segment["coordinates"]
        xs = [pt[0] for pt in coords]
        ys = [pt[1] for pt in coords]
        ax.plot(xs, ys, color='#0066cc', linewidth=2.5, solid_capstyle='round', zorder=1)

# --- LAYER 2: PROCESS INTERACTIVE GRAPH NODES ---
for node_id, node in graph_nodes.items():
    node_type = node.get("type")
    
    if node_type == "space_sea" or not node_type:
        continue
        
    q = node["axial_q"]
    r = node["axial_r"]
    
    x_graph = q
    y_graph = -r * (np.sqrt(3) / 2)
    
    x_coords.append(x_graph)
    y_coords.append(y_graph)
    
    # Custom rendering rules per requirement specifications (Using zorder=2 to sit cleanly over borders)
    if node_type == "clear":
        ax.plot(x_graph, y_graph, 'ko', markersize=2, zorder=2)
    elif node_type == "mountain":
        ax.plot(x_graph, y_graph, marker='^', color='#e6b800', markersize=2, linestyle='None', zorder=2)
    elif node_type == "alpine":
        ax.plot(x_graph, y_graph, marker='^', color='#ff3333', markersize=2, 
                markeredgecolor='red', markeredgewidth=1.5, linestyle='None', zorder=2)
    elif node_type == "small_city":
        ax.plot(x_graph, y_graph, marker='o', color='#00cccc', markersize=5, linestyle='None', zorder=2)
    elif node_type == "medium_city":
        ax.plot(x_graph, y_graph, marker='s', color='#ff9900', markersize=5, linestyle='None', zorder=2)
    elif node_type == "large_city":
        ax.plot(x_graph, y_graph, marker='h', color='#cc00cc', markersize=5, linestyle='None', zorder=2)
    elif node_type == "ferry":
        ax.plot(x_graph, y_graph, marker='d', color='#009999', markersize=2, linestyle='None', zorder=2)
    elif node_type == "ferry_small_city":
        ax.plot(x_graph, y_graph, marker='o', color='#00cccc', markersize=5, linestyle='None', zorder=2)
        ax.plot(x_graph, y_graph, marker='o', color='black', markersize=2, linestyle='None', zorder=3)

    plotted_nodes.append((x_graph, y_graph, q, r, node_type, node_id))

# Dynamic adjustment of layout bounds based purely on grid calculations
if x_coords and y_coords:
    ax.set_xlim(min(x_coords) - 2, max(x_coords) + 2)
    ax.set_ylim(min(y_coords) - 2, max(y_coords) + 2)

# Grid lines cleanup for seamless tabletop gaming aesthetic
plt.title("Eurorails — Digital Lattice Node Map (Pure Axial Topology)", fontsize=14, fontweight='bold', pad=15)
ax.axis('off')
plt.tight_layout()

# Tooltip annotation (hidden until a point is clicked)
tooltip = ax.annotate(
    "", xy=(0, 0), xytext=(10, 10),
    textcoords="offset points",
    bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="gray", alpha=0.9),
    fontsize=9, visible=False, zorder=3
)
_last_clicked = [None]  # mutable container to track toggle state

def on_click(event):
    if event.inaxes is not ax:
        tooltip.set_visible(False)
        fig.canvas.draw_idle()
        return

    # Find nearest plotted node
    best_dist = float('inf')
    best_node = None
    for (x, y, q, r, ntype, nid) in plotted_nodes:
        d = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5
        if d < best_dist:
            best_dist = d
            best_node = (x, y, q, r, ntype, nid)

    THRESHOLD = 0.4
    if best_node and best_dist < THRESHOLD:
        x, y, q, r, ntype, nid = best_node
        if _last_clicked[0] == nid and tooltip.get_visible():
            tooltip.set_visible(False)
            _last_clicked[0] = None
        else:
            tooltip.set_text(f"q={q}, r={r}\n{ntype}\nID: {nid}")
            tooltip.xy = (x, y)
            tooltip.set_visible(True)
            _last_clicked[0] = nid
    else:
        tooltip.set_visible(False)
        _last_clicked[0] = None

    fig.canvas.draw_idle()

fig.canvas.mpl_connect('button_press_event', on_click)
plt.show()