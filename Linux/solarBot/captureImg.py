import glob
import os
import time
import threading
import cv2

CAMERA_SOURCE = "/dev/video0"
DIR_PATH = "imgForward"

# Desired resolution
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

_cap = None
_latest_frame = None
_frame_lock = threading.Lock()
_cam_ready = False


def test():
    print("Call capture Work!")


def _grab_loop():
    """Continuously drains camera buffer in background so latest_frame is always live."""
    global _latest_frame, _cam_ready
    while _cam_ready and _cap is not None and _cap.isOpened():
        ret, frame = _cap.read()
        if ret:
            with _frame_lock:
                _latest_frame = frame
        else:
            time.sleep(0.005)


def _init_camera():
    """Opens and configures V4L2 camera once, then starts background reader."""
    global _cap, _latest_frame, _cam_ready
    if _cam_ready and _cap is not None and _cap.isOpened():
        return True

    _cap = cv2.VideoCapture(CAMERA_SOURCE, cv2.CAP_V4L2)
    if not _cap.isOpened():
        print(f"Error: Could not open camera: {CAMERA_SOURCE}")
        return False

    # 1. Force MJPG BEFORE resolution so 1080p runs at 30 FPS
    _cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    _cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    # 2. Adjust Camera Properties (runs once at startup)
    _cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # 1 = Manual mode on V4L2
    _cap.set(cv2.CAP_PROP_CONTRAST, 100)
    _cap.set(cv2.CAP_PROP_BRIGHTNESS, 150)
    _cap.set(cv2.CAP_PROP_EXPOSURE, 350)

    # One-time warm-up flush
    for _ in range(5):
        ret, frame = _cap.read()
        if ret:
            with _frame_lock:
                _latest_frame = frame

    _cam_ready = True
    threading.Thread(target=_grab_loop, daemon=True).start()
    print(f"[CAMERA READY] {CAMERA_SOURCE} locked open & streaming in background.")
    return True


def capture_image():
    os.makedirs(DIR_PATH, exist_ok=True)

    if not _init_camera():
        return None

    existing_files = glob.glob(os.path.join(DIR_PATH, "front_*.jpg"))
    next_index = len(existing_files) + 1
    filename = f"front_{next_index:04d}.jpg"
    full_path = os.path.join(DIR_PATH, filename)

    with _frame_lock:
        frame = None if _latest_frame is None else _latest_frame.copy()

    if frame is not None:
        cv2.imwrite(full_path, frame)
        print(f"Saved instant frame: {full_path}")
        return full_path
    else:
        print("Error: No frame available in buffer.")
        return None


if __name__ == "__main__":
    capture_image()