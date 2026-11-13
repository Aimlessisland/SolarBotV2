import glob
import os
import cv2
import numpy as np

# Folders configuration
INPUT_DIR = os.path.expanduser("~/solarBot/imgForward")
EDGES_DIR = os.path.expanduser("~/solarBot/edgesOutput")


def fit_curve_3pts(p1, p2, p3, axis="y_along_x", num_points=60):
  """Fits a 2nd-degree polynomial passing EXACTLY through p1, p2, and p3.

  - 'y_along_x' (for horizontal arcs): fits y = ax^2 + bx + c
  - 'x_along_y' (for vertical side lanes): fits x = ay^2 + by + c
  """
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


def process_to_edges():
  os.makedirs(EDGES_DIR, exist_ok=True)

  image_files = glob.glob(os.path.join(INPUT_DIR, "front_*.jpg"))
  if not image_files:
    print("No images found in imgForward folder!")
    return None

  latest_file = max(image_files, key=os.path.getmtime)
  print(f"Reading latest image: {latest_file}")

  img = cv2.imread(latest_file)
  if img is None:
    print("Error: Could not read the image.")
    return None

  h, w = img.shape[:2]

  # 1. Grayscale & Canny Edge Detection
  gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  edges = cv2.Canny(gray_img, 100, 200)

  # ==========================================================
  # 2. CALIBRATED TAPE BOUNDARIES (1920x1080)
  # ==========================================================

  cx_ratio = 0.482

  # LEFT SIDE LANE: top point shifted slightly right (0.280 -> 0.287) to bend toward center
  left_top = (int(w * 0.287), int(h * 0.165))
  left_mid = (int(w * 0.145), int(h * 0.400))  # Kept unchanged
  left_bot = (int(w * 0.020), int(h * 0.670))  # Kept unchanged
  left_curve = fit_curve_3pts(left_top, left_mid, left_bot, axis="x_along_y")

  # RIGHT SIDE LANE: shifted in toward the center by ~9.6 px (-0.005w across all 3 points)
  right_top = (int(w * 0.660), int(h * 0.165))
  right_mid = (int(w * 0.820), int(h * 0.400))
  right_bot = (int(w * 0.940), int(h * 0.670))
  right_curve = fit_curve_3pts(
      right_top, right_mid, right_bot, axis="x_along_y"
  )

  # BOTTOM BRUSH ARC (Connected to updated right_bot)
  brush_mid = (int(w * cx_ratio), int(h * 0.880))
  brush_curve = fit_curve_3pts(left_bot, brush_mid, right_bot, axis="y_along_x")

  # CENTER REFERENCE LINE
  center_top = (int(w * cx_ratio), int(h * 0.165))
  center_mid = (int(w * cx_ratio), int(h * 0.500))
  center_bot = brush_mid
  center_line = fit_curve_3pts(
      center_top, center_mid, center_bot, axis="x_along_y"
  )

  # ==========================================================
  # 3. DRAW REINFORCEMENT LINES ON EDGES
  # ==========================================================
  LINE_THICKNESS = 6
  BRUSH_THICKNESS = 10
  CENTER_THICKNESS = 4

  cv2.polylines(
      edges, [left_curve], isClosed=False, color=255, thickness=LINE_THICKNESS
  )
  cv2.polylines(
      edges, [right_curve], isClosed=False, color=255, thickness=LINE_THICKNESS
  )
  cv2.polylines(
      edges, [brush_curve], isClosed=False, color=255, thickness=BRUSH_THICKNESS
  )
  cv2.polylines(
      edges,
      [center_line],
      isClosed=False,
      color=255,
      thickness=CENTER_THICKNESS,
  )

  filename = os.path.basename(latest_file)
  output_path = os.path.join(EDGES_DIR, filename)
  cv2.imwrite(output_path, edges)

  print(f"Saved calibrated reinforced edge image to: {output_path}")
  return output_path


if __name__ == "__main__":
  process_to_edges()