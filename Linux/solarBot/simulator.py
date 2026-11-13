import os
import math
import time
import cv2
from direct.filter.FilterManager import FilterManager
import panda3d.core as p3d
from ursina import *

# ==========================================================
# CONFIGURATION & PHYSICAL SCALE
# ==========================================================
CAMERA_TILT_ANGLE = 22      # Downward camera tilt (degrees)
CAMERA_FOV = 115            # Wide-angle field of view

# Robot physical scale (1 unit = 1 meter)
ROBOT_WIDTH  = 0.71         # 71 cm physical width
ROBOT_DEPTH  = 0.51         # 51 cm physical depth
ROBOT_HEIGHT = 0.18         # 18 cm chassis height

# Commercial Solar Table Array (6.4m wide x 20.0m long)
TABLE_WIDTH  = 6.40
TABLE_LENGTH = 20.00
TABLE_TOP_Y  = 0.00
FLOOR_Y      = -1.50

# ==========================================================
# CROP & OUTPUT RESOLUTION SETTINGS
# ==========================================================
OUTPUT_WIDTH   = 1920
OUTPUT_HEIGHT  = 1080
CROP_PERCENT_X = 0.30       # Adjust if you want more/less side trimmed (0.20 to 0.35)
CROP_PERCENT_Y = 0.30       # Adjust if you want more/less top/bottom trimmed

FORWARD_DIR = "imgForward"
os.makedirs(FORWARD_DIR, exist_ok=True)

frame_counter = 1

# ==========================================================
# URSINA 3D ENGINE INITIALIZATION
# ==========================================================
app = Ursina(
    title="Solar Robot Simulator",
    size=(1280, 720),
    borderless=False
)

Sky(color=color.hex('#3b88d4'))

# Ground floor below table (cliff drop)
Entity(
    model='cube',
    position=(0, FLOOR_Y - 0.1, 0),
    scale=(35, 0.2, 35),
    color=color.hex('#1e221a'),
    unlit=True
)

# Under-table support legs
for x_leg in [-TABLE_WIDTH / 2 + 0.2, 0, TABLE_WIDTH / 2 - 0.2]:
    for z_leg in range(-8, 9, 4):
        Entity(
            model='cube',
            position=(x_leg, (FLOOR_Y + TABLE_TOP_Y) / 2, z_leg),
            scale=(0.08, abs(FLOOR_Y), 0.08),
            color=color.hex('#555b62'),
            unlit=True
        )

# Aluminum frame
Entity(
    model='cube',
    position=(0, TABLE_TOP_Y - 0.04, 0),
    scale=(TABLE_WIDTH + 0.08, 0.06, TABLE_LENGTH + 0.08),
    color=color.hex('#888f96'),
    unlit=True
)

# Modular Solar Panels
panel_cols = 6
panel_rows = 10
p_w = TABLE_WIDTH / panel_cols
p_l = TABLE_LENGTH / panel_rows

for c in range(panel_cols):
    for r in range(panel_rows):
        px = -TABLE_WIDTH / 2 + (c + 0.5) * p_w
        pz = -TABLE_LENGTH / 2 + (r + 0.5) * p_l

        Entity(
            model='cube',
            position=(px, TABLE_TOP_Y - 0.015, pz),
            scale=(p_w - 0.02, 0.03, p_l - 0.02),
            color=color.hex('#c2c7cc'),
            unlit=True
        )

        Entity(
            model='cube',
            position=(px, TABLE_TOP_Y - 0.005, pz),
            scale=(p_w - 0.06, 0.025, p_l - 0.06),
            color=color.hex('#0d1726'),
            unlit=True
        )

        for grid_idx in [-0.25 * p_w, 0, 0.25 * p_w]:
            Entity(
                model='cube',
                position=(px + grid_idx, TABLE_TOP_Y + 0.001, pz),
                scale=(0.004, 0.001, p_l - 0.08),
                color=color.hex('#263d59'),
                unlit=True
            )

# White Tape Track Markings
Entity(  # Left Guide Track
    model='cube',
    position=(-0.45, TABLE_TOP_Y + 0.003, 0),
    scale=(0.045, 0.003, TABLE_LENGTH * 0.94),
    color=color.white,
    unlit=True
)

Entity(  # Front Edge Warning Seam
    model='cube',
    position=(0, TABLE_TOP_Y + 0.003, (TABLE_LENGTH / 2) - 0.45),
    scale=(TABLE_WIDTH * 0.92, 0.003, 0.045),
    color=color.white,
    unlit=True
)

# Robot Chassis & Camera Mount
START_Z = -TABLE_LENGTH / 2 + 2.0
robot = Entity(position=(0, TABLE_TOP_Y + (ROBOT_HEIGHT / 2), START_Z), rotation_y=0)

hull = Entity(
    parent=robot,
    model='cube',
    position=(0, 0, -ROBOT_DEPTH / 2),
    scale=(ROBOT_WIDTH, ROBOT_HEIGHT, ROBOT_DEPTH),
    color=color.hex('#6e7379'),
    unlit=True
)

camera.parent = robot
camera.position = (0, 0.18, 0.0)
camera.rotation = (CAMERA_TILT_ANGLE, 0, 0)
camera.fov = CAMERA_FOV

# UI Overlay
status_text = Text(
    text='',
    origin=(0, 0),
    position=(0, 0.44),
    scale=1.4,
    color=color.lime,
    background=True
)

Text(
    text='[W/S] Drive | [A/D] Steer | [Space / C] Save 1080p Straight Frame | [R] Reset',
    position=(-0.85, -0.45),
    scale=0.85,
    color=color.yellow
)

# ==========================================================
# MAIN WINDOW FISHEYE FILTER (MATCHES YOUR SETUP EXACTLY)
# ==========================================================
filter_manager = FilterManager(base.win, base.cam)
scene_tex = p3d.Texture()
quad = filter_manager.renderSceneInto(colortex=scene_tex)

vshader = """
#version 120
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 uv;

void main() {
    gl_Position = p3d_Vertex;
    uv = p3d_MultiTexCoord0;
}
"""

fshader = """
#version 120
uniform sampler2D tex;
varying vec2 uv;

void main() {
    vec2 d = (uv - vec2(0.5, 0.5)) * 2.0;
    float r2 = dot(d, d);

    float k = 2.0;       // Base overall distortion strength
    float curve_x = 3.0; // Side curvature (bends vertical lines)
    float curve_y = 3.0; // Top/bottom curvature (bends horizontal lines)

    vec2 distorted_uv = uv + vec2(d.x * curve_x, d.y * curve_y) * r2 * (k * 0.35);

    if (distorted_uv.x < 0.0 || distorted_uv.x > 1.0 || distorted_uv.y < 0.0 || distorted_uv.y > 1.0) {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    } else {
        gl_FragColor = texture2D(tex, distorted_uv);
    }
}
"""

fisheye_shader = p3d.Shader.make(p3d.Shader.SL_GLSL, vshader, fshader)
quad.setShader(fisheye_shader)
quad.setShaderInput("tex", scene_tex)

# ==========================================================
# FRAME CAPTURE FUNCTION (CROPS STRAIGHT & SCALES TO 1080P)
# ==========================================================
def capture_fisheye_to_disk():
    global frame_counter
    while os.path.exists(os.path.join(FORWARD_DIR, f"front_{frame_counter:04d}.jpg")):
        frame_counter += 1

    filename = f"front_{frame_counter:04d}.jpg"
    filepath = os.path.join(FORWARD_DIR, filename)
    temp_path = os.path.join(FORWARD_DIR, "_raw_temp_snap.png")

    p3d_file = p3d.Filename.fromOsSpecific(os.path.abspath(temp_path))
    base.win.saveScreenshot(p3d_file)

    time.sleep(0.05)

    img = cv2.imread(temp_path)
    if img is not None:
        h, w = img.shape[:2]

        # Crop black border corners to create clean straight edges
        crop_x = int(w * CROP_PERCENT_X)
        crop_y = int(h * CROP_PERCENT_Y)

        cropped = img[crop_y : h - crop_y, crop_x : w - crop_x]

        # Resize cropped frame cleanly to 1920x1080
        final_1080p = cv2.resize(cropped, (OUTPUT_WIDTH, OUTPUT_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
        cv2.imwrite(filepath, final_1080p, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

        print(f"\n>>> SAVED 1920x1080 STRAIGHT-EDGE FRAME: {filepath} <<<")
        status_text.text = f"SAVED: {filename} (1920x1080)"
    else:
        print("[CAPTURE ERROR] Could not read screenshot for post-processing.")

# ==========================================================
# MOVEMENT & CLIFF DROP
# ==========================================================
def update():
    dt = time.dt

    half_w = TABLE_WIDTH / 2
    half_l = TABLE_LENGTH / 2
    on_table = (-half_w <= robot.x <= half_w) and (-half_l <= robot.z <= half_l)

    if not on_table:
        robot.y -= 3.8 * dt
        robot.rotation_x = min(robot.rotation_x + 55 * dt, 85)
        status_text.text = 'CLIFF DROP: FALLING OFF TABLE! (Press R)'
    else:
        robot.y = TABLE_TOP_Y + (ROBOT_HEIGHT / 2)
        robot.rotation_x = 0

        speed = 1.4 * dt
        rot_speed = 65.0 * dt

        if held_keys['w'] or held_keys['up arrow']:
            robot.position += robot.forward * speed
            status_text.text = 'Serial.println("M1 100")'
        elif held_keys['s'] or held_keys['down arrow']:
            robot.position -= robot.forward * speed
            status_text.text = 'Serial.println("M2 100")'
        elif held_keys['a'] or held_keys['left arrow']:
            robot.rotation_y -= rot_speed
            status_text.text = 'Serial.println("M4 100")'
        elif held_keys['d'] or held_keys['right arrow']:
            robot.rotation_y += rot_speed
            status_text.text = 'Serial.println("M3 100")'
        elif held_keys['r']:
            robot.position = (0, TABLE_TOP_Y + (ROBOT_HEIGHT / 2), START_Z)
            robot.rotation_y = 0
            robot.rotation_x = 0
            status_text.text = 'RESET POSITION'

def input(key):
    if key in ('space', 'c'):
        capture_fisheye_to_disk()
    elif key == 'f':
        window.fullscreen = not window.fullscreen
    elif key == 'escape':
        application.quit()

if __name__ == '__main__':
    app.run()