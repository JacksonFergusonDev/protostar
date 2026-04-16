import drawsvg as draw
import numpy as np

# --- GLOBAL CONFIGURATION ---
SIGMA, BETA, RHO = 10.0, 8 / 3, 28.0
SIM_DURATION = 1200
TRANSIENT_STEPS = 800
LINE_WIDTH = 2.4

# Colors
WET_COLOR = "#00FFFF"
DRY_START = "#FF00FF"
DRY_END = "#3F007F"


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


def project_points(history, azim=135, elev=25, roll=0, scale_x=5.0, scale_y=15.0):
    xs, ys, zs = history[:, 0], history[:, 1], history[:, 2]
    a, e, r = np.radians(azim), np.radians(elev), np.radians(roll)

    px = -xs * np.sin(a) + ys * np.cos(a)
    py = -xs * np.cos(a) * np.sin(e) - ys * np.sin(a) * np.sin(e) + zs * np.cos(e)

    if roll != 0:
        px_new = px * np.cos(r) - py * np.sin(r)
        py_new = px * np.sin(r) + py * np.cos(r)
        px, py = px_new, py_new

    px -= np.mean(px)
    py -= np.mean(py)
    return px * scale_x, py * scale_y


def generate_svg(filename, step=2, precision=1):
    history = get_lorenz_rk4()
    px, py = project_points(history)

    # Subsampling
    px = px[::step]
    py = py[::step]

    # Viewbox setup
    view_w, view_h = 300, 600
    off_x, off_y = 0, -30
    left = -view_w / 2 + off_x
    top = -view_h / 2 + off_y

    d = draw.Drawing(
        600,
        500,
        viewBox=f"{left} {top} {view_w} {view_h}",
        preserveAspectRatio="none",
        shape_rendering="geometricPrecision",
    )

    total_duration = 6.0
    css_content = f"""
    <style>
        @keyframes paintFlow {{
            0%   {{ stroke: {WET_COLOR}; stroke-opacity: 0; }}
            1%   {{ stroke: {WET_COLOR}; stroke-opacity: 1; }}
            15%  {{ stroke: {WET_COLOR}; stroke-opacity: 1; }}
            40%  {{ stroke: var(--dry-color); stroke-opacity: 1; }}
            70%  {{ stroke-opacity: 1; }}
            90%  {{ stroke-opacity: 0; }}
            100% {{ stroke-opacity: 0; }}
        }}
        .paint-segment {{
            fill: none; stroke-width: {LINE_WIDTH};
            stroke-linecap: round; stroke-opacity: 0;
            animation: paintFlow {total_duration}s linear infinite;
        }}
    </style>
    """
    d.append(draw.Raw(css_content))

    n_segments = len(px) - 1
    c_start = np.array(
        [int(DRY_START[1:3], 16), int(DRY_START[3:5], 16), int(DRY_START[5:7], 16)]
    )
    c_end = np.array(
        [int(DRY_END[1:3], 16), int(DRY_END[3:5], 16), int(DRY_END[5:7], 16)]
    )

    for i in range(n_segments):
        delay = (i / n_segments) * (total_duration * 0.7)
        t = i / n_segments
        rgb = (c_start * (1 - t) + c_end * t).astype(int)
        target_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        p = draw.Path(
            class_="paint-segment",
            style=f"animation-delay: {delay:.4f}s; --dry-color: {target_hex};",
        )

        p.M(round(px[i], precision), round(-py[i], precision))
        p.L(round(px[i + 1], precision), round(-py[i + 1], precision))
        d.append(p)

    d.save_svg(filename)
    print(f"Exported: {filename} (Segments: {n_segments})")


if __name__ == "__main__":
    # 1. Web-Optimized (Subsampled + Lower Precision)
    generate_svg("docs/assets/lorenz_css.svg", step=2, precision=1)

    # 2. High Quality (Hero Page)
    # Removing subsampling (step=1) and increasing precision to 3 decimal places
    generate_svg("docs/assets/lorenz_high_res.svg", step=1, precision=3)
