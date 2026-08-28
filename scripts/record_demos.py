"""Ultra-fast, deterministic terminal session recorder for Protostar demo assets.

Generates standard asciicast v2 (.cast) files from scripted terminal sessions
without requiring a headless browser or ffmpeg.
"""

from __future__ import annotations

import argparse
import codecs
import contextlib
import fcntl
import json
import os
import pty
import select
import shutil
import struct
import subprocess
import termios
import time
from collections.abc import Callable
from pathlib import Path

DEFAULT_COLS = 105
DEFAULT_ROWS = 30
DEFAULT_WORKSPACE = "/tmp/demo_project"
DEFAULT_SCROLL_DELAY = 0.075  # Seconds per line during pager scrolling


def set_winsize(fd: int, rows: int, cols: int) -> None:
    """Sets the terminal window dimensions on a file descriptor."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def get_fixture_line_count(
    fixture_preset: str, relative_path: str = "pyproject.toml"
) -> int:
    """Extracts the exact line count of a generated file from docs/fixtures."""
    repo_root = Path(__file__).resolve().parent.parent
    fixture_file = repo_root / "docs" / "fixtures" / fixture_preset / relative_path
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

        self.master_fd, self.slave_fd = pty.openpty()
        set_winsize(self.master_fd, self.rows, self.cols)
        set_winsize(self.slave_fd, self.rows, self.cols)

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["BAT_PAGING"] = "always"
        env["BAT_THEME"] = "Catppuccin Mocha"
        env["LINES"] = str(self.rows)
        env["COLUMNS"] = str(self.cols)

        # Inherit host venv bin and tools on PATH
        protostar_root = str(Path(__file__).resolve().parent.parent)
        venv_bin = os.path.join(protostar_root, ".venv", "bin")
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
        )
        os.close(self.slave_fd)

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

        # Start recording and clear screen so the initial starship prompt is drawn at t=0
        self.events.clear()
        self.decoder.reset()
        self.start_time = time.time()
        self.recording = True

        self._silent_write("clear\n")
        self._drain(0.4)

    def _silent_write(self, data: str) -> None:
        """Writes data directly to master fd without recording timestamps."""
        os.write(self.master_fd, data.encode("utf-8"))

    def _drain(self, timeout: float = 0.05) -> None:
        """Drains output from master fd and logs events if recording is active."""
        deadline = time.time() + timeout
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
                if decoded and self.recording:
                    rel_time = round(time.time() - self.start_time, 4)
                    self.events.append([rel_time, "o", decoded])
            except OSError:
                break

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
        self._drain(wait)

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

    def save(self, output_path: str | Path) -> None:
        """Closes the shell and saves the recorded events to an asciicast v2 file."""
        self.recording = False
        with contextlib.suppress(Exception):
            self._silent_write("exit\n")
            self._drain(0.2)
            if self.proc:
                self.proc.wait(timeout=1.0)
        with contextlib.suppress(OSError):
            os.close(self.master_fd)

        theme = {
            "fg": "#cdd6f4",
            "bg": "#0a0f1f",
            "palette": "#1e1e2e:#f38ba8:#a6e3a1:#f9e2af:#89b4fa:#cba6f7:#22d3ee:#bac2de:#585b70:#f38ba8:#a6e3a1:#f9e2af:#89b4fa:#f5c2e7:#38bdf8:#a6adc8",
        }

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
            "theme": theme,
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
    preset: str,
    target_file: str = "pyproject.toml",
    scroll_delay: float = DEFAULT_SCROLL_DELAY,
    max_scroll: int = MAX_SCROLL_LINES,
) -> None:
    """Executes the standard post-initialization inspection with eza and bat.

    Dynamically calculates the exact number of lines to scroll through bat
    based on the total line count in docs/fixtures/<preset>/<target_file>,
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
    total_lines = get_fixture_line_count(preset, target_file)
    visible_lines = max(1, session.rows - 5)
    needed_lines = max(5, total_lines - visible_lines + 4)
    lines_to_scroll = min(needed_lines, max_scroll)

    session.scroll_pager(lines=lines_to_scroll, delay=scroll_delay)
    session.sleep(2.0)  # Hold view before exiting pager

    session.type("q", char_delay=0.01, post_delay=0.3)


def record_headless(session: PTYSession) -> None:
    """Script for the non-interactive (headless) CLI initialization demo."""
    session.sleep(0.5)
    session.type("protostar init --template cli", char_delay=0.035, post_delay=0.3)
    session.enter(wait=3.0)

    # Post-generation inspection using cli fixture line metrics
    inspect_project_file(session, preset="cli")


def record_wizard(session: PTYSession) -> None:
    """Script for the interactive wizard CLI initialization demo using the Astro preset."""
    session.sleep(0.5)
    session.type("protostar init", char_delay=0.035, post_delay=0.3)
    session.enter(wait=1.0)

    # 1. Template selection: "Start from a template?" -> Navigate down and select "astro"
    session.sleep(0.5)
    session.down(count=2, wait=0.2)
    session.sleep(0.4)
    session.enter(wait=0.8)

    # 2. Component selection: "Select the components for your new environment:"
    # In the astro preset, defaults (direnv, Ruff, markdownlint, just) are pre-selected.
    # Pause briefly to showcase the pre-checked template tooling, then submit defaults:
    session.sleep(0.8)
    session.enter(wait=0.8)

    # 3. Project Metadata prompts
    # Description (press Enter to skip)
    session.sleep(0.4)
    session.enter(wait=0.5)

    # License (MIT selected by default, press Enter to confirm)
    session.sleep(0.4)
    session.enter(wait=0.5)

    # Author Name (press Enter to accept default or skip)
    session.sleep(0.3)
    session.enter(wait=0.4)

    # Author Email (press Enter to accept default or skip)
    session.sleep(0.3)
    session.enter(wait=0.4)

    # GitHub Username (press Enter to skip)
    session.sleep(0.3)
    session.enter(wait=0.4)

    # Minimum Python version (3.13 default, press Enter to confirm and begin scaffolding)
    session.sleep(0.3)
    session.enter(wait=4.0)

    # 4. Post-generation inspection using astro fixture line metrics
    inspect_project_file(session, preset="astro")


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
        "--cols", type=int, default=DEFAULT_COLS, help="Terminal width in columns"
    )
    parser.add_argument(
        "--rows", type=int, default=DEFAULT_ROWS, help="Terminal height in rows"
    )

    args = parser.parse_args()
    targets = ["headless", "wizard"] if args.scenario == "all" else [args.scenario]

    for target in targets:
        out_path = args.output or Path(f"docs/assets/demo_{target}.cast")
        print(f"🎬 Recording demo '{target}' -> {out_path} ...")
        session = PTYSession(cols=args.cols, rows=args.rows)
        session.start()
        SCENARIOS[target](session)
        session.save(out_path)
        print(f"✔ Recorded '{target}' successfully ({len(session.events)} events).")


if __name__ == "__main__":
    main()
