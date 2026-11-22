import os
import glob
import json
import math
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import cv2
import numpy as np
import serial

import captureImg

# Tuned Up reference are forward 65 width 71 as brush the rest of parameter let god design
# May peace be with you!

OUTPUT_DIR = "objectDetectTest"
FORWARD_DIR = "imgForward"
SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
BRUSH_WIDTH_CM = 71.0

M1_DIST_TABLE = {
    100: 5.0,
    200: 1.0,
    300: 9.0,
    400: 15.0,
    500: 20.0,
    600: 30.0,
    700: 36.0,
    800: 43.0,
    900: 50.0,
    1000: 57.0,
}

M2_DIST_TABLE = {
    100: 8.0,
    200: 1.0,
    300: 10.0,
    400: 17.0,
    500: 25.0,
    600: 33.0,
    700: 41.0,
    800: 49.0,
    900: 57.0,
    1000: 65.0,
}

serial_lock = threading.Lock()
blind_approach_steps = 0
front_guide_steps = 0
corner_state = "NORMAL"      # "NORMAL" -> "CORNER_BACKUP" -> "CORNER_ROTATE" -> "NORMAL"
corner_rotate_steps = 0

# Web start/stop event for 'f' (Full Cleaning) mode
web_start_event = threading.Event()


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
# COMMAND DISPATCHER (THREAD-SAFE FOR KEYBOARD + WEB)
# ==========================================================
def send_command(ser, command):
    """Sends command over serial and waits for Arduino 'OK'."""
    with serial_lock:
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
    list_of_images = glob.glob(os.path.join(FORWARD_DIR, "front_*.jpg"))
    if not list_of_images:
        list_of_images = glob.glob(os.path.join(FORWARD_DIR, "front_*.png"))

    if not list_of_images:
        print(f"\n[ERROR] No 'front_*.jpg' images found in '{FORWARD_DIR}'!")
        print(f"Please drop your image (e.g., front_0001.jpg) into '{FORWARD_DIR}' and try again.\n")
        return None, None, None

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
    front_mid = (int(w * cx_ratio), front_y_base + front_curve_depth)
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

    cm_calib = np.array([65,    60,  55,    50,  45,    40,  35,  30,  25,  20,  15,  10,    9,     8,     7,     6,     5,   0], dtype=float)
    y_calib  = np.array([215.5, 240, 254.5, 280, 300.5, 340, 375, 410, 438, 496, 553, 630.0, 648.0, 666.0, 684.0, 702.0, 720, 760], dtype=float)

    left_pts = left_curve.reshape(-1, 2)
    left_poly = np.polyfit(left_pts[:, 1], left_pts[:, 0], 2)
    right_pts = right_curve.reshape(-1, 2)
    right_poly = np.polyfit(right_pts[:, 1], right_pts[:, 0], 2)

    # ==========================================================
    # 3. PRIORITY 1: LEFT LINE SCAN + REAL-WORLD DEGREE ANGLE
    # ==========================================================
    def leftTracking(wide_search=False):
        mode_tag = "WIDE ROTATION SCAN" if wide_search else "NORMAL LANE SCAN"
        print(f"\n--- [PRIORITY 1: LEFT LINE SCAN REPORT ({mode_tag})] ---")
        left_perspective_corrections = {
            65: -5,
            60: -5,
            55: -6,
            50: -7,
            45: -7,
            40: -10,
            35: -13,
            30: -15,
            25: -19,
            20: -23,
            15: -28,
            10: -35,
            9:  -36,
            8:  -36,
            7:  -37,
            6:  -37,
            5:  -38
        }
        MAX_OFFSET_JUMP_PX = 55 if wide_search else 22
        MAX_CM_GAP = 15 if wide_search else 10

        detected_points = []
        offsets_by_cm = {}
        x_cm_by_y_cm = {}
        prev_calibrated_px = None
        prev_cm = None

        # Scan bottom-to-top (5 cm near brush -> 65 cm far ahead)
        for cm in reversed(cm_calib[:-1]):
            cm_key = int(cm)
            base_y = np.interp(cm, cm_calib[::-1], y_calib[::-1])
            target_y = int(base_y)
            left_x = int(np.polyval(left_poly, target_y))
            right_x = int(np.polyval(right_poly, target_y))
            lane_width_px = max(1.0, float(right_x - left_x))

            if wide_search:
                search_start = max(0, left_x - 60)
                search_end = min(w, left_x + 320)
            else:
                search_start = max(0, left_x - 35)
                search_end = min(w, left_x + 170)

            search_window = masked_edges[target_y, search_start:search_end]
            white_pixels = np.where(search_window > 0)[0]

            if len(white_pixels) > 0:
                edge_x = int(np.min(white_pixels + search_start))
                raw_px = edge_x - left_x
                correction = left_perspective_corrections.get(cm_key, 0)
                calibrated_px = raw_px + correction

                # Prevent jumping across large empty gaps onto stray glare far ahead
                if prev_cm is not None and (cm_key - prev_cm) > MAX_CM_GAP:
                    print(f"  [Left  {cm_key:2d}cm] Y={target_y:3d} | REJECTED gap ({cm_key}cm vs prev {prev_cm}cm > {MAX_CM_GAP}cm)")
                    continue

                # Continuity check against previous valid point below it
                if prev_calibrated_px is not None and abs(calibrated_px - prev_calibrated_px) > MAX_OFFSET_JUMP_PX:
                    print(f"  [Left  {cm_key:2d}cm] Y={target_y:3d} | REJECTED jump ({calibrated_px:+4d}px vs prev {prev_calibrated_px:+4d}px)")
                    continue

                # Convert pixel offset at this row into real-world cm (71.0 cm full panel width)
                x_cm = round((calibrated_px / lane_width_px) * BRUSH_WIDTH_CM, 2)

                prev_calibrated_px = calibrated_px
                prev_cm = cm_key
                offsets_by_cm[cm_key] = calibrated_px
                x_cm_by_y_cm[cm_key] = x_cm
                detected_points.append((edge_x, target_y))
                cv2.circle(traced_image, (edge_x, target_y), 3, (0, 0, 255), -1)
                cv2.line(traced_image, (left_x, target_y), (edge_x, target_y), (0, 0, 255), 1)

                print(
                    f"  [Left  {cm_key:2d}cm] Y={target_y:3d} | BaseX={left_x:3d} -> EdgeX={edge_x:3d} | "
                    f"Offset={calibrated_px:+4d}px ({x_cm:+5.1f}cm)"
                )
            else:
                print(f"  [Left  {cm_key:2d}cm] Y={target_y:3d} | (No white pixels detected in window)")

        if len(detected_points) > 2:
            pts_array = np.array(detected_points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [pts_array], isClosed=False, color=(0, 0, 255), thickness=2)

        # 5-Point Symmetrical Pairings + Short-Line Slope Fallback
        pairs = [(65, 5), (60, 10), (55, 15), (50, 20), (45, 25)]
        pair_deltas = []
        for f, n in pairs:
            if f in offsets_by_cm and n in offsets_by_cm:
                delta = offsets_by_cm[f] - offsets_by_cm[n]
                pair_deltas.append(delta)
                print(f"  [Pair ({f}cm - {n}cm)] Delta: {delta:+4d}px ({offsets_by_cm[f]} - {offsets_by_cm[n]})")

        lean_value = None
        if len(pair_deltas) >= 2:
            lean_value = round(float(np.median(pair_deltas)), 1)
        elif len(offsets_by_cm) >= 3:
            sorted_cms = sorted(offsets_by_cm.keys())
            lean_value = round(float(offsets_by_cm[sorted_cms[-1]] - offsets_by_cm[sorted_cms[0]]), 1)

        # Real-World Heading Angle (degrees) from Top-Down (Y_cm, X_cm) linear fit
        angle_deg = None
        if len(x_cm_by_y_cm) >= 3:
            y_cm_arr = np.array(sorted(x_cm_by_y_cm.keys()), dtype=np.float64)
            x_cm_arr = np.array([x_cm_by_y_cm[k] for k in sorted(x_cm_by_y_cm.keys())], dtype=np.float64)
            slope_dx_dy, _ = np.polyfit(y_cm_arr, x_cm_arr, 1)
            angle_deg = round(math.degrees(math.atan(slope_dx_dy)), 1)

        valid_count = len(offsets_by_cm)
        near_offsets = [offsets_by_cm[cm_k] for cm_k in offsets_by_cm if cm_k <= 25]
        near_x_cms = [x_cm_by_y_cm[cm_k] for cm_k in x_cm_by_y_cm if cm_k <= 25]
        near_count = len(near_offsets)
        near_offset = round(float(np.median(near_offsets)), 1) if near_count > 0 else None
        near_x_cm = round(float(np.median(near_x_cms)), 1) if near_count > 0 else None
        has_near_left = (near_count >= 2)
        mark_5_offset = offsets_by_cm.get(5, None)
        has_far_left = (65 in offsets_by_cm or 60 in offsets_by_cm)
        is_left_valid = (valid_count >= 4) or has_near_left

        # Topmost point where left line stops (detected_points is bottom-to-top, so [-1] is topmost)
        left_end_y = detected_points[-1][1] if len(detected_points) > 0 else None
        left_end_cm = max(offsets_by_cm.keys()) if len(offsets_by_cm) > 0 else None

        angle_str = f"{angle_deg:+.1f} deg" if angle_deg is not None else "None"
        print(
            f"  ==> Left Valid: {is_left_valid} ({valid_count} pts, {near_count} near, 5cm={mark_5_offset}px) | "
            f"Est. Angle: {angle_str} | Lean: {lean_value} px | Near Offset: {near_offset} px ({near_x_cm} cm) | Ends at Y={left_end_y} px ({left_end_cm} cm)"
        )
        return {
            "is_left_valid": is_left_valid,
            "valid_count": valid_count,
            "has_near_left": has_near_left,
            "mark_5_offset": mark_5_offset,
            "has_far_left": has_far_left,
            "left_lean": lean_value,
            "angle_deg": angle_deg,
            "near_offset": near_offset,
            "near_x_cm": near_x_cm,
            "left_end_y": left_end_y,
            "left_end_cm": left_end_cm,
        }

    # ==========================================================
    # 4. PRIORITY 2: BIDIRECTIONAL FRONT EDGE SCAN (BOTTOM-UP + TOP-DOWN)
    # ==========================================================
    def frontTracking(left_end_y=None, left_end_cm=None):
        print("\n--- [PRIORITY 2: BIDIRECTIONAL FRONT EDGE SCAN REPORT] ---")
        width_steps = np.linspace(10, 60, 25, dtype=int)
        front_pts = front_curve.reshape(-1, 2)
        front_poly = np.polyfit(front_pts[:, 0], front_pts[:, 1], 2)
        brush_pts = brush_curve.reshape(-1, 2)
        brush_poly = np.polyfit(brush_pts[:, 0], brush_pts[:, 1], 2)

        x_start_top, x_end_top = front_left[0], front_right[0]
        x_start_bot, x_end_bot = left_bot[0], right_bot[0]

        top_hits = []
        bot_hits = []

        for width_pos in width_steps:
            tx_top = int(np.interp(width_pos, [0, 71], [x_start_top, x_end_top]))
            tx_bot = int(np.interp(width_pos, [0, 71], [x_start_bot, x_end_bot]))
            top_y = int(np.polyval(front_poly, tx_top))
            bottom_y = int(np.polyval(brush_poly, tx_bot))

            num_samples = max(10, abs(bottom_y - top_y))
            y_samples = np.linspace(top_y, bottom_y, num_samples, dtype=int)
            x_samples = np.linspace(tx_top, tx_bot, num_samples, dtype=int)

            # 4A. Top-Down Ray (65 cm -> 0 cm)
            for y, x in zip(y_samples, x_samples):
                x_l = max(0, x - 3)
                x_r = min(w, x + 4)
                y_t = max(0, y - 1)
                y_b = min(h, y + 2)
                if np.any(masked_edges[y_t:y_b, x_l:x_r] > 0):
                    top_hits.append((x, y))
                    break

            # 4B. Bottom-Up Ray (0 cm brush -> 65 cm, ignores glare above front edge)
            # Start 12 px above brush curve so brush curve border itself never false-triggers
            for y, x in zip(y_samples[::-1], x_samples[::-1]):
                if y > bottom_y - 12:
                    continue
                x_l = max(0, x - 3)
                x_r = min(w, x + 4)
                y_t = max(0, y - 1)
                y_b = min(h, y + 2)
                if np.any(masked_edges[y_t:y_b, x_l:x_r] > 0):
                    bot_hits.append((x, y))
                    break

        def fit_clean_front(hits, color_bgr, label):
            if len(hits) < 5:
                print(f"  [{label:8s}] Hits: {len(hits):2d}/25 (Insufficient)")
                return None, None, 0, None, None

            arr = np.array(hits, dtype=np.float64)
            med_y = float(np.median(arr[:, 1]))
            # Reject glare/noise outliers > 25 px away from median Y
            inliers = arr[np.abs(arr[:, 1] - med_y) <= 25.0]
            if len(inliers) < 5:
                print(f"  [{label:8s}] Hits: {len(hits):2d}/25 -> Only {len(inliers)} inliers near Y={med_y:.1f}px (Scattered glare)")
                return None, None, len(inliers), None, None

            avg_y = float(np.mean(inliers[:, 1]))
            f_y = round(avg_y, 1)
            f_cm = round(float(np.interp(avg_y, y_calib, cm_calib)), 1)

            # Calculate front-line straightness (tilt: Y_right - Y_left)
            # Positive tilt (+px) = right side is lower/closer than left -> steer right (M4)
            # Negative tilt (-px) = left side is lower/closer than right -> steer left (M3)
            x_span = float(inliers[:, 0].max() - inliers[:, 0].min())
            tilt_px = 0.0
            tilt_deg = 0.0
            if x_span >= 40.0:
                slope_dy_dx, _ = np.polyfit(inliers[:, 0], inliers[:, 1], 1)
                tilt_px = round(float(slope_dy_dx * x_span), 1)

                left_x_at_y = float(np.polyval(left_poly, avg_y))
                right_x_at_y = float(np.polyval(right_poly, avg_y))
                lane_w_px = max(1.0, right_x_at_y - left_x_at_y)
                dx_cm = (x_span / lane_w_px) * BRUSH_WIDTH_CM

                cm_above = float(np.interp(max(215.5, avg_y - 10.0), y_calib, cm_calib))
                cm_below = float(np.interp(min(760.0, avg_y + 10.0), y_calib, cm_calib))
                cm_per_px_y = max(0.05, abs(cm_above - cm_below) / 20.0)
                dy_cm = tilt_px * cm_per_px_y
                tilt_deg = round(math.degrees(math.atan2(dy_cm, dx_cm)), 1)

            for pt in inliers.astype(int):
                cv2.circle(traced_image, (pt[0], pt[1]), 3, (0, 0, 255), -1)

            poly_tracked = np.polyfit(inliers[:, 0], inliers[:, 1], 2)
            x_vals = np.linspace(inliers[:, 0].min(), inliers[:, 0].max(), 60)
            y_vals = np.polyval(poly_tracked, x_vals)
            tracked_curve = np.column_stack((x_vals, y_vals)).astype(np.int32).reshape((-1, 1, 2))
            cv2.polylines(traced_image, [tracked_curve], isClosed=False, color=color_bgr, thickness=2)

            print(
                f"  [{label:8s}] Inliers: {len(inliers):2d}/{len(hits):2d} | Y={f_y:5.1f} px | "
                f"Distance={f_cm:4.1f} cm | Tilt={tilt_px:+5.1f} px ({tilt_deg:+4.1f} deg)"
            )
            return f_cm, f_y, len(inliers), tilt_px, tilt_deg

        # Draw Green for Top-Down, Cyan (255, 255, 0) for Bottom-Up
        top_cm, top_y, top_inliers, top_tilt_px, top_tilt_deg = fit_clean_front(top_hits, (0, 255, 0), "TOP-DOWN")
        bot_cm, bot_y, bot_inliers, bot_tilt_px, bot_tilt_deg = fit_clean_front(bot_hits, (255, 255, 0), "BOT-UP")

        # Arbitrate between Bottom-Up and Top-Down using Left-Line End Anchor
        front_cm, front_y, front_tilt_px, front_angle_deg = None, None, None, None
        if bot_cm is not None and top_cm is not None:
            # If Top-Down got tricked by glare much higher up (smaller Y) than Bottom-Up, trust Bottom-Up!
            if (bot_y - top_y) > 35.0:
                front_cm, front_y, front_tilt_px, front_angle_deg = bot_cm, bot_y, bot_tilt_px, bot_tilt_deg
                print(f"  ==> ARBITRATION: Top-Down hit upper glare ({top_cm}cm) -> Using BOT-UP ({bot_cm}cm)")
            else:
                front_cm, front_y, front_tilt_px, front_angle_deg = top_cm, top_y, top_tilt_px, top_tilt_deg
                print(f"  ==> ARBITRATION: Both scans agree -> Using TOP-DOWN ({top_cm}cm)")
        elif bot_cm is not None:
            front_cm, front_y, front_tilt_px, front_angle_deg = bot_cm, bot_y, bot_tilt_px, bot_tilt_deg
            print(f"  ==> ARBITRATION: Only BOT-UP valid -> Using BOT-UP ({bot_cm}cm)")
        elif top_cm is not None:
            front_cm, front_y, front_tilt_px, front_angle_deg = top_cm, top_y, top_tilt_px, top_tilt_deg
            print(f"  ==> ARBITRATION: Only TOP-DOWN valid -> Using TOP-DOWN ({top_cm}cm)")

        # Cross-check with Left Line End Point (e.g. left line stops at 9 cm right where front edge begins)
        if front_y is not None and left_end_y is not None and left_end_cm is not None and left_end_cm <= 25:
            diff_y = abs(front_y - left_end_y)
            print(f"  ==> CORNER CROSS-CHECK: Front Y={front_y:.1f}px vs Left End Y={left_end_y}px ({left_end_cm}cm) | DeltaY={diff_y:.1f}px")

        return front_cm, front_y, front_tilt_px, front_angle_deg

    # Execute Priority 1 (widened during corner rotation) and Priority 2 (paused during rotation)
    use_wide_scan = (corner_state == "CORNER_ROTATE")
    left_data = leftTracking(wide_search=use_wide_scan)

    if use_wide_scan:
        front_cm, front_y, front_tilt_px, front_angle_deg = None, None, None, None
        print("\n--- [PRIORITY 2: FRONT EDGE SCAN PAUSED DURING ROTATION] ---")
    else:
        front_cm, front_y, front_tilt_px, front_angle_deg = frontTracking(
            left_end_y=left_data["left_end_y"],
            left_end_cm=left_data["left_end_cm"]
        )

    # 5. Draw Boundary Overlays
    cv2.polylines(traced_image, [left_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [right_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [brush_curve], isClosed=False, color=(128, 0, 128), thickness=2)
    cv2.polylines(traced_image, [front_curve], isClosed=False, color=(128, 0, 128), thickness=2)

    # 6. Height & Width Depth Ticks
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
        **left_data,
        "front_cm": front_cm,
        "front_y": front_y,
        "front_tilt_px": front_tilt_px,
        "front_angle_deg": front_angle_deg,
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
# DECISION ARBITRATION (CONTINUOUS LANE-KEEPING + CORNER TURN + FRONT FALLBACK)
# ==========================================================
def decide_movement(telem):
    global blind_approach_steps, front_guide_steps, corner_state, corner_rotate_steps

    # --- Calibrated Safe Lane Range (Matches 5cm=+45px .. 50cm=+60px ideal profile) ---
    SAFE_LANE_MIN = 45.0            # Inner safe cruising limit (45 px)
    SAFE_LANE_MAX = 65.0            # Outer safe cruising limit (65 px)
    TARGET_OFFSET = 55.0            # Midpoint of [45px .. 65px]
    IDEAL_CRUISE_ANGLE = 2.0        # Natural perspective slope when centered (+45px near -> +60px far)
    STOP_EDGE_CM = 10.0             # Trigger corner sequence when front edge <= 10.0 cm
    SAFE_ROTATE_CLEARANCE_CM = 13.5 # Minimum front edge distance required BEFORE rotating
    ROTATE_HANDOFF_MAX_DEG = 15.0   # Hand off to active NORMAL lane steering once within ±15 deg
    FRONT_TILT_DEADZONE_PX = 10.0   # Front line tilt tolerance before steering M3/M4
    MAX_FRONT_GUIDE_STEPS = 4       # Max recovery steps using front line alone when left line is lost
    STEP_DURATION = 300
    MICRO_TURN_DURATION = 250       # Minimum 250 ticks so IRFB3306 + relay switches cleanly
    HARD_TURN_DURATION = 300        # Strong correction when far outside 45..65 px band
    MAX_BLIND_APPROACH_STEPS = 2
    MAX_CORNER_ROTATE_STEPS = 12    # Safety cap so it never spins endlessly

    is_left_valid = telem["is_left_valid"]
    valid_count = telem["valid_count"]
    mark_5_offset = telem.get("mark_5_offset", None)
    has_far_left = telem["has_far_left"]
    left_lean = telem["left_lean"]
    angle_deg = telem.get("angle_deg", None)
    near_offset = telem["near_offset"]
    near_x_cm = telem.get("near_x_cm", None)
    left_end_y = telem["left_end_y"]
    left_end_cm = telem["left_end_cm"]
    front_cm = telem["front_cm"]
    front_y = telem["front_y"]
    front_tilt_px = telem.get("front_tilt_px", None)
    front_angle_deg = telem.get("front_angle_deg", None)

    in_target_band = (near_offset is not None and SAFE_LANE_MIN <= near_offset <= SAFE_LANE_MAX)
    angle_display = f"{angle_deg:+.1f} deg" if angle_deg is not None else "None"
    front_tilt_display = f"{front_tilt_px:+.1f} px ({front_angle_deg:+.1f} deg)" if front_tilt_px is not None else "None"

    print("\n" + "=" * 55)
    print(f"TELEMETRY SUMMARY [STATE: {corner_state}]:")
    print(f"  [P1] Left Line Valid : {is_left_valid} ({valid_count} pts, 5cm={mark_5_offset}px, In45..65={in_target_band})")
    print(f"  [P1] Est. Line Angle : {angle_display} (Lean={left_lean} px, Target={IDEAL_CRUISE_ANGLE:+.1f} deg)")
    print(f"  [P1] Far Left Alive  : {has_far_left} (Ends at Y={left_end_y} px / {left_end_cm} cm)")
    print(f"  [P1] Near Offset     : {near_offset} px / {near_x_cm} cm (Safe Band: {SAFE_LANE_MIN}..{SAFE_LANE_MAX} px)")
    print(f"  [P2] Front Edge      : {front_cm} cm (Front Y={front_y} px | Tilt={front_tilt_display})")
    print("=" * 55)

    # ----------------------------------------------------------
    # CORNER STATE 1: VERIFY SAFE BACKUP CLEARANCE (>= 13.5 cm) -> M6 800 KICKOFF
    # ----------------------------------------------------------
    if corner_state == "CORNER_BACKUP":
        # Safeguard: If backing up reveals the left boundary actually continues past a panel seam, cancel turn!
        if has_far_left and valid_count >= 8:
            print(
                f"[CORNER ABORTED - SEAM DETECTED] Left line continues to {left_end_cm} cm ({valid_count} pts) "
                f"-> Cancel turn & Resume Forward (M1 {STEP_DURATION})"
            )
            corner_state = "NORMAL"
            corner_rotate_steps = 0
            return f"M1 {STEP_DURATION}", False

        if front_cm is None or front_cm >= SAFE_ROTATE_CLEARANCE_CM:
            dist_str = f"{front_cm:.1f} cm" if front_cm is not None else "cleared frame"
            print(
                f"[CORNER CLEARANCE OK] Front edge {dist_str} (>= {SAFE_ROTATE_CLEARANCE_CM} cm) "
                f"-> Safe to pivot! Kickoff Rotate Right (M6 800)"
            )
            corner_state = "CORNER_ROTATE"
            corner_rotate_steps = 1
            return "M6 800", False
        else:
            print(
                f"[CORNER BACKUP RETRY] Front edge only {front_cm:.1f} cm (< {SAFE_ROTATE_CLEARANCE_CM} cm) "
                f"-> Backing up more for safety (M2 200)"
            )
            return "M2 200", False

    # ----------------------------------------------------------
    # CORNER STATE 2: ROTATE RIGHT (M6 300) UNTIL NEW EDGE LOCKED, THEN HAND OFF TO NORMAL STEERING
    # ----------------------------------------------------------
    if corner_state == "CORNER_ROTATE":
        new_edge_locked = (
            valid_count >= 5
            and angle_deg is not None
            and abs(angle_deg) <= ROTATE_HANDOFF_MAX_DEG
        )

        if new_edge_locked:
            print(
                f"[CORNER PIVOT LOCKED] New edge seen ({angle_deg:+.1f} deg, 5cm={mark_5_offset}px, Pts={valid_count}) "
                f"-> Switching immediately to active NORMAL lane steering!"
            )
            corner_state = "NORMAL"
            corner_rotate_steps = 0
            blind_approach_steps = 0
            front_guide_steps = 0
            # Fall straight through to Priority 1A below so it steers M3/M4 on this exact frame!
        else:
            if corner_rotate_steps >= MAX_CORNER_ROTATE_STEPS:
                print(f"[CORNER STOP] Reached max rotation steps ({MAX_CORNER_ROTATE_STEPS}) -> STOP!")
                corner_state = "NORMAL"
                corner_rotate_steps = 0
                return None, True

            corner_rotate_steps += 1
            print(
                f"[CORNER ROTATING {corner_rotate_steps}/{MAX_CORNER_ROTATE_STEPS}] "
                f"Angle={angle_display} (Need <= ±{ROTATE_HANDOFF_MAX_DEG} deg, Pts={valid_count}) -> M6 300"
            )
            return "M6 300", False

    # ----------------------------------------------------------
    # IMMEDIATE FRONT EDGE GUARD: ONLY TURN IF LEFT LINE ENDS NEAR CORNER (IGNORE PANEL SEAMS)
    # ----------------------------------------------------------
    left_ends_near_corner = (not has_far_left) and (left_end_cm is None or left_end_cm <= 25)
    if front_cm is not None and front_cm <= STOP_EDGE_CM and left_ends_near_corner:
        print(
            f"[CORNER DETECTED] Front edge at {front_cm:.1f} cm (<= {STOP_EDGE_CM} cm) & Left ends at {left_end_cm} cm "
            f"-> Backing up for safe clearance (M2 300)"
        )
        corner_state = "CORNER_BACKUP"
        return "M2 300", False

    # ----------------------------------------------------------
    # PRIORITY 1A: ACTIVE CONTINUOUS LANE-KEEPING (TARGET 45..65px & +2.0 DEG)
    # ----------------------------------------------------------
    if (has_far_left or valid_count >= 4) and valid_count >= 4:
        blind_approach_steps = 0
        front_guide_steps = 0
        if front_cm is not None and front_cm > STOP_EDGE_CM:
            print(f"[PRIORITY 1 OVERRIDE] Front edge seen at {front_cm:.1f} cm, Left Line still alive ahead -> KEEP GOING!")

        lane_error = (near_offset - TARGET_OFFSET) if near_offset is not None else 0.0
        cur_angle = angle_deg if angle_deg is not None else IDEAL_CRUISE_ANGLE

        # Relative angle compared to ideal straight-cruise perspective (+2.0 deg)
        rel_angle = cur_angle - IDEAL_CRUISE_ANGLE

        # Project where near_offset will land after 1 forward M1 step (~10 cm ahead)
        projected_offset = (near_offset + (rel_angle * 2.5)) if near_offset is not None else TARGET_OFFSET
        will_land_in_band = (SAFE_LANE_MIN <= projected_offset <= SAFE_LANE_MAX) and (abs(rel_angle) <= 4.0)

        # Desired heading angle to smoothly glide back onto 55 px (45..65 px band)
        desired_angle = IDEAL_CRUISE_ANGLE + max(-7.0, min(7.0, -lane_error * 0.35))
        angle_diff = cur_angle - desired_angle

        in_safe_band = (near_offset is None) or (SAFE_LANE_MIN <= near_offset <= SAFE_LANE_MAX)
        print(
            f"[LANE CHECK] Offset={near_offset}px (In45..65={in_safe_band}) | "
            f"Angle={angle_display} (Desired={desired_angle:+.1f} deg, Diff={angle_diff:+.1f} deg) | Projected={projected_offset:.1f}px"
        )

        # 1. Inside 45..65 px and aligned with ideal cruise angle -> Step Forward!
        if in_safe_band and abs(rel_angle) <= 2.5:
            print(f"[PRIORITY 1] Inside Safe Lane ({SAFE_LANE_MIN}..{SAFE_LANE_MAX}px) & Straight -> Step Forward (M1 {STEP_DURATION})")
            return f"M1 {STEP_DURATION}", False

        # 2. Outside 45..65 px, BUT nose is already pointed back into the band -> Step Forward to glide in!
        if will_land_in_band:
            print(f"[PRIORITY 1 - GLIDE IN] Angled toward 45..65px band ({cur_angle:+.1f} deg) -> Step Forward (M1 {STEP_DURATION})")
            return f"M1 {STEP_DURATION}", False

        # 3. Actively steer M4 (Right) or M3 (Left) on every move to keep line in 45..65 px!
        if abs(angle_diff) > 2.2:
            turn_ticks = HARD_TURN_DURATION if (abs(angle_diff) > 6.5 or abs(lane_error) > 20.0) else MICRO_TURN_DURATION
            if angle_diff > 0:
                print(f"[PRIORITY 1 - SELF-CORRECT] Steer Right toward 45..65px (Diff={angle_diff:+.1f} deg) -> M4 {turn_ticks}")
                return f"M4 {turn_ticks}", False
            else:
                print(f"[PRIORITY 1 - SELF-CORRECT] Steer Left toward 45..65px (Diff={angle_diff:+.1f} deg) -> M3 {turn_ticks}")
                return f"M3 {turn_ticks}", False
        else:
            print(f"[PRIORITY 1] On intercept course ({cur_angle:+.1f} deg) -> Step Forward (M1 {STEP_DURATION})")
            return f"M1 {STEP_DURATION}", False

    # ----------------------------------------------------------
    # PRIORITY 2: LEFT LINE ENDED AHEAD -> CHECK FRONT EDGE
    # ----------------------------------------------------------
    if is_left_valid and not has_far_left:
        if front_cm is not None:
            blind_approach_steps = 0
            print(
                f"[PRIORITY 2 - APPROACH] Left line ended (Y={left_end_y} px) & Front edge at {front_cm:.1f} cm "
                f"(> {STOP_EDGE_CM} cm) -> Lock steering & Step Forward (M1 {STEP_DURATION})"
            )
            return f"M1 {STEP_DURATION}", False
        else:
            if blind_approach_steps < MAX_BLIND_APPROACH_STEPS:
                blind_approach_steps += 1
                print(
                    f"[PRIORITY 2 - CORNER APPROACH {blind_approach_steps}/{MAX_BLIND_APPROACH_STEPS}] "
                    f"Left line ended at {left_end_cm} cm, scanning for front line -> Step Forward (M1 {STEP_DURATION})"
                )
                return f"M1 {STEP_DURATION}", False
            else:
                print("[STOP - NO LINE] Left line ended and no front edge found after approach -> STOP MOVING!")
                return None, True

    # ----------------------------------------------------------
    # PRIORITY 3: FRONT-LINE FALLBACK ALIGNMENT (LAST TRY BEFORE QUITTING)
    # ----------------------------------------------------------
    if front_cm is not None:
        if front_cm <= STOP_EDGE_CM:
            print(
                f"[PRIORITY 3 - CORNER DETECTED] Front edge at {front_cm:.1f} cm (<= {STOP_EDGE_CM} cm) "
                f"-> Backing up for safe clearance (M2 300)"
            )
            corner_state = "CORNER_BACKUP"
            front_guide_steps = 0
            return "M2 300", False

        if front_tilt_px is not None and abs(front_tilt_px) > FRONT_TILT_DEADZONE_PX:
            if front_guide_steps >= MAX_FRONT_GUIDE_STEPS:
                print("[STOP - NO LINE] Max front-line alignment tries reached -> STOP MOVING!")
                return None, True

            front_guide_steps += 1
            turn_ticks = HARD_TURN_DURATION if abs(front_tilt_px) > 25.0 else MICRO_TURN_DURATION
            if front_tilt_px > 0:
                print(
                    f"[PRIORITY 3 - FRONT ALIGN RIGHT {front_guide_steps}/{MAX_FRONT_GUIDE_STEPS}] "
                    f"Left line out of view, Front line tilted {front_tilt_display} "
                    f"(right side closer) -> Steer Right to square up (M4 {turn_ticks})"
                )
                return f"M4 {turn_ticks}", False
            else:
                print(
                    f"[PRIORITY 3 - FRONT ALIGN LEFT {front_guide_steps}/{MAX_FRONT_GUIDE_STEPS}] "
                    f"Left line out of view, Front line tilted {front_tilt_display} "
                    f"(left side closer) -> Steer Left to square up (M3 {turn_ticks})"
                )
                return f"M3 {turn_ticks}", False

        if front_guide_steps < MAX_FRONT_GUIDE_STEPS:
            front_guide_steps += 1
            print(
                f"[PRIORITY 3 - FRONT STRAIGHT GUIDE {front_guide_steps}/{MAX_FRONT_GUIDE_STEPS}] "
                f"Front line straight ({front_tilt_display}) at {front_cm:.1f} cm -> Step Forward (M1 {STEP_DURATION})"
            )
            return f"M1 {STEP_DURATION}", False

    print("[STOP - NO LINE] Left line lost (insufficient points) -> STOP MOVING!")
    return None, True


# ==========================================================
# DISTANCE MEASUREMENT & NON-BLOCKING BACKGROUND MAPPER
# ==========================================================
def ticks_to_cm(motor_cmd: str, ticks: int) -> float:
    """Returns calibrated true displacement (cm) for M1 (forward) or M2 (reverse)."""
    table = M1_DIST_TABLE if motor_cmd == "M1" else M2_DIST_TABLE
    if ticks in table:
        return table[ticks]
    if ticks < 200:
        # Unramped region (< 200 ticks)
        return round((ticks / 100.0) * table[100], 2)
    # Ramped cruise region (>= 200 ticks): piecewise linear interpolation
    ramped_ticks = [200, 300, 400, 500, 600, 700, 800, 900, 1000]
    ramped_cm = [table[t] for t in ramped_ticks]
    return round(float(np.interp(ticks, ramped_ticks, ramped_cm)), 2)


def write_map_files_worker(path_points, corner_vertices):
    """Background daemon writer saving a human-readable ASCII + JSON text map."""
    try:
        xs = [p[0] for p in path_points]
        ys = [p[1] for p in path_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width_cm = round(max_x - min_x, 1)
        height_cm = round(max_y - min_y, 1)
        est_passes = max(1, math.ceil(width_cm / BRUSH_WIDTH_CM))

        total_dist_cm = 0.0
        for i in range(1, len(path_points)):
            dx = path_points[i][0] - path_points[i - 1][0]
            dy = path_points[i][1] - path_points[i - 1][1]
            total_dist_cm += math.hypot(dx, dy)
        total_dist_cm = round(total_dist_cm, 1)

        # Build ASCII Grid (44 chars wide x 18 rows tall)
        grid_w, grid_h = 44, 18
        grid = [[" " for _ in range(grid_w)] for _ in range(grid_h)]
        span_x = max(10.0, max_x - min_x)
        span_y = max(10.0, max_y - min_y)

        def to_grid(pt):
            gx = int(round(((pt[0] - min_x) / span_x) * (grid_w - 1)))
            gy = int(round((1.0 - (pt[1] - min_y) / span_y) * (grid_h - 1)))
            gx = max(0, min(grid_w - 1, gx))
            gy = max(0, min(grid_h - 1, gy))
            return gx, gy

        # Plot path segments onto ASCII grid
        for i in range(1, len(path_points)):
            x0, y0 = to_grid(path_points[i - 1])
            x1, y1 = to_grid(path_points[i])
            steps = max(abs(x1 - x0), abs(y1 - y0), 1)
            for s in range(steps + 1):
                px = int(round(x0 + (x1 - x0) * (s / steps)))
                py = int(round(y0 + (y1 - y0) * (s / steps)))
                if grid[py][px] == " ":
                    grid[py][px] = "-" if abs(x1 - x0) >= abs(y1 - y0) else "|"

        # Plot corners and start marker
        turn_labels = ["EAST", "SOUTH", "WEST", "NORTH"]
        for idx, c_pt in enumerate(corner_vertices, start=1):
            cx, cy = to_grid(c_pt)
            grid[cy][cx] = str(idx) if idx <= 9 else "+"

        sx, sy = to_grid((0.0, 0.0))
        grid[sy][sx] = "S"

        # Assemble clean plaintext report
        lines = []
        lines.append("=" * 64)
        lines.append("                 SOLAR ARRAY EXPLORATION MAP")
        lines.append("=" * 64)
        lines.append(f"Timestamp      : {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Array Size     : Width = {width_cm:.1f} cm  |  Height = {height_cm:.1f} cm")
        lines.append(f"Brush Width    : {BRUSH_WIDTH_CM:.1f} cm (Est. Cleaning Passes: {est_passes})")
        lines.append(f"Total Traveled : {total_dist_cm:.1f} cm")
        lines.append("=" * 64)
        lines.append("")
        lines.append(f"                    TOP ({width_cm:.1f} cm)")
        for row_idx, row in enumerate(grid):
            left_lbl = f"LEFT ({height_cm:.0f}cm) " if row_idx == grid_h // 2 else "             "
            right_lbl = f" RIGHT ({height_cm:.0f}cm)" if row_idx == grid_h // 2 else ""
            lines.append(f"{left_lbl}{''.join(row)}{right_lbl}")
        lines.append(f"                  BOTTOM ({width_cm:.1f} cm)")
        lines.append("  Legend: [S]=Start (0,0)  [1..4]=Corners  [|/-]=Robot Path")
        lines.append("")
        lines.append("-" * 64)
        lines.append("CORNER WAYPOINTS (CM):")
        lines.append("  Start    : (0.0, 0.0)")
        for idx, c_pt in enumerate(corner_vertices, start=1):
            dir_lbl = turn_labels[(idx - 1) % 4]
            status = "Loop Closed" if idx >= 4 else f"Turned {dir_lbl}"
            lines.append(f"  Corner {idx} : ({c_pt[0]:.1f}, {c_pt[1]:.1f})  [{status}]")
        lines.append("-" * 64)
        lines.append("SUMMARY JSON:")

        summary_json = {
            "width_cm": width_cm,
            "height_cm": height_cm,
            "brush_width_cm": BRUSH_WIDTH_CM,
            "est_passes": est_passes,
            "corners_cm": corner_vertices,
        }
        lines.append(json.dumps(summary_json, indent=2))

        txt_path = os.path.join(OUTPUT_DIR, "explored_map.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        print("\n" + "*" * 60)
        print(f"[EXPLORATION COMPLETE] Array Size: {width_cm:.1f} cm (W) x {height_cm:.1f} cm (H)")
        print(f"[MAP SAVED] {txt_path}")
        print("[SHOWCASE MODE] Background counting stopped — robot continues driving!")
        print("*" * 60 + "\n")
    except Exception as e:
        print(f"[MAPPER WARNING] Could not save text map (main drive unaffected): {e}")


def save_explored_map_async(path_points, corner_vertices):
    """Launches a fire-and-forget daemon thread to write the map without blocking auto drive."""
    threading.Thread(
        target=write_map_files_worker,
        args=(list(path_points), list(corner_vertices)),
        daemon=True,
    ).start()


def start_brush_with_kick(ser, kick_pwm=120, cruise_pwm=50, kick_sec=0.04):
    """Sends a quick 40ms 120 PWM torque kick to break friction, then drops immediately to 50 PWM."""
    send_command(ser, f"M20 {kick_pwm}")
    time.sleep(kick_sec)
    send_command(ser, f"M20 {cruise_pwm}")


# ==========================================================
# CONTINUOUS AUTO DRIVE LOOP (RUNS UNTIL STOP CONDITION)
# ==========================================================
def auto_drive_step_by_step(ser, full_cleaning=False, wait_for_web_start=False):
    global blind_approach_steps, front_guide_steps, corner_state, corner_rotate_steps
    blind_approach_steps = 0
    front_guide_steps = 0
    corner_state = "NORMAL"
    corner_rotate_steps = 0

    BRUSH_KICK_PWM = 120
    BRUSH_CRUISE_PWM = 50
    BRUSH_KICK_SEC = 0.04
    PUMP_DURATION_MS = 1500
    PUMP_EVERY_N_MOVES = 4

    brush_running = False
    normal_move_counter = 0

    CARDINAL_VECTORS = [
        ("NORTH", 0.0, 1.0),
        ("EAST",  1.0, 0.0),
        ("SOUTH", 0.0, -1.0),
        ("WEST", -1.0, 0.0),
    ]
    mapping_active = True
    dir_idx = 0
    x_cm, y_cm = 0.0, 0.0
    path_points = [(0.0, 0.0)]
    corner_vertices = []
    total_forward_moves = 0

    mode_banner = f"FULL CLEANING MODE ('f': BRUSH {BRUSH_KICK_PWM}->{BRUSH_CRUISE_PWM} PWM + PUMP 1500ms/4 MOVES)" if full_cleaning else "CONTINUOUS AUTO DRIVE MODE ('a')"
    print("\n==========================================")
    print(f">>> {mode_banner} <<<")
    print("Background perimeter mapper ON (Starts at 0,0 facing NORTH)")
    print("Press Ctrl+C anytime to exit to terminal command menu")
    print("==========================================")

    step_count = 0

    try:
        while True:
            # In 'f' mode with web control, wait here until phone taps Start (or Break pauses it)
            if full_cleaning and wait_for_web_start and not web_start_event.is_set():
                if brush_running:
                    send_command(ser, "M20 0")
                    brush_running = False
                    print("[FULL MODE - PAUSED] Brush STOPPED (M20 0)")

                print("\n[FULL MODE STANDBY] Waiting for Web 'Start' button on port 5000 (Ctrl+C for terminal menu)...")
                while not web_start_event.is_set():
                    time.sleep(0.15)

                # Reset corner/cycle state cleanly when starting a fresh run from Web
                blind_approach_steps = 0
                front_guide_steps = 0
                corner_state = "NORMAL"
                corner_rotate_steps = 0
                normal_move_counter = 0
                print("\n[FULL MODE STARTED] Web Start triggered -> Engaging brush & auto clean!")

            # Start brush immediately in 'f' mode with 120 -> 50 PWM kickstart
            if full_cleaning and not brush_running:
                start_brush_with_kick(ser, BRUSH_KICK_PWM, BRUSH_CRUISE_PWM, BRUSH_KICK_SEC)
                brush_running = True
                print(f"[FULL MODE] Brush ON (Kick M20 {BRUSH_KICK_PWM} -> M20 {BRUSH_CRUISE_PWM})")

            step_count += 1
            print(f"\n>>> [AUTO CYCLE {step_count}] <<<")

            if captureImg.capture_image() is None:
                print("[STOP] Camera disconnected or failed to capture — aborting auto drive.")
                break

            traced_img, img_path, telem = process_and_trace()
            if traced_img is None:
                print("[STOP] Camera frame invalid — aborting auto drive.")
                break

            outputImage(traced_img, img_path)
            prev_corner_state = corner_state
            cmd, should_stop = decide_movement(telem)

            # Check if Web pressed Break/Stop while vision was processing
            if full_cleaning and wait_for_web_start and not web_start_event.is_set():
                continue

            # Full Cleaning Mode: Stop brush during corner turns, resume with kickstart after clearing corner
            if full_cleaning:
                if corner_state in ("CORNER_BACKUP", "CORNER_ROTATE") and brush_running:
                    send_command(ser, "M20 0")
                    brush_running = False
                    print("[FULL MODE] Corner turn active -> Brush STOPPED (M20 0)")
                elif corner_state == "NORMAL" and not brush_running and not should_stop:
                    start_brush_with_kick(ser, BRUSH_KICK_PWM, BRUSH_CRUISE_PWM, BRUSH_KICK_SEC)
                    brush_running = True
                    print(f"[FULL MODE] Corner cleared -> Brush RESUMED (Kick M20 {BRUSH_KICK_PWM} -> M20 {BRUSH_CRUISE_PWM})")

            # Fire-and-forget corner tracker (wrapped so it can never interrupt driving)
            if mapping_active:
                try:
                    if prev_corner_state == "CORNER_ROTATE" and corner_state == "NORMAL":
                        corner_vertices.append((round(x_cm, 1), round(y_cm, 1)))
                        dir_idx = (dir_idx + 1) % 4
                        print(
                            f"[MAPPER CORNER {len(corner_vertices)}] Vertex=({x_cm:.1f}, {y_cm:.1f}) cm "
                            f"-> Turned to {CARDINAL_VECTORS[dir_idx][0]}"
                        )
                except Exception as e:
                    print(f"[MAPPER WARNING] Corner tracking skipped: {e}")

            if cmd is not None:
                # Full Cleaning Mode: Spray water 1500ms once every 4 straight/lane movements
                if full_cleaning and corner_state == "NORMAL":
                    normal_move_counter += 1
                    if normal_move_counter >= PUMP_EVERY_N_MOVES:
                        print(f"[FULL MODE] {normal_move_counter} moves reached -> Spraying water (M30 {PUMP_DURATION_MS})")
                        send_command(ser, f"M30 {PUMP_DURATION_MS}")
                        normal_move_counter = 0

                send_command(ser, cmd)

                # Fire-and-forget distance counter (wrapped so it can never interrupt driving)
                if mapping_active:
                    try:
                        parts = cmd.split()
                        if len(parts) == 2 and parts[0] in ("M1", "M2"):
                            motor_code = parts[0]
                            ticks = int(parts[1])
                            dist_cm = ticks_to_cm(motor_code, ticks)
                            sign = 1.0 if motor_code == "M1" else -1.0
                            heading_name, dx, dy = CARDINAL_VECTORS[dir_idx]

                            x_cm += sign * dist_cm * dx
                            y_cm += sign * dist_cm * dy
                            path_points.append((round(x_cm, 1), round(y_cm, 1)))
                            if motor_code == "M1":
                                total_forward_moves += 1

                            dist_to_origin = math.hypot(x_cm, y_cm)
                            print(
                                f"[MAPPER] {motor_code} {ticks} ({sign * dist_cm:+.1f}cm {heading_name}) "
                                f"-> Pos=({x_cm:.1f}, {y_cm:.1f}) cm | DistToStart={dist_to_origin:.1f} cm"
                            )

                            # Once 3 corners done (heading WEST on Edge 4) and back near (0,0), save & stop mapper
                            if len(corner_vertices) >= 3 and dir_idx == 3 and total_forward_moves >= 8:
                                if dist_to_origin <= 30.0 or x_cm <= 15.0:
                                    corner_vertices.append((round(x_cm, 1), round(y_cm, 1)))
                                    save_explored_map_async(path_points, corner_vertices)
                                    mapping_active = False
                    except Exception as e:
                        print(f"[MAPPER WARNING] Step count skipped: {e}")

                time.sleep(0.2)  # Settle pause so robot finishes sliding before next photo

            if should_stop:
                print(f"[AUTO COMPLETE] Stop condition reached after {step_count} cycle(s).")
                if full_cleaning and wait_for_web_start:
                    # Return to Web standby instead of dropping out of 'f' mode
                    web_start_event.clear()
                    continue
                break

    except KeyboardInterrupt:
        print("\n[AUTO ABORTED] Ctrl+C pressed — returning to main command menu.")
    finally:
        web_start_event.clear()
        # Always guarantee brush turns off when leaving 'f' mode
        if full_cleaning and brush_running:
            print("[FULL MODE] Stopping brush on exit (M20 0)...")
            send_command(ser, "M20 0")

        if mapping_active and len(path_points) >= 5:
            print("[MAPPER] Saving partial perimeter map in background before exit...")
            write_map_files_worker(path_points, corner_vertices)

    print("==========================================\n")


# ==========================================================
# ALWAYS-ON MOBILE / WEB CONTROL BRIDGE (PORT 5000)
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
            cmd = params.get("c", [""])[0].strip().upper()

            if cmd:
                print(f"\n[WEB CMD] -> {cmd}")
                # Start / Break triggers from the phone controller
                if cmd in ("START", "F", "A", "M20 100"):
                    web_start_event.set()
                elif cmd in ("STOP", "BREAK", "PAUSE", "M0 0"):
                    web_start_event.clear()
                    send_command(ser, "M0 0")
                    send_command(ser, "M20 0")
                else:
                    # Direct manual control commands (M1, M2, M3, M4, M20, M30, etc.)
                    send_command(ser, cmd)

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
# DIRECT SERIAL TERMINAL MODE ('t' MODE)
# ==========================================================
def direct_serial_mode(ser):
    print("\n==========================================")
    print(">>> DIRECT TERMINAL MODE ('t' MODE) <<<")
    print("Type raw commands (e.g. M1 100, M20 100, M30 100)")
    print("Type 'q' to return to main menu.")
    print("==========================================")

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
    os.makedirs(FORWARD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not captureImg.init_camera():
        print("[FATAL] No camera detected! Plug in the camera and restart.")
        return
    ser = connect_port()

    # Keep Web bridge running continuously on port 5000 for phone control
    web_server = mobileControl(ser)

    # Boot directly into 'f' mode armed & waiting for Web 'Start' button
    web_start_event.clear()
    auto_drive_step_by_step(ser, full_cleaning=True, wait_for_web_start=True)

    while True:
        try:
            cmd = input("\nEnter command ('y': snap+move, 'c': capture+AI only, 'a': continuous auto drive, 'f': full clean mode [web wait], 't': direct serial terminal, 'n': exit): ").strip().lower()
        except KeyboardInterrupt:
            print("\nType 'n' to exit cleanly.")
            continue

        if cmd == 'n':
            captureImg.cam_ready = False
            if captureImg.cap is not None:
                captureImg.cap.release()
            web_server.shutdown()
            web_server.server_close()
            print("Terminating tracker.")
            if ser and ser.is_open:
                ser.close()
                print("Serial port closed.")
            break
        elif cmd == 'y':
            if captureImg.capture_image() is None:
                print("[ABORT] Camera failed — not moving.")
                continue

            traced_img, img_path, telem = process_and_trace()
            if traced_img is not None:
                outputImage(traced_img, img_path)
                decision, _ = decide_movement(telem)
                if decision is not None:
                    send_command(ser, decision)
        elif cmd == 'c':
            if captureImg.capture_image() is None:
                print("[ABORT] Camera failed.")
                continue

            traced_img, img_path, telem = process_and_trace()
            if traced_img is not None:
                outputImage(traced_img, img_path)
                decision, _ = decide_movement(telem)
                print(f"[AI ONLY - NO MOVE] Planned command: {decision}")
        elif cmd == 'a':
            auto_drive_step_by_step(ser, full_cleaning=False, wait_for_web_start=False)
        elif cmd == 'f':
            web_start_event.clear()
            auto_drive_step_by_step(ser, full_cleaning=True, wait_for_web_start=True)
        elif cmd == 't':
            direct_serial_mode(ser)
        else:
            print("Invalid input. Type 'y', 'c', 'a', 'f', 't', or 'n'.")


if __name__ == "__main__":
    main_loop()