import os
import glob
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import cv2
import numpy as np
import serial

# Camera capture module commented out for manual screenshot testing:
# import captureImg
# instand snapped

OUTPUT_DIR = "objectDetectTest"
FORWARD_DIR = "imgForward"
SERIAL_PORT = "/dev/ttyACM1"
BAUD_RATE = 115200

serial_lock = threading.Lock()

def connect_port():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # One-time Arduino Uno reset settle
        ser.reset_input_buffer()
        print(f"[CONNECTED] {SERIAL_PORT} @ {BAUD_RATE} ready!")
        return ser
    except Exception as e:
        print(f"[ERROR] Could not open {SERIAL_PORT}: {e}")
        return None

# ==========================================================
# COMMAND DISPATCHER
# ==========================================================
def send_command(ser, command):
    """Sends command over serial and waits for Arduino 'OK'."""
    if ser is None:
        print(f"\n>>> [OFFLINE] COMMAND ISSUED: {command} <<<\n")
        return False

    ser.reset_input_buffer()
    ser.write(f"{command}\n".encode("utf-8"))
    print(f">>> SENT: {command}")

    start = time.time()
    while time.time() - start < 3.0:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                print(f"<<< ARDUINO: {line}")
            if line.upper() == "OK":
                return True

    print("[TIMEOUT] No 'OK' received from Arduino.")
    return False

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
# PROCESS & TRACE PIPELINE
# ==========================================================
def process_and_trace():
    # Specifically target front_*.jpg files
    list_of_images = glob.glob(os.path.join(FORWARD_DIR, "front_*.jpg"))
    if not list_of_images:
        list_of_images = glob.glob(os.path.join(FORWARD_DIR, "front_*.png"))

    if not list_of_images:
        print(f"\n[ERROR] No 'front_*.jpg' images found in '{FORWARD_DIR}'!")
        print(f"Please drop your image (e.g., front_0001.jpg) into '{FORWARD_DIR}' and try again.\n")
        return None, None, None

    # Pick the newest front_*.jpg in the folder
    latest_image_path = max(list_of_images, key=os.path.getmtime)
    print("\n" + "=" * 55)
    print(f"Processing latest frame: {latest_image_path}")
    print("=" * 55)

    img = cv2.imread(latest_image_path)
    if img is None:
        print("[ERROR] Could not read the image file.")
        return None, None, None

    h, w = img.shape[:2]

    # 1. Canny Edge Detection
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray_img, 100, 200)

    # 2. Define Boundaries & Calibration Curves
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

    cm_calib = np.array([65,   60,   55,   50,   45,   40,   35,   30,   25,   20,   15,   10,   5,    0   ], dtype=float)
    y_calib  = np.array([215.5, 240,  254.5, 280,  300.5, 340,  375,  410,  438,  496,  553,  630,  720,  760  ], dtype=float)

    # ==========================================================
    # 3. TRACKING MODULES WITH DETAILED PX LOGGING
    # ==========================================================
    def leftTracking():
        print("\n--- [LEFT LINE SCAN REPORT] ---")
        left_perspective_corrections = {
            65: -10, 60: -11, 55: -12, 50: -13, 45: -14, 40: -16, 35: -20, 30: -20,
            25: -21, 20: -24, 15: -27, 10: -32, 5:  -36
        }
        left_pts = left_curve.reshape(-1, 2)
        left_poly = np.polyfit(left_pts[:, 1], left_pts[:, 0], 2)
        
        detected_points = []
        offsets_by_cm = {}
        
        for cm in cm_calib[:-1]:  # 65 cm down to 5 cm
            cm_key = int(cm)
            base_y = np.interp(cm, cm_calib[::-1], y_calib[::-1])
            target_y = int(base_y)
            left_x = int(np.polyval(left_poly, target_y))
            
            search_start = max(0, left_x - 30)
            search_end = min(w, left_x + 110)
            
            search_window = masked_edges[target_y, search_start:search_end]
            white_pixels = np.where(search_window > 0)[0]
            
            if len(white_pixels) > 0:
                edge_x = int(np.min(white_pixels + search_start))
                raw_px = edge_x - left_x
                correction = left_perspective_corrections.get(cm_key, 0)
                calibrated_px = raw_px + correction
                
                offsets_by_cm[cm_key] = calibrated_px
                detected_points.append((edge_x, target_y))
                cv2.circle(traced_image, (edge_x, target_y), 3, (0, 0, 255), -1)
                cv2.line(traced_image, (left_x, target_y), (edge_x, target_y), (0, 0, 255), 1)

                print(f"  [Left  {cm_key:2d}cm] Y={target_y:3d} | BaseX={left_x:3d} -> EdgeX={edge_x:3d} | Raw={raw_px:+4d}px | Offset={calibrated_px:+4d}px")
            else:
                print(f"  [Left  {cm_key:2d}cm] Y={target_y:3d} | (No white pixels detected in window)")

        if len(detected_points) > 2:
            pts_array = np.array(detected_points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [pts_array], isClosed=False, color=(0, 0, 255), thickness=2)

        # 5-Point Symmetrical Pairings
        pairs = [(65, 5), (60, 10), (55, 15), (50, 20), (45, 25)]
        pair_deltas = []
        for f, n in pairs:
            if f in offsets_by_cm and n in offsets_by_cm:
                delta = offsets_by_cm[f] - offsets_by_cm[n]
                pair_deltas.append(delta)
                print(f"  [Pair ({f}cm - {n}cm)] Delta: {delta:+4d}px ({offsets_by_cm[f]} - {offsets_by_cm[n]})")
        
        lean_value = None
        if len(pair_deltas) >= 3:
            lean_value = round(float(np.median(pair_deltas)), 1)
        elif len(pair_deltas) > 0:
            lean_value = round(float(np.mean(pair_deltas)), 1)

        has_far_left = (65 in offsets_by_cm or 60 in offsets_by_cm)
        print(f"  ==> Left Lean Result: {lean_value} px | Far Line Alive: {has_far_left}")
        return lean_value, has_far_left

    def rightTracking():
        print("\n--- [RIGHT LINE SCAN REPORT] ---")
        perspective_corrections = {
            65: 22, 60: 18, 55: 24, 50: 23, 45: 19, 40: 15, 35: 20, 30: 15,
            25: 12, 20: 6,  15: 4,  10: 0,  5:  0
        }
        right_pts = right_curve.reshape(-1, 2)
        right_poly = np.polyfit(right_pts[:, 1], right_pts[:, 0], 2)
        
        detected_points = []
        offsets_by_cm = {}
        
        for cm in cm_calib[:-1]:
            cm_key = int(cm)
            base_y = np.interp(cm, cm_calib[::-1], y_calib[::-1])
            target_y = int(base_y)
            right_x = int(np.polyval(right_poly, target_y))
            
            search_start = max(0, right_x - 110)
            search_end = min(w, right_x + 30)
            
            search_window = masked_edges[target_y, search_start:search_end]
            white_pixels = np.where(search_window > 0)[0]
            
            if len(white_pixels) > 0:
                edge_x = int(np.max(white_pixels + search_start))
                raw_px = right_x - edge_x
                correction = perspective_corrections.get(cm_key, 0)
                calibrated_px = raw_px + correction
                
                offsets_by_cm[cm_key] = calibrated_px
                detected_points.append((edge_x, target_y))
                cv2.circle(traced_image, (edge_x, target_y), 3, (0, 0, 255), -1)
                cv2.line(traced_image, (right_x, target_y), (edge_x, target_y), (0, 0, 255), 1)

                print(f"  [Right {cm_key:2d}cm] Y={target_y:3d} | BaseX={right_x:3d} -> EdgeX={edge_x:3d} | Raw={raw_px:+4d}px | Offset={calibrated_px:+4d}px")
            else:
                print(f"  [Right {cm_key:2d}cm] Y={target_y:3d} | (No white pixels detected in window)")

        if len(detected_points) > 2:
            pts_array = np.array(detected_points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [pts_array], isClosed=False, color=(0, 0, 255), thickness=2)

        pairs = [(65, 5), (60, 10), (55, 15), (50, 20), (45, 25)]
        pair_deltas = []
        for f, n in pairs:
            if f in offsets_by_cm and n in offsets_by_cm:
                delta = offsets_by_cm[f] - offsets_by_cm[n]
                pair_deltas.append(delta)
                print(f"  [Pair ({f}cm - {n}cm)] Delta: {delta:+4d}px ({offsets_by_cm[f]} - {offsets_by_cm[n]})")
        
        lean_value = None
        if len(pair_deltas) >= 3:
            lean_value = round(float(np.median(pair_deltas)), 1)
        elif len(pair_deltas) > 0:
            lean_value = round(float(np.mean(pair_deltas)), 1)

        has_far_right = (65 in offsets_by_cm or 60 in offsets_by_cm)
        print(f"  ==> Right Lean Result: {lean_value} px | Far Line Alive: {has_far_right}")
        return lean_value, has_far_right

    def frontTracking():
        print("\n--- [FRONT EDGE SCAN REPORT] ---")
        width_steps = np.linspace(10, 60, 25, dtype=int)
        front_pts = front_curve.reshape(-1, 2)
        front_poly = np.polyfit(front_pts[:, 0], front_pts[:, 1], 2)
        brush_pts = brush_curve.reshape(-1, 2)
        brush_poly = np.polyfit(brush_pts[:, 0], brush_pts[:, 1], 2)
        
        x_start_top, x_end_top = front_left[0], front_right[0]
        x_start_bot, x_end_bot = left_bot[0], right_bot[0]
        
        detected_points = []
        
        for width_pos in width_steps:
            tx_top = int(np.interp(width_pos, [0, 71], [x_start_top, x_end_top]))
            tx_bot = int(np.interp(width_pos, [0, 71], [x_start_bot, x_end_bot]))
            top_y = int(np.polyval(front_poly, tx_top))
            bottom_y = int(np.polyval(brush_poly, tx_bot))
            
            num_samples = max(10, abs(bottom_y - top_y))
            y_samples = np.linspace(top_y, bottom_y, num_samples, dtype=int)
            x_samples = np.linspace(tx_top, tx_bot, num_samples, dtype=int)
            
            for y, x in zip(y_samples, x_samples):
                x_l = max(0, x - 3)
                x_r = min(w, x + 4)
                y_t = max(0, y - 1)
                y_b = min(h, y + 2)
                
                search_window = masked_edges[y_t:y_b, x_l:x_r]
                if np.any(search_window > 0):
                    edge_pt = (x, y)
                    detected_points.append(edge_pt)
                    cv2.line(traced_image, (tx_top, top_y), (tx_bot, bottom_y), (0, 255, 0), 1)
                    cv2.circle(traced_image, edge_pt, 3, (0, 0, 255), -1)
                    break
                    
        front_cm = None
        if len(detected_points) >= 3:
            detected_arr = np.array(detected_points, dtype=np.float64)
            avg_y = float(np.mean(detected_arr[:, 1]))
            front_cm = round(float(np.interp(avg_y, y_calib, cm_calib)), 1)
            
            poly_tracked = np.polyfit(detected_arr[:, 0], detected_arr[:, 1], 2)
            x_vals = np.linspace(detected_arr[:, 0].min(), detected_arr[:, 0].max(), 60)
            y_vals = np.polyval(poly_tracked, x_vals)
            tracked_curve = np.column_stack((x_vals, y_vals)).astype(np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [tracked_curve], isClosed=False, color=(0, 255, 0), thickness=2)

            print(f"  -> Hits Found: {len(detected_points)}/25 points | Average Y: {avg_y:.1f} px | Distance: {front_cm:.1f} cm")
        else:
            print(f"  -> Hits Found: {len(detected_points)}/25 (Insufficient for front edge)")

        return front_cm

    # Execute tracking routines
    left_lean, has_far_left = leftTracking()
    right_lean, has_far_right = rightTracking()
    front_cm = frontTracking()

    # 4. Draw Boundary Overlays
    cv2.polylines(traced_image, [left_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [right_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [brush_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [front_curve], isClosed=False, color=(128, 0, 128), thickness=2)

    # 5. Height & Width Depth Ticks
    left_pts = left_curve.reshape(-1, 2)
    left_poly = np.polyfit(left_pts[:, 1], left_pts[:, 0], 2)
    right_pts = right_curve.reshape(-1, 2)
    right_poly = np.polyfit(right_pts[:, 1], right_pts[:, 0], 2)
    
    for cm in range(65, -1, -1):
        target_y = int(np.interp(cm, cm_calib[::-1], y_calib[::-1]))
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

    telemetry = {
        "left_lean": left_lean,
        "has_far_left": has_far_left,
        "right_lean": right_lean,
        "has_far_right": has_far_right,
        "front_cm": front_cm
    }

    return traced_image, latest_image_path, telemetry

# ==========================================================
# OUTPUT IMAGE SAVER
# ==========================================================
def outputImage(traced_image, image_path):
    if traced_image is None or image_path is None:
        return
    filename = os.path.basename(image_path)
    out_path = os.path.join(OUTPUT_DIR, f"tracked_{filename}")
    cv2.imwrite(out_path, traced_image)
    print(f"Saved tracked image: {out_path}\n")

# ==========================================================
# DECISION ARBITRATION
# ==========================================================
def decide_movement(telem):
    DEADZONE = 4.0
    STOP_EDGE_CM = 10.0
    STEP_DURATION = 100

    left_lean = telem["left_lean"]
    right_lean = telem["right_lean"]
    has_far_side = telem["has_far_left"] or telem["has_far_right"]
    front_cm = telem["front_cm"]

    print("\n" + "=" * 55)
    print("TELEMETRY SUMMARY:")
    print(f"  Front Distance : {front_cm} cm")
    print(f"  Far Line Alive : {has_far_side}")
    print(f"  Left Lean      : {left_lean} px")
    print(f"  Right Lean     : {right_lean} px")
    print("=" * 55)

    # 1. Edge Stop Arbitration
    if front_cm is not None and not has_far_side:
        print(f"[EDGE WARNING] Front edge detected at {front_cm:.1f} cm (True Array Termination)")
        if front_cm <= STOP_EDGE_CM:
            print(f"[SUCCESS] Reached target stopping margin ({front_cm:.1f} cm <= {STOP_EDGE_CM} cm)! HALTING.")
            return "M0 0", True

    # 2. Steering & Tracking Arbitration
    if left_lean is not None:
        if left_lean > DEADZONE:
            print(f"Action: Tracking Left Line -> Nose Left ({left_lean:+.1f}px) -> Counter Right")
            return f"M3 {STEP_DURATION}", False
        elif left_lean < -DEADZONE:
            print(f"Action: Tracking Left Line -> Nose Right ({left_lean:+.1f}px) -> Counter Left")
            return f"M4 {STEP_DURATION}", False
        else:
            print(f"Action: Tracking Left Line -> Parallel ({left_lean:+.1f}px) -> Step Forward")
            return f"M1 {STEP_DURATION}", False

    elif right_lean is not None:
        if right_lean > DEADZONE:
            print("Action: Tracking Right Line -> Counter Left")
            return f"M4 {STEP_DURATION}", False
        elif right_lean < -DEADZONE:
            print("Action: Tracking Right Line -> Counter Right")
            return f"M3 {STEP_DURATION}", False
        else:
            print("Action: Tracking Right Line -> Parallel -> Step Forward")
            return f"M1 {STEP_DURATION}", False

    else:
        print("Action: Center Track (No side frames) -> Driving Straight Forward")
        return f"M1 {STEP_DURATION}", False

# ==========================================================
# STEP-BY-STEP MANUAL DRIVE LOOP
# ==========================================================
def auto_drive_step_by_step(ser):
    print("\n==========================================")
    print(">>> STEP-BY-STEP MANUAL PROCESSING MODE <<<")
    print("==========================================")

    step_count = 0

    while True:
        step_input = input(f"\n[Step {step_count + 1}] Drop 'front_xxxx.jpg' into '{FORWARD_DIR}' & press Enter (or 'q' to stop): ").strip().lower()
        if step_input == 'q':
            print("Stopped.")
            break

        step_count += 1

        # Camera capture is intentionally commented out for manual control:
        # captureImg.capture_image()

        traced_img, img_path, telem = process_and_trace()
        if traced_img is None:
            print("[STOP] Waiting for a valid image.")
            continue

        cmd, should_stop = decide_movement(telem)
        send_command(ser, cmd)

        if should_stop:
            break

    print("==========================================\n")

# ==========================================================
# MOBILE / WEB CONTROL BRIDGE (PORT 5000)
# ==========================================================
def mobileControl(ser):
    """Starts background HTTP listener on port 5000 for Node.js / Web commands."""
    class WebCmdHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/cmd":
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)
            cmd = params.get("c", [""])[0].strip()

            if cmd:
                print(f"\n[WEB CMD] -> {cmd}")
                send_command(ser, cmd.upper())

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):
            pass

    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("0.0.0.0", 5000), WebCmdHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("[WEB READY] Listening for Node.js / Web on port 5000 (/cmd?c=...)")
    return server

# ==========================================================
# DIRECT SERIAL TERMINAL MODE
# ==========================================================
def direct_serial_mode(ser):
    print("\n==========================================")
    print(">>> DIRECT TERMINAL MODE ('t' MODE) <<<")
    print("Type raw commands (e.g. M1 100, M20 100, M30 100, M0 0)")
    print("Type 'q' to return to main menu.")
    print("==========================================")

    web_server = mobileControl(ser)
    
    while True:
        raw_cmd = input("\n[Direct Serial] > ").strip()
        if not raw_cmd:
            continue
        if raw_cmd.lower() == 'q':
            print("Exiting Direct Terminal Mode.")
            break

        send_command(ser, raw_cmd.upper())

    print("==========================================\n")

# ==========================================================
# MAIN LOOP
# ==========================================================
def main_loop():
    ser = connect_port()

    while True:
        cmd = input("\nEnter command ('y': single debug snap, 'a': step-by-step drive, 't': direct serial terminal, 'n': exit): ").strip().lower()
        
        if cmd == 'n':
            print("Terminating tracker.")
            if ser and ser.is_open:
                ser.close()
                print("Serial port closed.")
            break
        elif cmd == 'y':
            # Camera capture commented out:
            # captureImg.capture_image()

            traced_img, img_path, telem = process_and_trace()
            if traced_img is not None:
                outputImage(traced_img, img_path)
                decision, _ = decide_movement(telem)
                send_command(ser, decision)
        elif cmd == 'a':
            auto_drive_step_by_step(ser)
        elif cmd == 't':
            direct_serial_mode(ser)
        else:
            print("Invalid input. Type 'y', 'a', 't', or 'n'.")

if __name__ == "__main__":
    main_loop()