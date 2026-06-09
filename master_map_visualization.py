import json
import numpy as np
import matplotlib.pyplot as plt

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
        ax.plot(x_graph, y_graph, marker='d', color='#009999', markersize=6, linestyle='None', zorder=2)
    elif node_type == "ferry_small_city":
        ax.plot(x_graph, y_graph, marker='o', color='#00cccc', markersize=5, linestyle='None', zorder=2)
        ax.plot(x_graph, y_graph, marker='o', color='black', markersize=2, linestyle='None', zorder=3)

    plotted_nodes.append((x_graph, y_graph, q, r, node_type, node_id, node_data))

# Dynamic adjustment of layout bounds based on calculated nodes
if x_coords and y_coords:
    ax.set_xlim(min(x_coords) - 1.5, max(x_coords) + 1.5)
    ax.set_ylim(min(y_coords) - 1.5, max(y_coords) + 1.5)

# --- LAYER 2.5: FERRY ROUTE LINES ---
rendered_ferry_pairs = set()
for node_id, node_data in master_map.items():
    fl = node_data.get('ferry_link')
    if not isinstance(fl, dict):
        continue
    partner_id = fl.get('to')
    if not partner_id or partner_id not in master_map:
        continue
    pair_key = "__".join(sorted([node_id, partner_id]))
    if pair_key in rendered_ferry_pairs:
        continue
    rendered_ferry_pairs.add(pair_key)

    q1, r1 = node_data["axial_q"], node_data["axial_r"]
    x1, y1 = q1, -r1 * (np.sqrt(3) / 2)
    q2, r2 = master_map[partner_id]["axial_q"], master_map[partner_id]["axial_r"]
    x2, y2 = q2, -r2 * (np.sqrt(3) / 2)

    ax.plot([x1, x2], [y1, y2], color='#00aa44', linewidth=1.5,
            linestyle='--', alpha=0.8, zorder=1)
    cost = fl.get('cost_ecu', '?')
    ax.text((x1 + x2) / 2, (y1 + y2) / 2, f"{cost} ECU",
            fontsize=7, color='#00aa44', ha='center', va='bottom', zorder=3)

plt.title("Eurorails — Unified Digital Engine Canvas (Master Node & Obstacle Topology)", fontsize=13, fontweight='bold', pad=15)
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
        if _last_clicked[0] == nid and tooltip.get_visible():
            tooltip.set_visible(False)
            _last_clicked[0] = None
        else:
            # Construct a details output including localized network parameters
            obs_details = []
            for n_id, conn in ndata.get("neighbors", {}).items():
                if conn.get("river"):
                    obs_details.append(f" -> {n_id}: River ({conn.get('river_name')})")
                elif conn.get("lake"):
                    obs_details.append(f" -> {n_id}: Lake ({conn.get('lake_name')})")
                    
            obs_string = "\n".join(obs_details) if obs_details else " No adjacent river/lake blocks"
            
            city_types = {"small_city", "medium_city", "large_city"}
            city_line = f"\nCity: {ndata.get('city_name')}" if ntype in city_types else ""
            label_text = f"ID: {nid} ({ntype}){city_line}\nq={q}, r={r}\n\nObstacles:\n{obs_string}"
            tooltip.set_text(label_text)
            tooltip.xy = (x, y)
            tooltip.set_visible(True)
            _last_clicked[0] = nid
    else:
        tooltip.set_visible(False)
        _last_clicked[0] = None

    fig.canvas.draw_idle()

fig.canvas.mpl_connect('button_press_event', on_click)
print("🗺️  Map Visualizer Active. Click nodes directly to review layout attributes and connected topological obstacles.")
plt.show()