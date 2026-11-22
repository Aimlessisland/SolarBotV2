import glob
import os
import time
import threading
import cv2

CAMERA_SOURCE = None  # Auto-detected at startup (checks /dev/v4l/by-id & /dev/video0..5)
DIR_PATH = "imgForward"

# Desired resolution
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

# Auto-light tuning (keeps image balanced from dark indoors to bright sun)
TARGET_LIGHT = 115   # Target brightness (0..255)
LIGHT_GAP    = 20    # Deadband so exposure doesn't flicker
MIN_EXPOSURE = 40    # Lowest exposure for bright sunlight
MAX_EXPOSURE = 1200  # Highest exposure for dark indoor testing

cap = None
latest_frame = None
frame_lock = threading.Lock()
cam_ready = False
exposure = 350


def test():
    print("Call capture Work!")


def find_working_camera():
    """Auto-detects the active USB video capture stream across /dev/v4l/by-id and /dev/video0..5."""
    by_id_paths = sorted(glob.glob("/dev/v4l/by-id/*video-index0"))
    candidates = by_id_paths + [f"/dev/video{i}" for i in range(6)]

    seen_realpaths = set()
    for source in candidates:
        if not os.path.exists(source):
            continue
        real_dev = os.path.realpath(source)
        if real_dev in seen_realpaths:
            continue
        seen_realpaths.add(real_dev)

        test_cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if test_cap.isOpened():
            test_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            ret, frame = test_cap.read()
            if ret and frame is not None and frame.size > 0:
                print(f"[CAMERA AUTO-FOUND] {source} -> {real_dev}")
                return test_cap, source
        test_cap.release()

    return None, None


def grab_loop():
    """Continuously drains camera buffer in background so latest_frame is always live."""
    global latest_frame, cam_ready, exposure
    count = 0

    while cam_ready and cap is not None and cap.isOpened():
        ret, frame = cap.read()
        if ret:
            with frame_lock:
                latest_frame = frame

            # Check brightness every 10 frames and adjust exposure up/down
            count += 1
            if count % 10 == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                light = gray.mean()

                if light < (TARGET_LIGHT - LIGHT_GAP) and exposure < MAX_EXPOSURE:
                    exposure = min(MAX_EXPOSURE, exposure + 40)
                    cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
                elif light > (TARGET_LIGHT + LIGHT_GAP) and exposure > MIN_EXPOSURE:
                    exposure = max(MIN_EXPOSURE, exposure - 40)
                    cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
        else:
            time.sleep(0.005)


def init_camera():
    """Auto-finds and configures V4L2 camera once, then starts background reader."""
    global cap, latest_frame, cam_ready, exposure, CAMERA_SOURCE
    if cam_ready and cap is not None and cap.isOpened():
        return True

    cap, detected_source = find_working_camera()
    if cap is None:
        print("Error: Could not find any working USB camera on /dev/v4l/by-id or /dev/video0..5")
        return False

    CAMERA_SOURCE = detected_source

    # 1. Force MJPG BEFORE resolution so 1080p runs at 30 FPS
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    # 2. Adjust Camera Properties (runs once at startup)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # 1 = Manual mode on V4L2
    cap.set(cv2.CAP_PROP_CONTRAST, 100)
    cap.set(cv2.CAP_PROP_BRIGHTNESS, 150)
    cap.set(cv2.CAP_PROP_EXPOSURE, exposure)

    # One-time warm-up flush
    for _ in range(5):
        ret, frame = cap.read()
        if ret:
            with frame_lock:
                latest_frame = frame

    cam_ready = True
    threading.Thread(target=grab_loop, daemon=True).start()
    print(f"[CAMERA READY] {CAMERA_SOURCE} locked open & streaming 1920x1080 in background.")
    return True


def capture_image():
    os.makedirs(DIR_PATH, exist_ok=True)

    if not init_camera():
        return None

    existing_files = glob.glob(os.path.join(DIR_PATH, "front_*.jpg"))
    next_index = len(existing_files) + 1
    filename = f"front_{next_index:04d}.jpg"
    full_path = os.path.join(DIR_PATH, filename)

    with frame_lock:
        frame = None if latest_frame is None else latest_frame.copy()

    if frame is not None:
        cv2.imwrite(full_path, frame)
        print(f"Saved instant frame: {full_path}")
        return full_path
    else:
        print("Error: No frame available in buffer.")
        return None


if __name__ == "__main__":
    capture_image()