import json
import math
import numpy as np
import matplotlib.pyplot as plt

with open('map_rough_draft.json', 'r') as f:
    data = json.load(f)

graph_nodes = data['graph_data']

fig, ax = plt.subplots(figsize=(14, 10))
ax.set_aspect('equal')
ax.set_facecolor('#f0f5fa')

R = 1 / math.sqrt(3)
SQRT3_OVER_2 = math.sqrt(3) / 2

DIRECTIONS = [
    ((1,  0),  5, 0),  # Right: line between Bottom-Right (5) and Top-Right (0)
    ((0,  1),  4, 5),  # Down-Right: line between Bottom (4) and Bottom-Right (5)
    ((-1, 1),  3, 4),  # Down-Left: line between Bottom-Left (3) and Bottom (4)
    ((-1, 0),  2, 3),  # Left: line between Top-Left (2) and Bottom-Left (3)
    ((0, -1),  1, 2),  # Up-Left: line between Top (1) and Top-Left (2)
    ((1, -1),  0, 1),  # Up-Right: line between Top-Right (0) and Top (1)
]


def hex_vertex(x, y, k):
    angle = k * math.pi / 3 + math.pi / 6
    return (x + R * math.cos(angle), y + R * math.sin(angle))


def neighbor_key(r, c, dq, dr):
    n_r = r + dr
    
    # 1. Direct horizontal movement (Row parity doesn't change)
    if dr == 0:
        n_c = c + dq
        
    # 2. Diagonal movement starting from an EVEN row
    elif r % 2 == 0:
        if (dq, dr) == (0, 1):   n_c = c + 1  # Down-Right
        if (dq, dr) == (-1, 1):  n_c = c      # Down-Left
        if (dq, dr) == (0, -1):  n_c = c      # Up-Left
        if (dq, dr) == (1, -1):  n_c = c + 1  # Up-Right
        
    # 3. Diagonal movement starting from an ODD row
    else:
        if (dq, dr) == (0, 1):   n_c = c      # Down-Right
        if (dq, dr) == (-1, 1):  n_c = c - 1  # Down-Left
        if (dq, dr) == (0, -1):  n_c = c - 1  # Up-Left
        if (dq, dr) == (1, -1):  n_c = c      # Up-Right
        
    return f"r{n_r}_c{n_c}"


x_coords = []
y_coords = []

for node_id, node in graph_nodes.items():
    node_type = node.get('type')
    if node_type == 'space_sea' or not node_type:
        continue

    q = node['axial_q']
    c = node['col']
    r = node['axial_r']

    x = q
    y = -r * SQRT3_OVER_2

    x_coords.append(x)
    y_coords.append(y)

    if node_type == 'clear':
        ax.plot(x, y, 'ko', markersize=2)
    elif node_type == 'mountain':
        ax.plot(x, y, marker='^', color='#e6b800', markersize=2, linestyle='None')
    elif node_type == 'alpine':
        ax.plot(x, y, marker='^', color='#ff3333', markersize=2,
                markeredgecolor='red', markeredgewidth=1.5, linestyle='None')
    elif node_type == 'small_city':
        ax.plot(x, y, marker='o', color='#00cccc', markersize=5, linestyle='None')
    elif node_type == 'medium_city':
        ax.plot(x, y, marker='s', color='#ff9900', markersize=5, linestyle='None')
    elif node_type == 'large_city':
        ax.plot(x, y, marker='h', color='#cc00cc', markersize=5, linestyle='None')
    elif node_type == 'ferry':
        ax.plot(x, y, marker='d', color='#009999', markersize=2, linestyle='None')
    elif node_type == 'ferry_small_city':
        ax.plot(x, y, marker='o', color='#00cccc', markersize=5, linestyle='None')
        ax.plot(x, y, marker='o', color='black', markersize=2, linestyle='None')

    for (dq, dr), vi, vj in DIRECTIONS:
        key = neighbor_key(r, c, dq, dr)
        if key not in graph_nodes:
            ax.plot(
                [hex_vertex(x, y, vi)[0], hex_vertex(x, y, vj)[0]],
                [hex_vertex(x, y, vi)[1], hex_vertex(x, y, vj)[1]],
                color='#0066cc', linewidth=2.5, solid_capstyle='round'
            )

if x_coords and y_coords:
    ax.set_xlim(min(x_coords) - 2, max(x_coords) + 2)
    ax.set_ylim(min(y_coords) - 2, max(y_coords) + 2)

plt.title("Eurorails — Coastline Map", fontsize=14, fontweight='bold', pad=15)
ax.axis('off')
plt.tight_layout()
plt.show()
