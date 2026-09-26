"""Ultra-fast, deterministic terminal session recorder for Protostar demo assets.

Generates standard asciicast v2 (.cast) files from scripted terminal sessions
without requiring a headless browser or ffmpeg.
"""

from __future__ import annotations

import argparse
import builtins
import codecs
import contextlib
import fcntl
import json
import os
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time
import types
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import SNAPSHOTS_DIR, VENV_BIN

DEFAULT_COLS = 105
DEFAULT_ROWS = 30
DEFAULT_WORKSPACE = "/tmp/demo_project"
DEFAULT_SCROLL_DELAY = 0.075  # Seconds per line during pager scrolling
CLEAR_SCREEN_MARKERS = ("\x1b[3J\x1b[H\x1b[2J", "\x1b[H\x1b[2J", "\x1b[2J")


@dataclass(frozen=True)
class DemoTrialResult:
    """Summary metrics of a single demo recording trial."""

    trial: int
    duration_s: float
    events: int
    status: str


# Single source of truth for demo colors: consumed by asciinema-player (docs) and agg (GIFs)
DEFAULT_THEME: dict[str, str] = {
    "fg": "#cdd6f4",
    "bg": "#0a0f1f",
    "palette": "#1e1e2e:#f38ba8:#a6e3a1:#f9e2af:#89b4fa:#cba6f7:#22d3ee:#bac2de:#585b70:#f38ba8:#a6e3a1:#f9e2af:#89b4fa:#f5c2e7:#38bdf8:#a6adc8",
}


def set_winsize(fd: int, rows: int, cols: int) -> None:
    """Sets the terminal window dimensions on a file descriptor."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)  # type: ignore[attr-defined, unused-ignore]


def get_fixture_line_count(
    fixture_template: str, relative_path: str = "pyproject.toml"
) -> int:
    """Extracts the exact line count of a generated file from tests/snapshots."""
    fixture_file = SNAPSHOTS_DIR / fixture_template / relative_path
    if fixture_file.exists():
        return len(fixture_file.read_text(encoding="utf-8").splitlines())
    return 60


class PTYSession:
    """Manages an interactive PTY session and records output to asciicast v2 format."""

    def __init__(
        self,
        workspace: str = DEFAULT_WORKSPACE,
        cols: int = DEFAULT_COLS,
        rows: int = DEFAULT_ROWS,
    ) -> None:
        self.workspace = workspace
        self.cols = cols
        self.rows = rows
        self.events: list[list[float | str]] = []
        self.start_time: float = 0.0
        self.recording: bool = False
        self.master_fd: int = -1
        self.slave_fd: int = -1
        self.proc: subprocess.Popen[bytes] | None = None
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def start(self) -> None:
        """Spawns the background shell inside a pseudo-terminal."""
        # Ensure fresh clean workspace
        shutil.rmtree(self.workspace, ignore_errors=True)
        os.makedirs(self.workspace, exist_ok=True)

        self.master_fd, self.slave_fd = pty.openpty()  # type: ignore[attr-defined, unused-ignore]
        set_winsize(self.master_fd, self.rows, self.cols)
        set_winsize(self.slave_fd, self.rows, self.cols)

        env = os.environ.copy()
        # Record the product palette and an interactive pager regardless of the
        # invoking agent or shell's output preferences.
        env.pop("NO_COLOR", None)
        env["PAGER"] = "less"
        env["BAT_PAGER"] = "less"
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["BAT_PAGING"] = "always"
        env["BAT_THEME"] = "Catppuccin Mocha"
        env["LINES"] = str(self.rows)
        env["COLUMNS"] = str(self.cols)

        # Inherit host venv bin and tools on PATH
        venv_bin = str(VENV_BIN)
        env["PATH"] = (
            f"{venv_bin}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        )

        self.proc = subprocess.Popen(
            ["/bin/zsh", "-f"],
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            close_fds=True,
            env=env,
            cwd=self.workspace,
            start_new_session=True,
        )
        os.close(self.slave_fd)
        self.slave_fd = -1

        # Perform silent bootstrap (unset host venv, enforce local venv priority, load direnv & starship hooks)
        self._silent_write(f'export PATH="{venv_bin}:$PATH"\n')
        self._drain(0.05)
        self._silent_write(f"alias protostar='{venv_bin}/protostar'\n")
        self._drain(0.05)
        self._silent_write("unset VIRTUAL_ENV\n")
        self._drain(0.05)
        self._silent_write('export BAT_THEME="Catppuccin Mocha"\n')
        self._drain(0.05)
        self._silent_write('export COLORTERM="truecolor"\n')
        self._drain(0.05)
        self._silent_write(
            "git config --global --add safe.directory '*' 2>/dev/null || true\n"
        )
        self._drain(0.05)
        self._silent_write("source <(direnv hook zsh)\n")
        self._drain(0.15)
        self._silent_write("source <(starship init zsh --print-full-init)\n")
        self._drain(0.3)
        self._silent_write('eval "$(/opt/homebrew/bin/zsh-patina activate)"\n')
        self._drain(0.1)
        self._silent_write(f"cd {self.workspace}\n")
        self._drain(0.1)
        self._silent_write(f'export PATH="{venv_bin}:$PATH"\n')
        self._silent_write(f"alias protostar='{venv_bin}/protostar'\n")
        self._drain(0.05)

        # Starship can finish drawing the pre-recording prompt after the last
        # bootstrap command. Drain it before collecting the clean redraw.
        self._drain(0.4)

        # Trigger native shell clear-and-redraw via form-feed (Ctrl-L / \x0c).
        # This completely avoids typing or echoing the command word "clear",
        # prevents subprocess execution latency, and eliminates zsh's
        # PROMPT_EOL_MARK inverted '%' line-fill artifacts.
        self._silent_write("\x0c")
        redraw_output = self._drain(0.4)
        screen_start = next(
            (
                redraw_output.find(marker)
                for marker in CLEAR_SCREEN_MARKERS
                if redraw_output.find(marker) >= 0
            ),
            -1,
        )

        initial_content = (
            redraw_output[screen_start:] if screen_start >= 0 else redraw_output
        )

        if not initial_content.strip():
            raise RuntimeError(
                "Failed to capture clean prompt redraw for initial demo frame."
            )

        assert "clear" not in initial_content.lower()[:40], (
            f"Command leak detected in initial demo frame: {initial_content!r}"
        )

        self.events.clear()
        self.decoder.reset()
        self.start_time = time.time()
        self.recording = True

        self.events.append([0.0, "o", initial_content])

    def _silent_write(self, data: str) -> None:
        """Writes data directly to master fd without recording timestamps."""
        os.write(self.master_fd, data.encode("utf-8"))

    def _drain(self, timeout: float = 0.05) -> str:
        """Drains output from master fd, records it when active, and returns it."""
        deadline = time.time() + timeout
        output: list[str] = []
        while True:
            remaining = max(0.0, deadline - time.time())
            r, _, _ = select.select([self.master_fd], [], [], remaining)
            if not r:
                break
            try:
                chunk = os.read(self.master_fd, 4096)
                if not chunk:
                    break
                if b"\x1b[6n" in chunk:
                    os.write(self.master_fd, b"\x1b[1;1R")

                decoded = self.decoder.decode(chunk, final=False)
                output.append(decoded)
                if decoded and self.recording:
                    rel_time = round(time.time() - self.start_time, 4)
                    self.events.append([rel_time, "o", decoded])
            except OSError:
                break
        return "".join(output)

    def type(
        self, text: str, char_delay: float = 0.035, post_delay: float = 0.2
    ) -> None:
        """Types text with natural keystroke timing."""
        for char in text:
            os.write(self.master_fd, char.encode("utf-8"))
            self._drain(char_delay)
        if post_delay > 0:
            self._drain(post_delay)

    def enter(self, wait: float = 0.5) -> None:
        """Sends an Enter keypress and waits for output."""
        os.write(self.master_fd, b"\n")
        if wait > 0:
            self._drain(wait)

    def wait_for(
        self,
        markers: str | tuple[str, ...],
        timeout: float = 10.0,
        post_wait: float = 0.4,
    ) -> str:
        """Drains output until any specified marker is observed, then drains post_wait.

        Args:
            markers: Substring or tuple of substrings to look for in the output stream.
            timeout: Maximum seconds to wait before raising TimeoutError.
            post_wait: Additional seconds to drain after the marker is detected
                (useful for allowing shell prompt redraws to settle).

        Returns:
            The accumulated decoded output drained during this operation.

        Raises:
            TimeoutError: If none of the markers appear before the timeout expires.
        """
        targets = (markers,) if isinstance(markers, str) else markers
        deadline = time.time() + timeout
        accumulated: list[str] = []

        while time.time() < deadline:
            remaining = max(0.01, min(0.15, deadline - time.time()))
            chunk_str = self._drain(remaining)
            if chunk_str:
                accumulated.append(chunk_str)
                full_text = "".join(accumulated)
                if any(m in full_text for m in targets):
                    if post_wait > 0:
                        extra = self._drain(post_wait)
                        accumulated.append(extra)
                    return "".join(accumulated)

        raise TimeoutError(
            f"Timed out after {timeout}s waiting for markers: {targets!r}. "
            f"Received output: {''.join(accumulated)!r}"
        )

    def key(self, key_bytes: bytes, wait: float = 0.3) -> None:
        """Sends raw key sequence (e.g. arrow keys, space, escape)."""
        os.write(self.master_fd, key_bytes)
        self._drain(wait)

    def down(self, count: int = 1, wait: float = 0.1) -> None:
        """Sends Down arrow key sequence."""
        for _ in range(count):
            os.write(self.master_fd, b"\x1b[B")
            self._drain(wait)

    def scroll_pager(
        self, lines: int = 15, delay: float = DEFAULT_SCROLL_DELAY
    ) -> None:
        """Scrolls down inside a pager (bat/less) using standard vi/less navigation keys."""
        for _ in range(lines):
            os.write(self.master_fd, b"j")
            self._drain(delay)

    def space(self, wait: float = 0.4) -> None:
        """Sends Space keypress."""
        os.write(self.master_fd, b" ")
        self._drain(wait)

    def sleep(self, seconds: float) -> None:
        """Pauses the timeline while continuing to drain any background stream output."""
        self._drain(seconds)

    def __enter__(self) -> PTYSession:
        """Starts the session when entering context."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: builtins.type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Ensures the session and all child processes are terminated on exit."""
        self.close()

    def close(self) -> None:
        """Terminates the shell and all child processes, and closes open file descriptors."""
        self.recording = False
        if self.proc is not None and self.proc.poll() is None:
            pid = self.proc.pid
            with contextlib.suppress(Exception):
                self._silent_write("q\nexit\n")
                self._drain(0.1)

            if self.proc.poll() is None:
                # Terminate the entire process group
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(pid, signal.SIGTERM)
                try:
                    self.proc.wait(timeout=0.5)
                except (subprocess.TimeoutExpired, Exception):
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.killpg(pid, signal.SIGKILL)
                    with contextlib.suppress(Exception):
                        self.proc.wait(timeout=0.5)

        if self.master_fd >= 0:
            with contextlib.suppress(OSError):
                os.close(self.master_fd)
            self.master_fd = -1

    def save(self, output_path: str | Path) -> None:
        """Closes the shell and saves the recorded events to an asciicast v2 file."""
        self.close()
        if self.events:
            total_duration = round(time.time() - self.start_time, 4)
            if total_duration > float(self.events[-1][0]):
                self.events.append([total_duration, "o", ""])

        header = {
            "version": 2,
            "width": self.cols,
            "height": self.rows,
            "timestamp": int(self.start_time),
            "env": {
                "SHELL": "/bin/zsh",
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
            },
            "theme": DEFAULT_THEME,
        }

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(json.dumps(header) + "\n")
            for ev in self.events:
                f.write(json.dumps(ev) + "\n")


MAX_SCROLL_LINES = 32  # Maximum lines to scroll during demo previews


def inspect_project_file(
    session: PTYSession,
    template: str,
    target_file: str = "pyproject.toml",
    scroll_delay: float = DEFAULT_SCROLL_DELAY,
    max_scroll: int = MAX_SCROLL_LINES,
) -> None:
    """Executes the standard post-initialization inspection with eza and bat.

    Dynamically calculates the exact number of lines to scroll through bat
    based on the total line count in tests/snapshots/<template>/<target_file>,
    capped at max_scroll for demo brevity and pacing.
    """
    session.sleep(0.4)
    session.type(
        "eza --tree --git-ignore --all --icons", char_delay=0.03, post_delay=0.2
    )
    session.enter(wait=2.2)

    session.type(f"bat {target_file}", char_delay=0.03, post_delay=0.2)
    session.enter(wait=0.3)
    session.sleep(0.8)  # Initial pause to view file header

    # Calculate lines to scroll (capped for crisp demo pacing)
    total_lines = get_fixture_line_count(template, target_file)
    visible_lines = max(1, session.rows - 5)
    needed_lines = max(5, total_lines - visible_lines + 4)
    lines_to_scroll = min(needed_lines, max_scroll)

    session.scroll_pager(lines=lines_to_scroll, delay=scroll_delay)
    session.sleep(2.0)  # Hold view at end of file preview


def record_headless(session: PTYSession) -> None:
    """Script for the non-interactive (headless) CLI initialization demo."""
    session.sleep(0.5)
    session.type("protostar init --template cli", char_delay=0.035, post_delay=0.3)
    session.enter(wait=0.0)
    session.wait_for("Project ready.", timeout=12.0, post_wait=0.4)
    session.sleep(0.6)  # Viewing pause after initialization completes

    # Post-generation inspection using cli fixture line metrics
    inspect_project_file(session, template="cli")


def record_wizard(session: PTYSession) -> None:
    """Script for the interactive recipe editor demo using the Astro template."""
    # Textual reads Enter as a carriage return; a bare newline is ctrl+j.
    enter = b"\r"
    shift_tab = b"\x1b[Z"

    session.sleep(0.5)
    session.type("protostar init", char_delay=0.035, post_delay=0.3)
    session.enter(wait=0.0)
    session.wait_for("Build your recipe", timeout=8.0, post_wait=0.6)

    # 1. The template picker has focus: open it and pick "Astro" (after
    #    "No template" and "FastAPI").
    session.key(enter, wait=0.5)
    session.down(count=2, wait=0.25)
    session.key(enter, wait=0.4)
    # The template loads in a worker, and the preview re-plans.
    session.sleep(1.6)

    # 2. Focus wraps backwards from the picker to "Continue".
    session.key(shift_tab, wait=0.5)
    session.key(enter, wait=0.0)
    session.wait_for("COMMANDS & PACKAGES", timeout=15.0, post_wait=0.6)

    # 3. The change review focuses the file tree: step down it to show diffs.
    session.down(count=3, wait=0.5)
    session.sleep(1.2)

    # 4. Focus wraps backwards from the file tree to "Apply".
    session.key(shift_tab, wait=0.5)
    session.key(enter, wait=0.0)
    session.wait_for("Project ready.", timeout=20.0, post_wait=0.4)
    session.sleep(0.6)  # Viewing pause after initialization completes

    # 5. Post-generation inspection using astro fixture line metrics
    inspect_project_file(session, template="astro")


SCENARIOS: dict[str, Callable[[PTYSession], None]] = {
    "headless": record_headless,
    "wizard": record_wizard,
}


def main() -> None:
    """CLI entrypoint for recording terminal demo sessions."""
    parser = argparse.ArgumentParser(
        description="Record Protostar terminal demo sessions."
    )
    parser.add_argument(
        "scenario",
        choices=["headless", "wizard", "all"],
        help="Which demo scenario to record",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output .cast file path (defaults to docs/assets/demo_<scenario>.cast)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Number of recording trials to run, selecting the shortest duration (default: 1)",
    )
    parser.add_argument(
        "--cols", type=int, default=DEFAULT_COLS, help="Terminal width in columns"
    )
    parser.add_argument(
        "--rows", type=int, default=DEFAULT_ROWS, help="Terminal height in rows"
    )

    args = parser.parse_args()
    targets = ["headless", "wizard"] if args.scenario == "all" else [args.scenario]
    trials_count = max(1, args.trials)

    for target in targets:
        out_path = args.output or Path(f"docs/assets/demo_{target}.cast")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if trials_count == 1:
            print(f"🎬 Recording demo '{target}' -> {out_path} ...")
            with PTYSession(cols=args.cols, rows=args.rows) as session:
                SCENARIOS[target](session)
                session.save(out_path)
            duration = float(session.events[-1][0]) if session.events else 0.0
            print(
                f"✔ Recorded '{target}' successfully in {duration:.2f}s "
                f"({len(session.events)} events)."
            )
            continue

        print(
            f"🎬 Recording demo '{target}' ({trials_count} trials requested) -> {out_path} ..."
        )
        trial_results: list[DemoTrialResult] = []
        trial_paths: list[Path] = []

        try:
            for trial_idx in range(1, trials_count + 1):
                tmp_cast = out_path.with_name(
                    f".{out_path.stem}.trial_{trial_idx}.tmp.cast"
                )
                trial_paths.append(tmp_cast)
                print(f"  ↳ [Trial {trial_idx}/{trials_count}] Recording ...")
                try:
                    with PTYSession(cols=args.cols, rows=args.rows) as session:
                        SCENARIOS[target](session)
                        session.save(tmp_cast)
                    duration = float(session.events[-1][0]) if session.events else 0.0
                    event_count = len(session.events)
                    trial_results.append(
                        DemoTrialResult(
                            trial=trial_idx,
                            duration_s=round(duration, 2),
                            events=event_count,
                            status="success",
                        )
                    )
                    print(
                        f"    ✔ Trial {trial_idx} completed in {duration:.2f}s "
                        f"({event_count} events)"
                    )
                except Exception as exc:
                    trial_results.append(
                        DemoTrialResult(
                            trial=trial_idx,
                            duration_s=0.0,
                            events=0,
                            status=f"failed: {exc}",
                        )
                    )
                    print(f"    ✖ Trial {trial_idx} failed: {exc}")

            successful_trials = [t for t in trial_results if t.status == "success"]
            if not successful_trials:
                raise RuntimeError(
                    f"All {trials_count} recording trials failed for demo '{target}'."
                )

            winner = min(successful_trials, key=lambda t: t.duration_s)
            winning_path = out_path.with_name(
                f".{out_path.stem}.trial_{winner.trial}.tmp.cast"
            )
            shutil.move(winning_path, out_path)

            durations = [t.duration_s for t in successful_trials]
            min_duration = min(durations)
            max_duration = max(durations)
            mean_duration = round(sum(durations) / len(durations), 2)
            saved_vs_slowest_s = round(max_duration - min_duration, 2)

            trial_dicts = [
                {
                    "trial": r.trial,
                    "duration_s": r.duration_s,
                    "events": r.events,
                    "status": r.status,
                    **({"winner": True} if r.trial == winner.trial else {}),
                }
                for r in trial_results
            ]

            summary = {
                "scenario": target,
                "trials_requested": trials_count,
                "trials_completed": len(successful_trials),
                "winning_trial": winner.trial,
                "winning_duration_s": winner.duration_s,
                "event_count": winner.events,
                "duration_range_s": [min_duration, max_duration],
                "mean_duration_s": mean_duration,
                "saved_vs_slowest_s": saved_vs_slowest_s,
                "trials": trial_dicts,
                "output_file": str(out_path),
            }

            print(f"\n=== DEMO TRIAL SUMMARY [{target}] ===")
            print(json.dumps(summary, indent=2))
            print("====================================\n")
            print(
                f"✔ Selected trial {winner.trial} ({winner.duration_s:.2f}s) "
                f"saved to {out_path}"
            )
        finally:
            for p in trial_paths:
                if p.exists():
                    p.unlink()


if __name__ == "__main__":
    main()
