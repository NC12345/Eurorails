import cv2
import json
import os

# --- CALIBRATION CONFIGURATION ---
# Base structural measurements verified from your map analysis
START_X = 126
START_Y = 78
DELTA_X = 35    # Horizontal pixel column step
DELTA_Y = 27   # Vertical pixel row step

# Keymapping definitions based on your updated prompt specifications
KEY_MAPPING = {
    '1': {'type': 'space_sea', 'color': (0, 0, 0), 'label': 'Void/Sea'},       # Black (skips pathfinding edge generation)
    '2': {'type': 'clear',     'color': (0, 255, 0), 'label': 'Clear'},       # Green (ECU 1M base cost)
    '3': {'type': 'mountain',  'color': (0, 255, 255), 'label': 'Mountain'},  # Yellow (ECU 2M base cost)
    '4': {'type': 'alpine',    'color': (0, 0, 255), 'label': 'Alpine'},      # Red (ECU 5M base cost)
    '5': {'type': 'small_city',  'color': (255, 255, 0), 'label': 'Small City'},   # Cyan
    '6': {'type': 'medium_city', 'color': (255, 165, 0), 'label': 'Medium City'},  # Orange
    '7': {'type': 'large_city',  'color': (255, 0, 255), 'label': 'Large City'},   # Magenta
    '8': {'type': 'ferry',       'color': (255, 200, 0), 'label': 'Ferry'}          # Teal
}

# Arrow key codes from cv2.waitKeyEx — macOS
ARROW_UP    = 63232
ARROW_DOWN  = 63233
ARROW_LEFT  = 63234
ARROW_RIGHT = 63235


def calculate_pixel_coords(row, col):
    """
    Calculates true pixel centers handling the staggered flat-topped triangular lattice.
    Odd rows slide left by 0.5 horizontal column steps.
    """
    precise_y = START_Y + (float(row) * DELTA_Y)
    
    if row % 2 == 0:
        precise_x = START_X + (float(col) * DELTA_X)
    else:
        # Staggered odd rows offset left by exactly half a column step
        precise_x = START_X + ((float(col) * DELTA_X) - (DELTA_X / 2.0))
        
    # Return rounded integers for OpenCV image matrices
    return int(round(precise_x)), int(round(precise_y))

PROGRESS_FILE = "eurorails_progress.json"
OUTPUT_FILE = "eurorails_keyboard_graph.json"


def save_progress(graph_data, current_row, current_col, history):
    state = {
        "current_row": current_row,
        "current_col": current_col,
        "history": history,
        "graph_data": graph_data,
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(state, f, indent=4)
    print(f"Progress saved to '{PROGRESS_FILE}' at Row {current_row}, Col {current_col} ({len(graph_data)} nodes).")


def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return None
    with open(PROGRESS_FILE, "r") as f:
        return json.load(f)


def main():
    # Load your aligned perspective map image
    img_path = "assets/Eurorails Map Fixed.jpg"
    if not os.path.exists(img_path):
        print(f"Error: Target map file '{img_path}' not found in local workspace.")
        return

    base_image = cv2.imread(img_path)
    display_layer = base_image.copy()

    # Attempt to resume from saved progress
    saved = load_progress()
    if saved:
        graph_data = saved["graph_data"]
        current_row = saved["current_row"]
        current_col = saved["current_col"]
        history = [tuple(entry) for entry in saved["history"]]
        # Redraw all previously plotted nodes onto the display layer
        for node in graph_data.values():
            cfg = next(item for item in KEY_MAPPING.values() if item["type"] == node["type"])
            cv2.circle(display_layer, (node["pixel_x"], node["pixel_y"]), 3, cfg["color"], -1)
        print(f"=== Resumed from '{PROGRESS_FILE}': {len(graph_data)} nodes loaded, starting at Row {current_row}, Col {current_col} ===")
    else:
        graph_data = {}
        current_row = 0
        current_col = 0
        history = []
        print("=== Eurorails Keyboard Mapping Engine Active (new session) ===")

    print("Commands: [1] Void/Sea | [2] Clear | [3] Mountain | [4] Alpine | [5] Small City | [6] Medium City | [7] Large City")
    print("Controls: [Arrow Keys] Nudge Reticle | [Backspace] Undo Last Node | [Q] Save & Quit | [Esc] Force Quit (no save)")
    print("----------------------------------------------------------------")

    # Active reticle position — initialized to math baseline, mutated by arrow nudges
    active_pixel_x, active_pixel_y = calculate_pixel_coords(current_row, current_col)

    while True:
        # Redraw display frame and overlay temporary active tracking reticle
        frame = display_layer.copy()
        cv2.circle(frame, (active_pixel_x, active_pixel_y), 5, (255, 105, 180), 2)
        cv2.putText(frame, f"Row: {current_row} Col: {current_col}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 105, 180), 2)

        cv2.imshow("Eurorails Strategy Plotter", frame)

        # Intercept keystroke input
        key = cv2.waitKeyEx(0)
        char_key = chr(key) if 32 <= key < 127 else ""

        if key == ARROW_UP:
            active_pixel_y -= 1
        elif key == ARROW_DOWN:
            active_pixel_y += 1
        elif key == ARROW_LEFT:
            active_pixel_x -= 1
        elif key == ARROW_RIGHT:
            active_pixel_x += 1

        elif char_key in KEY_MAPPING:
            node_cfg = KEY_MAPPING[char_key]

            # Commit point to graph database using current (possibly nudged) position
            node_key = f"r{current_row}_c{current_col}"
            graph_data[node_key] = {
                "row": current_row,
                "col": current_col,
                "axial_q": current_col if current_row % 2 == 0 else current_col - 0.5,
                "axial_r": current_row,
                "type": node_cfg["type"],
                "pixel_x": active_pixel_x,
                "pixel_y": active_pixel_y
            }

            # Burn permanent validation dot into display layer
            cv2.circle(display_layer, (active_pixel_x, active_pixel_y), 3, node_cfg["color"], -1)

            # Save history state for undo recovery operations
            history.append((current_row, current_col, node_key))

            # Advance to next slot, preserving any nudge offset from the committed point
            current_col += 1
            active_pixel_x += DELTA_X
            # active_pixel_y unchanged — same row

        elif key in (127, 8):  # Delete key (macOS) / Backspace
            if history:
                last_row, last_col, last_key = history.pop()

                # Restore reticle to the exact pixel coords that were saved for this node
                if last_key in graph_data:
                    active_pixel_x = graph_data[last_key]["pixel_x"]
                    active_pixel_y = graph_data[last_key]["pixel_y"]
                    del graph_data[last_key]
                else:
                    active_pixel_x, active_pixel_y = calculate_pixel_coords(last_row, last_col)

                current_row = last_row
                current_col = last_col

                # Redraw full validation history clear of the removed point
                display_layer = base_image.copy()
                for _, node in graph_data.items():
                    cfg = next(item for item in KEY_MAPPING.values() if item["type"] == node["type"])
                    cv2.circle(display_layer, (node["pixel_x"], node["pixel_y"]), 3, cfg["color"], -1)
                print(f"Reverted to Node: Row {current_row}, Col {current_col}")
            else:
                print("History buffer empty. Cannot undo further.")

        elif key == 13:  # Enter: advance to next row
            current_row += 1
            current_col = 0
            active_pixel_x, active_pixel_y = calculate_pixel_coords(current_row, current_col)

        elif key == ord('q') or key == ord('Q'):
            save_progress(graph_data, current_row, current_col, history)
            cv2.destroyAllWindows()
            return

        elif key == 27: # Escape: force quit without saving progress
            print("\nForce quit — progress NOT saved.")
            cv2.destroyAllWindows()
            return

if __name__ == "__main__":
    main()