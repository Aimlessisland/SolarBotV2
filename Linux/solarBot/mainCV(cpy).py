import os
import glob
import cv2
import numpy as np
import captureImg  # Automatically saves to ~/solarBot/imgForward

OUTPUT_DIR = "objectDetectTest"
FORWARD_DIR = "imgForward"

# ==========================================================
# CURVE FITTING HELPER
# ==========================================================
def fit_curve_3pts(p1, p2, p3, axis="y_along_x", num_points=60):
    x_pts = np.array([p1[0], p2[0], p3[0]], dtype=np.float64)
    y_pts = np.array([p1[1], p2[1], p3[1]], dtype=np.float64)

    if axis == "y_along_x":
        poly = np.polyfit(x_pts, y_pts, 2)
        x_vals = np.linspace(p1[0], p3[0], num_points)
        y_vals = np.polyval(poly, x_vals)
        pts = np.column_stack((x_vals, y_vals))
    else:
        poly = np.polyfit(y_pts, x_pts, 2)
        y_vals = np.linspace(p1[1], p3[1], num_points)
        x_vals = np.polyval(poly, y_vals)
        pts = np.column_stack((x_vals, y_vals))

    return pts.astype(np.int32).reshape((-1, 1, 2))

# ==========================================================
# PROCESS & TRACE (Digs into imgForward for the latest image)
# ==========================================================
def process_and_trace():
    # Automatically find the latest image inside imgForward
    list_of_images = glob.glob(os.path.join(FORWARD_DIR, "front_*.jpg"))
    if not list_of_images:
        print("Error: No images found in imgForward folder!")
        return None, None

    latest_image_path = max(list_of_images, key=os.path.getmtime)
    print(f"Processing latest image: {latest_image_path}")

    img = cv2.imread(latest_image_path)
    if img is None:
        print("Error: Could not read the image.")
        return None, None

    h, w = img.shape[:2]

    # 1. Canny Edge Detection
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray_img, 100, 200)

    # 2. DEFINE BOUNDARIES 
    cx_ratio = 0.482
    
    left_top = (int(w * 0.305), int(h * 0.165))
    left_mid = (int(w * 0.145), int(h * 0.400))
    left_bot = (int(w * 0.020), int(h * 0.670))
    
    right_top = (int(w * 0.660), int(h * 0.165))
    right_mid = (int(w * 0.820), int(h * 0.400))
    right_bot = (int(w * 0.940), int(h * 0.670))

    brush_mid = (int(w * cx_ratio), int(h * 0.880))

    front_y_base = int(h * 0.165) + 5  
    front_curve_depth = -15            
    
    front_left_mult = 0.300   
    front_right_mult = 0.665  
    
    front_left = (int(w * front_left_mult), front_y_base)
    front_mid  = (int(w * cx_ratio), front_y_base + front_curve_depth)
    front_right = (int(w * front_right_mult), front_y_base)
    
    left_curve = fit_curve_3pts(left_top, left_mid, left_bot, axis="x_along_y")
    right_curve = fit_curve_3pts(right_top, right_mid, right_bot, axis="x_along_y")
    brush_curve = fit_curve_3pts(left_bot, brush_mid, right_bot, axis="y_along_x")
    front_curve = fit_curve_3pts(front_left, front_mid, front_right, axis="y_along_x")

    polygon_points = np.vstack([front_curve, right_curve, brush_curve[::-1], left_curve[::-1]])
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [polygon_points], 255)
    
    masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
    traced_image = cv2.cvtColor(masked_edges, cv2.COLOR_GRAY2BGR)

    def leftTracking():
        cm_calib = np.array([65,   60,   55,   50,   45,   40,   35,   30,   25,   20,   15,   10,   5        ], dtype=float)
        y_calib  = np.array([215.5, 240,  254.5, 280,  300.5, 340,  375,  410,  438,  496,  553,  630,  720      ], dtype=float)
        left_perspective_corrections = {
            65: -10, 60: -11, 55: -12, 50: -13, 45: -14, 40: -16, 35: -20, 30: -20,
            25: -21, 20: -24, 15: -27, 10: -32, 5:  -36
        }
        left_pts = left_curve.reshape(-1, 2)
        left_poly = np.polyfit(left_pts[:, 1], left_pts[:, 0], 2)
        
        print("\n==========================================")
        print("LEFT LINE TRACING")
        print("==========================================")
        detected_points = []
        calibrated_pixels = []
        
        for cm in cm_calib:
            base_y = np.interp(cm, cm_calib[::-1], y_calib[::-1])
            target_y = int(base_y)
            left_x = int(np.polyval(left_poly, target_y))
            
            search_start = max(0, left_x - 30)
            search_end = min(w, max(left_x + 50, w // 2))
            search_window = masked_edges[target_y, search_start:search_end]
            white_pixels = np.where(search_window > 0)[0]
            
            if len(white_pixels) > 0:
                edge_x = int(np.min(white_pixels + search_start))
                raw_px = edge_x - left_x
                correction = left_perspective_corrections.get(int(cm), 0)
                calibrated_px = raw_px + correction
                calibrated_pixels.append(calibrated_px)
                print(f"@ {int(cm):2d}cm = {calibrated_px:+3d}px")
                detected_points.append((edge_x, target_y))
                cv2.circle(traced_image, (edge_x, target_y), 3, (0, 0, 255), -1)
                cv2.line(traced_image, (left_x, target_y), (edge_x, target_y), (0, 0, 255), 1)
                
        if calibrated_pixels:
            print(f"Average Left Offset: {np.mean(calibrated_pixels):+.1f}px")
            
        # RESTORED: Solid line connecting left dots
        if len(detected_points) > 2:
            pts_array = np.array(detected_points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [pts_array], isClosed=False, color=(0, 0, 255), thickness=2)
            
        print("==========================================\n")

    def rightTracking():
        cm_calib = np.array([65,   60,   55,   50,   45,   40,   35,   30,   25,   20,   15,   10,   5        ], dtype=float)
        y_calib  = np.array([215.5, 240,  254.5, 280,  300.5, 340,  375,  410,  438,  496,  553,  630,  720      ], dtype=float)
        perspective_corrections = {
            65: 22, 60: 18, 55: 24, 50: 23, 45: 19, 40: 15, 35: 20, 30: 15,
            25: 12, 20: 6,  15: 4,  10: 0,  5:  0
        }
        right_pts = right_curve.reshape(-1, 2)
        right_poly = np.polyfit(right_pts[:, 1], right_pts[:, 0], 2)
        
        print("\n==========================================")
        print("RIGHT LINE TRACING")
        print("==========================================")
        detected_points = []
        calibrated_pixels = []
        
        for cm in cm_calib:
            base_y = np.interp(cm, cm_calib[::-1], y_calib[::-1])
            target_y = int(base_y)
            right_x = int(np.polyval(right_poly, target_y))
            
            search_start = max(0, min(right_x - 50, w // 2))
            search_end = min(w, right_x + 30)
            search_window = masked_edges[target_y, search_start:search_end]
            white_pixels = np.where(search_window > 0)[0]
            
            if len(white_pixels) > 0:
                edge_x = int(np.max(white_pixels + search_start))
                raw_px = right_x - edge_x
                correction = perspective_corrections.get(int(cm), 0)
                calibrated_px = raw_px + correction
                calibrated_pixels.append(calibrated_px)
                print(f"@ {int(cm):2d}cm = {calibrated_px:+3d}px")
                detected_points.append((edge_x, target_y))
                cv2.circle(traced_image, (edge_x, target_y), 3, (0, 0, 255), -1)
                cv2.line(traced_image, (right_x, target_y), (edge_x, target_y), (0, 0, 255), 1)
                
        if calibrated_pixels:
            print(f"Average Right Offset: {np.mean(calibrated_pixels):+.1f}px")
            
        # RESTORED: Solid line connecting right dots
        if len(detected_points) > 2:
            pts_array = np.array(detected_points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [pts_array], isClosed=False, color=(0, 0, 255), thickness=2)
            
        print("==========================================\n")

    def frontTracking():
        width_steps = np.linspace(10, 60, 25, dtype=int)
        front_pts = front_curve.reshape(-1, 2)
        front_poly = np.polyfit(front_pts[:, 0], front_pts[:, 1], 2)
        brush_pts = brush_curve.reshape(-1, 2)
        brush_poly = np.polyfit(brush_pts[:, 0], brush_pts[:, 1], 2)
        
        x_start_top, x_end_top = front_left[0], front_right[0]
        x_start_bot, x_end_bot = left_bot[0], right_bot[0]
        
        print("\n==========================================")
        print("FRONT LINE TRACING")
        print("==========================================")
        detected_points = []
        
        for width_pos in width_steps:
            tx_top = int(np.interp(width_pos, [0, 71], [x_start_top, x_end_top]))
            tx_bot = int(np.interp(width_pos, [0, 71], [x_start_bot, x_end_bot]))
            top_y = int(np.polyval(front_poly, tx_top))
            bottom_y = int(np.polyval(brush_poly, tx_bot))
            
            y_samples = np.linspace(top_y, bottom_y, max(10, abs(bottom_y - top_y)), dtype=int)
            x_samples = np.linspace(tx_top, tx_bot, len(y_samples), dtype=int)
            
            edge_found = False
            for y, x in zip(y_samples, x_samples):
                if np.any(masked_edges[max(0, y-1):min(h, y+2), max(0, x-3):min(w, x+4)] > 0):
                    detected_points.append((x, y))
                    cv2.circle(traced_image, (x, y), 3, (0, 0, 255), -1)
                    edge_found = True
                    break
                    
        # RESTORED: Solid line connecting front dots
        if len(detected_points) > 2:
            detected_arr = np.array(detected_points, dtype=np.float64)
            poly_tracked = np.polyfit(detected_arr[:, 0], detected_arr[:, 1], 2)
            x_vals = np.linspace(detected_arr[:, 0].min(), detected_arr[:, 0].max(), 60)
            y_vals = np.polyval(poly_tracked, x_vals)
            tracked_curve = np.column_stack((x_vals, y_vals)).astype(np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [tracked_curve], isClosed=False, color=(0, 255, 0), thickness=2)
            
        print("==========================================\n")

    # Run all trackers sequentially
    leftTracking()
    rightTracking()
    frontTracking()

    # Draw boundary boxes (Purple)
    cv2.polylines(traced_image, [left_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [right_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [brush_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [front_curve], isClosed=False, color=(128, 0, 128), thickness=2)

    # ==========================================================
    # RESTORED: HEIGHT & WIDTH DEPTH TICKS
    # ==========================================================
    depth_y_offset = 0  
    cm_calib = np.array([65,   60,   55,   50,   45,   40,   35,   30,   25,   20,   15,   10,   5,    0   ], dtype=float)
    y_calib  = np.array([215.5, 240,  254.5, 280,  300.5, 340,  375,  410,  438,  496,  553,  630,  720,  760  ], dtype=float)
    
    left_pts = left_curve.reshape(-1, 2)
    left_poly = np.polyfit(left_pts[:, 1], left_pts[:, 0], 2)
    right_pts = right_curve.reshape(-1, 2)
    right_poly = np.polyfit(right_pts[:, 1], right_pts[:, 0], 2)
    
    for cm in range(65, -1, -1):
        base_y = np.interp(cm, cm_calib[::-1], y_calib[::-1])
        target_y = int(base_y + depth_y_offset)
        
        is_major = (cm % 5 == 0)
        tick_length = 20 if is_major else 10
        
        left_x = int(np.polyval(left_poly, target_y))
        cv2.line(traced_image, (left_x, target_y), (left_x - tick_length, target_y), (0, 255, 255), 2 if is_major else 1)
        if is_major:
            cv2.putText(traced_image, f"{cm}", (left_x - tick_length - 28, target_y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
            
        right_x = int(np.polyval(right_poly, target_y))
        cv2.line(traced_image, (right_x, target_y), (right_x + tick_length, target_y), (0, 255, 255), 2 if is_major else 1)
        if is_major:
            cv2.putText(traced_image, f"{cm}", (right_x + tick_length + 5, target_y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

    front_pts = front_curve.reshape(-1, 2)
    front_poly = np.polyfit(front_pts[:, 0], front_pts[:, 1], 2)
    x_start, x_end = front_left[0], front_right[0]

    for val in range(0, 72, 5):
        tx = int(np.interp(val, [0, 71], [x_start, x_end]))
        ty = int(np.polyval(front_poly, tx))
        major = (val % 10 == 0 or val == 35)
        t_len = 15 if major else 8
        cv2.line(traced_image, (tx, ty), (tx, ty - t_len), (0, 255, 0), 2 if major else 1)
        if major:
            cv2.putText(traced_image, f"{val}", (tx - 8, ty - t_len - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)

    brush_pts = brush_curve.reshape(-1, 2)
    brush_poly = np.polyfit(brush_pts[:, 0], brush_pts[:, 1], 2)
    brush_x_start, brush_x_end = left_bot[0], right_bot[0]

    for val in range(0, 72, 5):
        tx = int(np.interp(val, [0, 71], [brush_x_start, brush_x_end]))
        ty = int(np.polyval(brush_poly, tx))
        major = (val % 10 == 0 or val == 35)
        t_len = 15 if major else 8
        cv2.line(traced_image, (tx, ty), (tx, ty + t_len), (0, 255, 0), 2 if major else 1)
        if major:
            cv2.putText(traced_image, f"{val}", (tx - 8, ty + t_len + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)        

    return traced_image, latest_image_path

# ==========================================================
# OUTPUT IMAGE FUNCTION (Saves debug output)
# ==========================================================
def outputImage(traced_image, image_path):
    if traced_image is None or image_path is None:
        return

    save_choice = input("Do you want to save the tracked output image? (y/n): ").strip().lower()
    if save_choice == 'y':
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filename = os.path.basename(image_path)
        out_path = os.path.join(OUTPUT_DIR, f"tracked_{filename}")
        cv2.imwrite(out_path, traced_image)
        print(f"Saved tracked debug image to: {out_path}\n")
    else:
        print("Image saving skipped.\n")

# ==========================================================
# MAIN LOOP
# ==========================================================
def main_loop():
    print("--- Solar Panel Tracker Started ---")
    while True:
        cmd = input("Take a picture? (y/n): ").strip().lower()
        
        if cmd == 'n':
            print("Stopping program.")
            break
        elif cmd == 'y':
            print("Calling camera...")
            
            # 1. CAPTURE IMAGE (Saves new image into imgForward folder)
            # -> If you want to test statically without camera, just comment out this line 
            #    and let process_and_trace() automatically grab the existing latest file!
            #captureImg.capture_image()
            
            # 2. PROCESS AND TRACE (Grabs latest image from imgForward and runs trackers)
            traced_img, img_path = process_and_trace()
            
            # 3. OUTPUT IMAGE (Handles saving/debugging choice)
            if traced_img is not None:
                outputImage(traced_img, img_path)
        else:
            print("Invalid input. Please type 'y' to continue or 'n' to stop.")

if __name__ == "__main__":
    main_loop()