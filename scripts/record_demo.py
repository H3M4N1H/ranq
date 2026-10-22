"""Record the README demo as an asciicast, then render it to a GIF with agg.

The commands run for real in a pseudo-terminal, so the recording shows Ranq's actual output.
The typing is simulated, and each command is time-lapsed to at most --max-run seconds because
PageSpeed Insights calls take far longer than a README GIF should. Re-run it after a release
that changes the output:

    python scripts/record_demo.py https://nodekraft.tech
    # -> docs/demo.cast, and docs/demo.gif when agg is on PATH

agg: https://github.com/asciinema/agg (single binary, no root needed).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = "\x1b[1;32m$\x1b[0m "
CLEAR = "\x1b[2J\x1b[H"


class Cast:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.clock = 0.0
        self.events: list[tuple[float, str]] = []

    def emit(self, text: str, delay: float = 0.0) -> None:
        self.clock += delay
        self.events.append((round(self.clock, 4), text))

    def type(self, command: str) -> None:
        self.emit(PROMPT, 0.4)
        for ch in command:
            self.emit(ch, 0.045)
        self.emit("\r\n", 0.5)

    def run(self, argv: list[str], cwd: Path, env: dict[str, str]) -> int:
        """Run argv in a pty of the cast's size and record its output with real timing."""
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", self.height, self.width, 0, 0))
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        last = time.monotonic()
        try:
            while True:
                ready, _, _ = select.select([master], [], [], 0.1)
                if not ready:
                    if proc.poll() is not None:
                        break
                    continue
                try:
                    data = os.read(master, 65536)
                except OSError:  # EIO once the child closes the pty
                    break
                if not data:
                    break
                now = time.monotonic()
                self.emit(data.decode("utf-8", "replace"), now - last)
                last = now
        finally:
            os.close(master)
        return proc.wait()

    def squeeze(self, start: int, seconds: float) -> None:
        """Time-lapse events[start:] so they span at most `seconds` (network waits are slow)."""
        if start >= len(self.events):
            return
        base = self.events[start - 1][0] if start else 0.0
        span = self.events[-1][0] - base
        if span <= seconds:
            return
        scale = seconds / span
        for i in range(start, len(self.events)):
            t, text = self.events[i]
            self.events[i] = (round(base + (t - base) * scale, 4), text)
        self.clock = self.events[-1][0]

    def write(self, path: Path, title: str) -> None:
        header = {
            "version": 2,
            "width": self.width,
            "height": self.height,
            "title": title,
            "env": {"TERM": "xterm-256color", "SHELL": "/bin/bash"},
        }
        with path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(header) + "\n")
            for t, text in self.events:
                f.write(json.dumps([t, "o", text]) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", help="site to audit in the demo (use one you own)")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--cast", type=Path, default=ROOT / "docs" / "demo.cast")
    parser.add_argument("--gif", type=Path, default=ROOT / "docs" / "demo.gif")
    parser.add_argument(
        "--max-run", type=float, default=3.5, help="seconds each command may take in the GIF"
    )
    parser.add_argument("--width", type=int, default=100)
    parser.add_argument("--height", type=int, default=30)
    args = parser.parse_args()

    ranq = shutil.which("ranq")
    if not ranq:
        sys.exit("ranq is not on PATH; install it first (pip install -e .)")

    commands = [
        ["audit", args.url, "--max-pages", str(args.max_pages)],
        ["geo", "bots", args.url],
    ]
    env = {
        **os.environ,
        "TERM": "xterm-256color",
        "COLUMNS": str(args.width),
        "LINES": str(args.height),
        "FORCE_COLOR": "1",
    }
    cast = Cast(args.width, args.height)
    with tempfile.TemporaryDirectory() as tmp:  # keeps ranq-report/ out of the repo
        for i, cmd in enumerate(commands):
            if i:
                cast.emit(CLEAR, 5.0)  # time to read the results
            cast.type(" ".join(["ranq", *cmd]))
            start = len(cast.events)
            code = cast.run([ranq, *cmd], Path(tmp), env)
            if code:
                output = "".join(text for _, text in cast.events[start:])
                sys.stderr.write(output[-3000:] + "\n")
                sys.exit(f"`ranq {' '.join(cmd)}` exited with {code}")
            cast.squeeze(start, args.max_run)
    cast.emit(PROMPT, 0.3)
    cast.emit("", 4.0)  # hold the last frame before the GIF loops

    cast.write(args.cast, "Ranq: SEO, AEO and GEO audits from the terminal")
    print(f"wrote {args.cast}")

    agg = shutil.which("agg")
    if not agg:
        print("agg not found; render with: agg --idle-time-limit 6 <cast> <gif>")
        return 0
    subprocess.run(
        [
            agg,
            "--idle-time-limit",
            "6",  # keep the reading pauses; run phases are already squeezed
            "--font-size",
            "15",
            "--theme",
            "monokai",
            "--last-frame-duration",
            "4",
            str(args.cast),
            str(args.gif),
        ],
        check=True,
    )
    print(f"wrote {args.gif} ({args.gif.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
