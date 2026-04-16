import drawsvg as draw
import numpy as np

# --- 1. GLOBAL CONFIGURATION ---

SIGMA, BETA, RHO = 10.0, 8 / 3, 28.0

CANVAS_SIZE = 500

# --- Attractor Stretch Controls ---
SCALE_X = 5.0
SCALE_Y = 15.0

# --- Canvas Pixel Dimensions (like raster width/height in px) ---
CANVAS_WIDTH = 600
CANVAS_HEIGHT = 500

# --- Camera Crop Window (coordinate-space crop, like cropping a canvas) ---
VIEW_WIDTH = 800
VIEW_HEIGHT = 200
VIEW_OFFSET_X = 0
VIEW_OFFSET_Y = -30

# --- Attractor Translation ---
OFFSET_X = 0
OFFSET_Y = 0

# --- Camera Crop Controls ---
VIEW_WIDTH = 300
VIEW_HEIGHT = 600

# --- Rotation ---
AZIM = 135
ELEV = 25
ROLL = 0

SIM_DURATION = 1200
TRANSIENT_STEPS = 800

LINE_WIDTH = 2.4

# Colors
WET_COLOR = "#00FFFF"
DRY_START = "#FF00FF"
DRY_END = "#3F007F"

EXPORT_LOCATION = "docs/assets/lorenz_gradient.svg"


# --- LORENZ SYSTEM ---


def lorenz_deriv(state):
    x, y, z = state
    return np.array([SIGMA * (y - x), x * (RHO - z) - y, x * y - BETA * z])


def get_lorenz_rk4():
    dt = 0.015
    total_points = SIM_DURATION + TRANSIENT_STEPS

    state = np.array([1.1, 1.0, 1.05])
    history = np.zeros((total_points, 3))

    for i in range(total_points):
        k1 = lorenz_deriv(state)
        k2 = lorenz_deriv(state + k1 * dt / 2)
        k3 = lorenz_deriv(state + k2 * dt / 2)
        k4 = lorenz_deriv(state + k3 * dt)

        state = state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

        history[i] = state

    return history[TRANSIENT_STEPS:]


# --- PROJECTION ---


def project_points(history):

    xs, ys, zs = history[:, 0], history[:, 1], history[:, 2]

    a = np.radians(AZIM)
    e = np.radians(ELEV)
    r = np.radians(ROLL)

    px = -xs * np.sin(a) + ys * np.cos(a)

    py = -xs * np.cos(a) * np.sin(e) - ys * np.sin(a) * np.sin(e) + zs * np.cos(e)

    if ROLL != 0:
        px_new = px * np.cos(r) - py * np.sin(r)
        py_new = px * np.sin(r) + py * np.cos(r)

        px, py = px_new, py_new

    # center attractor
    px -= np.mean(px)
    py -= np.mean(py)

    # manual stretch
    px = px * SCALE_X
    py = py * SCALE_Y

    # translation
    px += OFFSET_X
    py += OFFSET_Y

    return px, py


# --- SVG GENERATION ---


def generate_logo(filename=EXPORT_LOCATION):

    history = get_lorenz_rk4()

    px, py = project_points(history)

    # camera crop window
    left = -VIEW_WIDTH / 2 + VIEW_OFFSET_X
    top = -VIEW_HEIGHT / 2 + VIEW_OFFSET_Y

    d = draw.Drawing(
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        viewBox=f"{left} {top} {VIEW_WIDTH} {VIEW_HEIGHT}",
        preserveAspectRatio="none",  # <-- critical line
    )

    total_anim_duration = 8.0
    draw_phase = total_anim_duration / 2.0

    color_fade_delay = 0.15
    color_fade_speed = 0.4

    c_start = np.array(
        [int(DRY_START[1:3], 16), int(DRY_START[3:5], 16), int(DRY_START[5:7], 16)]
    )

    c_end = np.array(
        [int(DRY_END[1:3], 16), int(DRY_END[3:5], 16), int(DRY_END[5:7], 16)]
    )

    N = len(px)

    dists = np.sqrt(np.diff(px) ** 2 + np.diff(py) ** 2)
    cumulative_len = np.insert(np.cumsum(dists), 0, 0)

    total_len = max(cumulative_len[-1], 1e-6)

    group = draw.Group(
        stroke_width=LINE_WIDTH,
        stroke_linecap="round",
        fill="none",
    )

    d.append(group)

    for i in range(N - 1):
        t = i / (N - 1)

        rgb = (c_start * (1 - t) + c_end * t).astype(int)

        target_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        start_time = (cumulative_len[i] / total_len) * draw_phase
        fade_time = start_time + color_fade_delay
        disappear_time = draw_phase + start_time

        p = draw.Path()

        p.M(px[i], -py[i])
        p.L(px[i + 1], -py[i + 1])

        group.append(p)

        p.append_anim(
            draw.Animate(
                "stroke-opacity",
                total_anim_duration,
                values="0;1;0",
                keyTimes=f"0;{start_time / total_anim_duration};{disappear_time / total_anim_duration}",
                calcMode="discrete",
                repeatCount="indefinite",
            )
        )

        p.append_anim(
            draw.Animate(
                "stroke",
                total_anim_duration,
                values=f"{WET_COLOR};{WET_COLOR};{target_hex};{target_hex}",
                keyTimes=f"0;{fade_time / total_anim_duration};{(fade_time + color_fade_speed) / total_anim_duration};1",
                repeatCount="indefinite",
            )
        )

    d.save_svg(filename)

    print("SVG generated successfully")


if __name__ == "__main__":
    generate_logo()
