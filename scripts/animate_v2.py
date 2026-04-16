"""
Lorenz Attractor - WebM (VP9) + MP4 (H.264) renderer
"Wet brush drying" colour animation: cyan → magenta → deep purple.

Usage
-----
Full quality (slow, high bitrate):
    python lorenz_render.py

Test render (fast, low resolution - good for checking layout/timing):
    python lorenz_render.py --test

Custom output directory:
    python lorenz_render.py --outdir /path/to/dir
"""

import argparse
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.collections as mc
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter

# ---------------------------------------------------------------------------
# 1.  PARAMETERS
# ---------------------------------------------------------------------------
SIGMA, BETA, RHO = 15.0, 8 / 3, 28.0

# Attractor stretch applied during projection
SCALE_X = 5.0
SCALE_Y = 15.0

# Camera angles  (degrees)
AZIM = 135
ELEV = 25
ROLL = 0

# Attractor translation in coordinate space
OFFSET_X = 0
OFFSET_Y = 0

# ---------------------------------------------------------------------------
# Canvas / viewport
# ---------------------------------------------------------------------------
STRETCH_RATIO = 2.4  # x pixels-per-coord  /  y pixels-per-coord
CANVAS_HEIGHT_PX = 800  # fixed output height (full quality)
CANVAS_PAD_PX = 8  # empty pixels on each of the four edges

# ---------------------------------------------------------------------------
# Animation timing
# ---------------------------------------------------------------------------
FPS = 60
TOTAL_ANIM_SECS = 8.0
DRAW_PHASE_SECS = TOTAL_ANIM_SECS / 2.0  # 4 s to draw, 4 s to erase

# "Drying" timing - seconds after a segment first lights up
COLOR_FADE_DELAY = 0.15  # stays pure cyan for this long
COLOR_FADE_SPEED = 0.40  # then fades to dry colour over this many seconds

LINE_WIDTH = 1.8  # matplotlib points

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
BACKGROUND_COLOR = "black"
WET_COLOR = np.array([0, 255, 255], dtype=float)  # #00FFFF  cyan
DRY_START = np.array([255, 0, 255], dtype=float)  # #FF00FF  magenta
DRY_END = np.array([63, 0, 127], dtype=float)  # #3F007F  deep purple

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path("docs/assets")
STEM = "lorenz_gradient"
TEMP_RAW = Path("/tmp/lorenz_raw.mp4")

# ---------------------------------------------------------------------------
# Simulation quality presets
#   dt          - RK4 step size (smaller = smoother curve, more segments)
#   sim_time    - Lorenz time units to simulate  (18 ≈ ~2 full laps of the
#                 attractor at dt 0.001; identical for both presets so the
#                 animation shape is the same, just coarser in test mode)
#   transient_t - Lorenz time to discard as transient (warm-up)
# ---------------------------------------------------------------------------
PRESETS = {
    "full": {"dt": 0.001, "sim_time": 18.0, "transient_t": 12.0},
    "test": {"dt": 0.005, "sim_time": 18.0, "transient_t": 12.0},
}


# ---------------------------------------------------------------------------
# 2.  LORENZ SIMULATION
# ---------------------------------------------------------------------------


def lorenz_deriv(state: np.ndarray) -> np.ndarray:
    x, y, z = state
    return np.array(
        [
            SIGMA * (y - x),
            x * (RHO - z) - y,
            x * y - BETA * z,
        ]
    )


def get_lorenz_rk4(dt: float, sim_time: float, transient_t: float) -> np.ndarray:
    n_sim = round(sim_time / dt)
    n_tr = round(transient_t / dt)
    total = n_sim + n_tr
    state = np.array([1.1, 1.0, 1.05])
    history = np.zeros((total, 3))
    for i in range(total):
        k1 = lorenz_deriv(state)
        k2 = lorenz_deriv(state + k1 * dt / 2)
        k3 = lorenz_deriv(state + k2 * dt / 2)
        k4 = lorenz_deriv(state + k3 * dt)
        state = state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        history[i] = state
    print(f"  {n_sim} segments  (dt={dt}, sim_time={sim_time})")
    return history[n_tr:]


# ---------------------------------------------------------------------------
# 3.  PROJECTION  (identical maths to original SVG script)
# ---------------------------------------------------------------------------


def project_points(history: np.ndarray):
    xs, ys, zs = history[:, 0], history[:, 1], history[:, 2]
    a = np.radians(AZIM)
    e = np.radians(ELEV)
    r = np.radians(ROLL)

    px = -xs * np.sin(a) + ys * np.cos(a)
    py = -xs * np.cos(a) * np.sin(e) - ys * np.sin(a) * np.sin(e) + zs * np.cos(e)

    if ROLL != 0:
        px, py = (px * np.cos(r) - py * np.sin(r), px * np.sin(r) + py * np.cos(r))

    px -= np.mean(px)
    py -= np.mean(py)
    px = px * SCALE_X + OFFSET_X
    py = py * SCALE_Y + OFFSET_Y
    return px, -py  # flip Y to match SVG screen convention


# ---------------------------------------------------------------------------
# 4.  CANVAS AUTO-SIZING  (shrink-wrap + preserve SVG stretch ratio)
# ---------------------------------------------------------------------------


def compute_canvas(px: np.ndarray, py: np.ndarray, height_px: int, pad_px: int):
    """
    Returns (canvas_width_px, xlim, ylim) such that:
      - Canvas height == height_px
      - pad_px pixels of black space on every edge
      - Pixel-per-coord ratio in x vs y == STRETCH_RATIO  (faithfully
        reproduces the non-uniform stretch of the original SVG)
    """
    x_min, x_max = px.min(), px.max()
    y_min, y_max = py.min(), py.max()
    x_span = x_max - x_min
    y_span = y_max - y_min

    # pixels-per-coord derived from the fixed canvas height
    ppc_y = (height_px - 2 * pad_px) / y_span
    ppc_x = ppc_y * STRETCH_RATIO

    # canvas width: data footprint + padding on both sides
    raw_w = x_span * ppc_x + 2 * pad_px
    canvas_w = int(raw_w)
    if canvas_w % 2:  # codec requires even width
        canvas_w += 1

    # convert pixel padding back to coordinate units for xlim / ylim
    pad_cx = pad_px / ppc_x
    pad_cy = pad_px / ppc_y

    xlim = (x_min - pad_cx, x_max + pad_cx)
    ylim = (y_min - pad_cy, y_max + pad_cy)

    return canvas_w, xlim, ylim


# ---------------------------------------------------------------------------
# 5.  PRE-COMPUTE PER-SEGMENT TIMING & DRY-COLOUR ARRAYS
# ---------------------------------------------------------------------------


def build_segment_data(px: np.ndarray, py: np.ndarray):
    N = len(px)
    dists = np.hypot(np.diff(px), np.diff(py))
    cumlen = np.concatenate([[0], np.cumsum(dists)])
    total_len = max(cumlen[-1], 1e-6)

    t_norm = np.arange(N - 1) / max(N - 2, 1)  # 0 → 1 along arc length

    start_t = (cumlen[:-1] / total_len) * DRAW_PHASE_SECS
    disapp_t = DRAW_PHASE_SECS + start_t

    # Interpolate DRY_START → DRY_END along path  [0..1 float]
    dry_rgb = (
        DRY_START[None] * (1 - t_norm[:, None]) + DRY_END[None] * t_norm[:, None]
    ) / 255.0

    # Shape (N-1, 2, 2) - pairs of (x,y) endpoints for LineCollection
    seg_pts = np.stack(
        [np.column_stack([px[:-1], py[:-1]]), np.column_stack([px[1:], py[1:]])],
        axis=1,
    )

    return seg_pts, start_t, disapp_t, dry_rgb


# ---------------------------------------------------------------------------
# 6.  PER-FRAME RGBA COMPUTATION
# ---------------------------------------------------------------------------


def compute_frame_colors(
    t_now: float,
    start_t: np.ndarray,
    disapp_t: np.ndarray,
    dry_rgb: np.ndarray,
) -> np.ndarray:
    """
    Returns RGBA array (N-1, 4) for the current animation time t_now (s).

    Per-segment timing (mirrors the original SVG Animate logic):
      before start_t      → invisible (alpha 0)
      at start_t          → appears as WET_COLOR, alpha 1
      + COLOR_FADE_DELAY  → begins fading to dry_rgb over COLOR_FADE_SPEED s
      approaching disapp_t → fades out over 0.25 s
    """
    t = t_now % TOTAL_ANIM_SECS
    N = len(start_t)
    rgba = np.zeros((N, 4), dtype=float)

    alive = (t >= start_t) & (t < disapp_t)
    if not np.any(alive):
        return rgba

    idx = np.where(alive)[0]
    age = t - start_t[idx]

    # Wet → dry colour blend
    fade_start = COLOR_FADE_DELAY
    fade_end = COLOR_FADE_DELAY + COLOR_FADE_SPEED
    fade_frac = np.clip((age - fade_start) / (fade_end - fade_start + 1e-9), 0.0, 1.0)
    wet = WET_COLOR[None] / 255.0
    rgb = wet * (1 - fade_frac[:, None]) + dry_rgb[idx] * fade_frac[:, None]

    # Opacity: fast fade-in → hold → gentle fade-out near disapp_t
    fade_in_dur = 0.03
    fade_out_dur = 0.25
    time_left = disapp_t[idx] - t
    opacity = np.clip(age / fade_in_dur, 0.0, 1.0)
    opacity = np.minimum(opacity, np.clip(time_left / fade_out_dur, 0.0, 1.0))

    rgba[idx, :3] = rgb
    rgba[idx, 3] = opacity
    return rgba


# ---------------------------------------------------------------------------
# 7.  RENDER  (matplotlib → lossless PNG-frame intermediate)
# ---------------------------------------------------------------------------


def render_raw(
    seg_pts: np.ndarray,
    start_t: np.ndarray,
    disapp_t: np.ndarray,
    dry_rgb: np.ndarray,
    canvas_w: int,
    canvas_h: int,
    xlim: tuple,
    ylim: tuple,
):
    total_frames = round(TOTAL_ANIM_SECS * FPS)
    DPI = 100

    fig, ax = plt.subplots(
        figsize=(canvas_w / DPI, canvas_h / DPI),
        dpi=DPI,
    )
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)
    ax.axis("off")
    # Zero margins: the axes tile fills the entire figure pixel-for-pixel.
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # Do NOT call set_aspect('equal').  With the figure sized to the
    # desired canvas_w x canvas_h and no margins, matplotlib maps
    # the coordinate range to the pixel range non-uniformly, exactly
    # replicating SVG's preserveAspectRatio="none".
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)

    lc = mc.LineCollection(
        seg_pts,  # pyright: ignore[reportArgumentType]
        linewidths=LINE_WIDTH,
        capstyle="round",
        joinstyle="round",
        antialiased=True,
    )
    ax.add_collection(lc)

    writer = FFMpegWriter(
        fps=FPS,
        codec="png",
        extra_args=["-pix_fmt", "rgba"],
        metadata={"title": "Lorenz Attractor", "artist": "Protostar"},
    )

    print(
        f"  Rendering {total_frames} frames  ({canvas_w}x{canvas_h} px @ {FPS} fps) …"
    )
    TEMP_RAW.parent.mkdir(parents=True, exist_ok=True)

    with writer.saving(fig, str(TEMP_RAW), dpi=DPI):
        for frame_idx in range(total_frames):
            rgba = compute_frame_colors(frame_idx / FPS, start_t, disapp_t, dry_rgb)
            lc.set_color(rgba)  # pyright: ignore[reportArgumentType]
            writer.grab_frame()
            if frame_idx % FPS == 0:
                print(
                    f"    frame {frame_idx:4d}/{total_frames}  "
                    f"({100 * frame_idx / total_frames:.0f}%)"
                )

    plt.close(fig)
    print("  Raw frames complete.")


# ---------------------------------------------------------------------------
# 8.  ENCODE  WebM (VP9, two-pass) and MP4 (H.264)
# ---------------------------------------------------------------------------


def encode(output_dir: Path, test: bool):
    output_dir.mkdir(parents=True, exist_ok=True)
    webm_out = output_dir / f"{STEM}.webm"
    mp4_out = output_dir / f"{STEM}.mp4"

    if test:
        # Single-pass, fast settings — just for eyeballing layout/timing
        print("  Encoding WebM (test, fast) …")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(TEMP_RAW),
                "-c:v",
                "libvpx-vp9",
                "-b:v",
                "0",
                "-crf",
                "35",
                "-deadline",
                "realtime",
                "-cpu-used",
                "8",
                "-pix_fmt",
                "yuv420p",
                str(webm_out),
            ],
            check=True,
            stderr=subprocess.DEVNULL,
        )

        print("  Encoding MP4 (test, fast) …")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(TEMP_RAW),
                "-c:v",
                "libx264",
                "-crf",
                "28",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(mp4_out),
            ],
            check=True,
            stderr=subprocess.DEVNULL,
        )

    else:
        # Two-pass VP9: quality-constrained (b:v 0 + crf), maximum effort
        # -deadline best / -cpu-used 0 = highest quality, slower encode
        vp9_base = [
            "ffmpeg",
            "-y",
            "-i",
            str(TEMP_RAW),
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            "0",
            "-crf",
            "18",
            "-deadline",
            "best",
            "-cpu-used",
            "0",
            "-row-mt",
            "1",
            "-tile-columns",
            "2",
            "-auto-alt-ref",
            "1",
            "-lag-in-frames",
            "25",
            "-pix_fmt",
            "yuv420p",
        ]
        print("  VP9 pass 1 …")
        subprocess.run(
            [*vp9_base, "-pass", "1", "-an", "-f", "webm", "/dev/null"],
            check=True,
            stderr=subprocess.DEVNULL,
        )
        print("  VP9 pass 2 …")
        subprocess.run([*vp9_base, "-pass", "2", str(webm_out)], check=True)
        print(f"  WebM → {webm_out}")

        # H.264 MP4: visually lossless, broadly compatible, streaming-ready
        print("  Encoding MP4 …")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(TEMP_RAW),
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-preset",
                "slow",
                "-profile:v",
                "high",
                "-level",
                "4.1",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(mp4_out),
            ],
            check=True,
        )
        print(f"  MP4  → {mp4_out}")

    TEMP_RAW.unlink(missing_ok=True)
    for f in Path(".").glob("ffmpeg2pass*"):
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 9.  MAIN
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Render Lorenz attractor animation to WebM + MP4"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Fast low-quality test render (half resolution, fast encode)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory  (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    preset = PRESETS["test"] if args.test else PRESETS["full"]
    canvas_h = CANVAS_HEIGHT_PX // 2 if args.test else CANVAS_HEIGHT_PX
    label = "TEST (half-res, fast encode)" if args.test else "FULL QUALITY"

    print(f"\n=== Lorenz renderer — {label} ===\n")

    print("1/4  Simulating …")
    history = get_lorenz_rk4(**preset)
    px, py = project_points(history)

    print("2/4  Computing canvas …")
    canvas_w, xlim, ylim = compute_canvas(px, py, canvas_h, CANVAS_PAD_PX)
    print(
        f"     {canvas_w}x{canvas_h} px  |  "
        f"xlim=({xlim[0]:.1f}, {xlim[1]:.1f})  "
        f"ylim=({ylim[0]:.1f}, {ylim[1]:.1f})"
    )

    seg_pts, start_t, disapp_t, dry_rgb = build_segment_data(px, py)

    print("3/4  Rendering frames …")
    render_raw(seg_pts, start_t, disapp_t, dry_rgb, canvas_w, canvas_h, xlim, ylim)

    print("4/4  Encoding …")
    encode(args.outdir, test=args.test)

    print(f"\nDone!  Output in: {args.outdir}/")


if __name__ == "__main__":
    main()
