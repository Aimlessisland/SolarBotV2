import glob
import os
import cv2

# Easily change this later or adapt for 2 cameras
CAMERA_SOURCE = "/dev/video0"
DIR_PATH = os.path.expanduser("~/solarBot/imgForward")

# Desired resolution
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080


def test():
  print("Call capture Work!")


def capture_image():
  # Ensure folder exists
  os.makedirs(DIR_PATH, exist_ok=True)

  # Check existing files to roll the name forward automatically
  existing_files = glob.glob(os.path.join(DIR_PATH, "front_*.jpg"))
  next_index = len(existing_files) + 1
  filename = f"front_{next_index:04d}.jpg"
  full_path = os.path.join(DIR_PATH, filename)

  # Open camera directly with V4L2 to eliminate the GStreamer hang
  cap = cv2.VideoCapture(CAMERA_SOURCE, cv2.CAP_V4L2)
  if not cap.isOpened():
    print(f"Error: Could not open camera: {CAMERA_SOURCE}")
    return None

  # 1. Force MJPG BEFORE resolution so 1080p runs at 30 FPS instead of 5 FPS
  cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
  cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
  cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

  # 2. Adjust Camera Properties for Reflection/Noise Reduction
  cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # 1 = Manual mode on V4L2
  cap.set(cv2.CAP_PROP_CONTRAST, 100)
  cap.set(cv2.CAP_PROP_BRIGHTNESS, 100)
  cap.set(cv2.CAP_PROP_EXPOSURE, -5)

  # Warm-up buffer (fast at 30 FPS)
  for _ in range(5):
    cap.read()

  # Grab the frame with modified hardware settings
  ret, frame = cap.read()
  cap.release()

  if ret:
    cv2.imwrite(full_path, frame)
    print(f"Saved high-contrast/low-brightness frame: {full_path}")
    return full_path
  else:
    print("Error: Failed to grab frame.")
    return None


if __name__ == "__main__":
  capture_image()