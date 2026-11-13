from ursina import *
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
import io
from PIL import ImageGrab

# Change this number to adjust your camera's up/down tilt:
CAMERA_TILT_ANGLE = 30
CAMERA_FOV = 145

# Global variable to store live frame bytes
latest_jpeg = None

# --- BUILT-IN HTTP STREAMING SERVER (No Flask / No MSS Needed) ---
class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/video_feed':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                global latest_jpeg
                while True:
                    if latest_jpeg is not None:
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(latest_jpeg)))
                        self.end_headers()
                        self.wfile.write(latest_jpeg + b'\r\n')
                    time.sleep(0.033) # ~30 FPS
            except Exception:
                pass
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass # Suppress terminal log spam

def start_server():
    server = HTTPServer(('0.0.0.0', 5000), StreamHandler)
    server.serve_forever()

def capture_loop():
    global latest_jpeg
    while True:
        try:
            # Grabs screen natively on Windows using Pillow (built into Ursina)
            img = ImageGrab.grab()
            img = img.resize((960, 540)) # Lower resolution for smooth streaming
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            latest_jpeg = buf.getvalue()
        except Exception:
            pass
        time.sleep(0.033)


# Custom cube wireframe mesh using mode='line'
cube_line_mesh = Mesh(
    vertices=[
        # Bottom square
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5), (-0.5, -0.5, 0.5), (-0.5, -0.5, -0.5),
        # Top square
        (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5),
        # Vertical pillars
        (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5),
        (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5),
    ],
    mode='line',
)


def setup_lighting():
  DirectionalLight().y = 10
  DirectionalLight().x = 5
  DirectionalLight().z = -5
  AmbientLight(color=color.rgba(200, 200, 200, 255))


def setup_environment():
  Sky(color=color.hex('#50b4ff'))

  grid_step = 6
  tile_size = 5.6
  frame_size = 5.9

  solar_blue = color.hex('#1b365d')
  aluminum_gray = color.rgb(185, 190, 195)

  for x in range(-25, 26, int(grid_step)):
    for z in range(-25, 26, int(grid_step)):
      Entity(
          model='cube',
          position=(x, -0.21, z),
          scale=(frame_size, 0.09, frame_size),
          color=aluminum_gray,
          unlit=True,
      )
      frame_line = Entity(
          model='wireframe_cube',
          position=(x, -0.21, z),
          scale=(frame_size, 0.09, frame_size),
          color=color.black,
      )
      frame_line.set_depth_offset(1)

      Entity(
          model='cube',
          position=(x, -0.2, z),
          scale=(tile_size, 0.1, tile_size),
          color=solar_blue,
          unlit=True,
      )

      floor_line = Entity(
          model='wireframe_cube',
          position=(x, -0.2, z),
          scale=(tile_size, 0.1, tile_size),
          color=color.black,
      )
      floor_line.set_depth_offset(1)


def create_robot():
  robot = Entity(position=(0, 0.5, 0))

  hull = Entity(
      parent=robot,
      model='cube',
      position=(0, 0, -2),
      scale=(2, 0.5, 2.5),
      color=color.light_gray,
      unlit=True,
  )

  robot_outline = Entity(
      parent=hull,
      model='wireframe_cube',
      scale=(1.0, 1.0, 1.0),
      color=color.black,
  )
  robot_outline.set_depth_offset(1)

  brush_y = -0.05
  brush_z = -0.8
  brush_width = 3
  brush_height = 0.3
  brush_depth = 0.2

  Entity(
      parent=robot,
      model='cube',
      position=(0, brush_y, brush_z),
      scale=(brush_width, brush_height, brush_depth),
      color=color.orange,
      unlit=True,
  )

  return robot


def setup_camera(robot):
  camera.parent = robot
  camera.position = (0, 0.75, -1.3)
  camera.rotation = (CAMERA_TILT_ANGLE, 0, 0)
  

def setup_camera_controls():
  camera.position = (0, 0.52, -0.7)
  camera.rotation_x = CAMERA_TILT_ANGLE

  global camera_hud
  camera_hud = Text(
      text='',
      position=(-0.85, 0.45),
      scale=1.1,
      color=color.lime,
      background=True,
  )


def setup_ui_text():
  return Text(
      text='',
      origin=(0, 0),
      position=(0, 0.45),
      scale=1.5,
      color=color.lime,
      background=True,
  )


def control(robot, status_text):
  speed = 5 * time.dt
  rotation_speed = 100 * time.dt

  if held_keys['w'] or held_keys['up']:
    robot.position += robot.forward * speed
    status_text.text = 'Serial.println(M1 100)'
  elif held_keys['s'] or held_keys['down']:
    robot.position -= robot.forward * speed
    status_text.text = 'Serial.println(M2 100)'
  elif held_keys['a'] or held_keys['left']:
    robot.rotation_y -= rotation_speed
    status_text.text = 'Serial.println(M5 100)'
  elif held_keys['d'] or held_keys['right']:
    robot.rotation_y += rotation_speed
    status_text.text = 'Serial.println(M6 100)'
  else:
    status_text.text = ''


def input(key):
  if key == 'f':
    window.fullscreen = not window.fullscreen
  elif key == 'escape':
    window.fullscreen = False


def main():
  # Start background threads for screen capture and built-in HTTP server
  threading.Thread(target=capture_loop, daemon=True).start()
  threading.Thread(target=start_server, daemon=True).start()
  print("🚀 Simulation stream active at: http://localhost:5000/video_feed")

  app = Ursina()

  setup_lighting()
  setup_environment()
  my_robot = create_robot()
  setup_camera(my_robot)
  status_text = setup_ui_text()
  setup_camera_controls()

  global update

  def update():
    control(my_robot, status_text)

    dt = time.dt
    rot_speed = 50 * dt
    move_speed = 2.0 * dt

    if held_keys['up arrow']:
      camera.rotation_x -= rot_speed
    if held_keys['down arrow']:
      camera.rotation_x += rot_speed

    if held_keys['shift']:
      camera.y += move_speed
    if held_keys['control']:
      camera.y -= move_speed

    if camera.y < 0.05:
      camera.y = 0.05

    height_cm = camera.y * 100
    tilt_angle = camera.rotation_x

    camera_hud.text = (
        f'--- CAMERA MOUNT TELEMETRY ---\n'
        f'Tilt Angle : {tilt_angle:.1f}°\n'
        f'Height     : {height_cm:.1f} cm'
    )

  app.run()


if __name__ == '__main__':
  main()