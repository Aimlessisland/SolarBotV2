from ursina import *


# Change this number to adjust your camera's up/down tilt:
# The higher the number is the further it tilts down towards the floor
CAMERA_TILT_ANGLE = 30

# --- NEW: Camera Lens Width (Field of View) ---
# Standard view is around 40-60.
# A higher number (like 100-120) creates a wide-angle / fish-eye lens effect.
CAMERA_FOV = 145

# Custom cube wireframe mesh using mode='line'
cube_line_mesh = Mesh(
    vertices=[
        # Bottom square
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (-0.5, -0.5, 0.5),
        (-0.5, -0.5, 0.5),
        (-0.5, -0.5, -0.5),
        # Top square
        (-0.5, 0.5, -0.5),
        (0.5, 0.5, -0.5),
        (0.5, 0.5, -0.5),
        (0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
        (-0.5, 0.5, -0.5),
        # Vertical pillars
        (-0.5, -0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, -0.5, 0.5),
        (-0.5, 0.5, 0.5),
    ],
    mode='line',
)


def setup_lighting():
  """Sets up clean directional and ambient lighting"""
  DirectionalLight().y = 10
  DirectionalLight().x = 5
  DirectionalLight().z = -5
  AmbientLight(color=color.rgba(200, 200, 200, 255))


def setup_environment():
  """Creates a solar panel grid with thick aluminum frames and crisp black wireframe lines"""
  Sky(color=color.hex('#50b4ff'))

  grid_step = 6
  tile_size = 5.6
  frame_size = 5.9

  solar_blue = color.hex('#1b365d')
  aluminum_gray = color.rgb(185, 190, 195)

  # Floor Grid
  for x in range(-25, 26, int(grid_step)):
    for z in range(-25, 26, int(grid_step)):
      # 1. Thick Aluminum Base Frame
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

      # 2. Inner Blue Solar Panel Surface
      Entity(
          model='cube',
          position=(x, -0.2, z),
          scale=(tile_size, 0.1, tile_size),
          color=solar_blue,
          unlit=True,
      )

      # 3. Crisp Black Wireframe Outline on top
      floor_line = Entity(
          model='wireframe_cube',
          position=(x, -0.2, z),
          scale=(tile_size, 0.1, tile_size),
          color=color.black,
      )
      floor_line.set_depth_offset(1)


def create_robot():
  """Creates the robot chassis and a wider single straight orange brush across the front"""
  robot = Entity(position=(0, 0.5, 0))

  # 1. Main Robot Hull (Light Gray)
  hull = Entity(
      parent=robot,
      model='cube',
      position=(0, 0, -2),  # Hull position
      scale=(2, 0.5, 2.5),  # Width: 2, Height: 0.5, Depth: 2.5
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

  # 2. Wider Single Straight Orange Front Brush
  brush_y = -0.05  # Height offset relative to robot center
  brush_z = -0.8   # Forward/Backward distance from hull
  brush_width = 3 # <--- TINKER WITH THIS: Increase for wider, decrease for shorter
  brush_height = 0.3
  brush_depth = 0.2

  # Single continuous brush entity extending wider to the sides
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
  """Mounts the first-person camera to the robot with a wide action-cam FOV"""
  camera.parent = robot
  camera.position = (0, 0.75, -1.3)
  camera.rotation = (CAMERA_TILT_ANGLE, 0, 0)
  

  
def setup_camera_controls():
  """Initializes camera position and creates the live telemetry HUD"""
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
  """Creates a text element at the top center of the screen"""
  return Text(
      text='',
      origin=(0, 0),
      position=(0, 0.45),
      scale=1.5,
      color=color.lime,
      background=True,
  )


def control(robot, status_text):
  """Handles robot movement and updates screen text when keys are pressed"""
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
  """Handles fullscreen toggle with Ctrl+F and exits fullscreen with Esc"""
  if key == 'f':
    window.fullscreen = not window.fullscreen
  elif key == 'escape':
    window.fullscreen = False


def main():
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