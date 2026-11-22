import glob
import os
import time
import threading
import cv2

CAMERA_SOURCE = "/dev/video2"
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
    """Opens and configures V4L2 camera once, then starts background reader."""
    global cap, latest_frame, cam_ready, exposure
    if cam_ready and cap is not None and cap.isOpened():
        return True

    cap = cv2.VideoCapture(CAMERA_SOURCE, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"Error: Could not open camera: {CAMERA_SOURCE}")
        return False

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
    print(f"[CAMERA READY] {CAMERA_SOURCE} locked open & streaming in background.")
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
