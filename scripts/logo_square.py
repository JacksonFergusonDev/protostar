import cairosvg
import drawsvg as draw
import numpy as np

# --- 1. GLOBAL CONFIGURATION ---
# Simulation constants (The "Chaotic" Controls)
SIGMA = 13.0
BETA = 5 / 3
RHO = 20.0  # Increase for more complexity, decrease toward 24 for "cleaner" loops

# Aesthetic Controls
SIM_DURATION = 1000  # Total points to render (Adjust to hide/reveal line ends)
TRANSIENT_STEPS = 5000  # Discarding more ensures we start "deep" in the manifold
LINE_WIDTH = 5
CANVAS_SIZE = 500  # Only used for initial scaling; final canvas is cropped

# Colors & Export
CYAN = "#3D003D"  # "#00FFFF"
MAGENTA = "#003D3D"  # "#FF00FF"
CIRCLE_COLOR = "#FFFFFF"  # Or any color/hex you prefer
EXPORT_LOCATION = "docs/assets/protostar-mark.svg"
PADDING = 20


def lorenz_deriv(state):
    """
    Standard Lorenz system derivatives:
    dx/dt = sigma * (y - x)
    dy/dt = x * (rho - z) - y
    dz/dt = x * y - beta * z
    """
    x, y, z = state
    dx = SIGMA * (y - x)
    dy = x * (RHO - z) - y
    dz = x * y - BETA * z
    return np.array([dx, dy, dz])


def get_lorenz_rk4():
    """Integrates using 4th Order Runge-Kutta for high orbital fidelity."""
    dt = 0.012  # Integration step size
    total_points = SIM_DURATION + TRANSIENT_STEPS

    state = np.array([1.1, 1.0, 1.05])  # Initial condition
    history = np.zeros((total_points, 3))

    for i in range(total_points):
        k1 = lorenz_deriv(state)
        k2 = lorenz_deriv(state + k1 * dt / 2)
        k3 = lorenz_deriv(state + k2 * dt / 2)
        k4 = lorenz_deriv(state + k3 * dt)

        state = state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        history[i] = state

    return (
        history[TRANSIENT_STEPS:, 0],
        history[TRANSIENT_STEPS:, 1],
        history[TRANSIENT_STEPS:, 2],
    )


def project_and_normalize(xs, ys, zs, azim=135, elev=25):
    """Orthographic projection into SVG space."""
    a, e = np.radians(azim), np.radians(elev)
    px = -xs * np.sin(a) + ys * np.cos(a)
    py = -xs * np.cos(a) * np.sin(e) - ys * np.sin(a) * np.sin(e) + zs * np.cos(e)

    margin = 55
    p_min, p_max = np.array([px.min(), py.min()]), np.array([px.max(), py.max()])

    # Maintain aspect ratio while filling the canvas
    scale = (CANVAS_SIZE - 2 * margin) / max(p_max - p_min)
    px = (px - (p_min[0] + p_max[0]) / 2) * scale
    py = (py - (p_min[1] + p_max[1]) / 2) * scale

    return px, py


def generate_logo(svg_filename=EXPORT_LOCATION, png_filename=None):
    # Compute the Lorenz trajectory and project it
    xs, ys, zs = get_lorenz_rk4()
    px, py = project_and_normalize(xs, ys, zs)

    # Convert to drawing coordinates (y downward)
    draw_x = px
    draw_y = -py

    # 1. Calculate the bounding box of the trajectory
    min_x, max_x = np.min(draw_x), np.max(draw_x)
    min_y, max_y = np.min(draw_y), np.max(draw_y)

    path_w = max_x - min_x
    path_h = max_y - min_y

    # 2. Force Square Canvas: Find the larger dimension and set that as our side length
    side_length = max(path_w, path_h) + (2 * PADDING)

    # Create the square drawing
    d = draw.Drawing(side_length, side_length, origin=(0, 0))

    # 3. Centering Logic: Shift coordinates so the path is centered in the square
    # Offset = (Total Square Side / 2) - (Path Center)
    offset_x = (side_length / 2) - ((min_x + max_x) / 2)
    offset_y = (side_length / 2) - ((min_y + max_y) / 2)

    new_draw_x = draw_x + offset_x
    new_draw_y = draw_y + offset_y

    # 4. Setup Gradient
    gradient = draw.LinearGradient(0, 0, side_length, side_length)
    gradient.add_stop(0, CYAN)
    gradient.add_stop(1, MAGENTA)

    # 5. Add the Background Circle
    # Centered in the square, radius reaches the edges.
    bg_circle = draw.Circle(
        cx=side_length / 2,
        cy=side_length / 2,
        r=side_length / 2,
        fill=CIRCLE_COLOR,
        fill_opacity=1.0,  # Ensure it's opaque if you want it to hide the "transparent" background
    )
    d.append(bg_circle)

    # 6. Setup & Append Path (Now renders ON TOP of the circle)
    path = draw.Path(
        stroke=gradient,
        stroke_width=LINE_WIDTH,
        fill="none",
        stroke_linecap="round",
        stroke_linejoin="round",
    )

    path = draw.Path(
        stroke=gradient,
        stroke_width=LINE_WIDTH,
        fill="none",
        stroke_linecap="round",
        stroke_linejoin="round",
    )
    path.M(new_draw_x[0], new_draw_y[0])
    for i in range(1, len(new_draw_x)):
        path.L(new_draw_x[i], new_draw_y[i])

    d.append(path)

    # Save SVG
    d.save_svg(svg_filename)

    # 5. Export specific 192x192 PNG for Favicon
    if png_filename:
        svg_bytes = d.as_svg()
        # cairosvg allows us to force the output dimensions regardless of the SVG internal units
        cairosvg.svg2png(
            bytestring=svg_bytes,
            write_to=png_filename,
            output_width=192,
            output_height=192,
        )
        print(f"192x192 Favicon saved: {png_filename}")

    print(f"Internal Canvas: {side_length:.1f}x{side_length:.1f} (Square)")


if __name__ == "__main__":
    generate_logo(
        svg_filename="docs/assets/protostar-favicon.svg",
        png_filename="docs/assets/protostar-favicon.png",
    )
