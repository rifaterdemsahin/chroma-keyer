#!/usr/bin/env python3
"""Quality-assurance checks for keyed Canva WebMs.

Run by Grok / Claude / Antigravity after every encode. Exit 0 = PASS, 1 = FAIL.
Writes logs/qa_<stem>.log and a few sampled PNG frames.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DEMO_DIR = ROOT / "demo"
LOGS_DIR = ROOT / "logs"


class Check:
    def __init__(self, name: str, ok: bool, detail: str, warn: bool = False):
        self.name = name
        self.ok = ok
        self.warn = warn
        self.detail = detail

    def line(self) -> str:
        if not self.ok:
            tag = "FAIL"
        elif self.warn:
            tag = "WARN"
        else:
            tag = "PASS"
        return f"{tag:4} {self.name}: {self.detail}"


def ffprobe(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        text=True,
    )
    data = json.loads(raw)
    video = next(s for s in data["streams"] if s.get("codec_type") == "video")
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    tags = video.get("tags") or {}
    alpha_mode = str(tags.get("alpha_mode") or tags.get("ALPHA_MODE") or "")
    pix = video.get("pix_fmt") or ""
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "duration": float(data.get("format", {}).get("duration") or 0),
        "size": path.stat().st_size,
        "v_codec": video.get("codec_name"),
        "pix_fmt": pix,
        "alpha_mode": alpha_mode,
        "has_alpha": alpha_mode == "1" or pix.startswith("yuva") or pix in {"rgba", "bgra", "argb"},
        "has_audio": audio is not None,
        "a_codec": None if audio is None else audio.get("codec_name"),
        "channels": None if audio is None else audio.get("channels"),
    }


def extract_rgba(path: Path, dest: Path, at_s: float) -> Image.Image:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-c:v",
            "libvpx-vp9",
            "-ss",
            f"{at_s:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-update",
            "1",
            str(dest),
        ],
        check=True,
    )
    return Image.open(dest).convert("RGBA")


def score_frame(im: Image.Image) -> dict:
    w, h = im.size
    px = im.load()
    corner = 24
    boxes = [
        (0, 0, corner, corner),
        (w - corner, 0, w, corner),
        (0, h - corner, corner, h),
        (w - corner, h - corner, w, h),
    ]
    corner_alphas: list[int] = []
    for x0, y0, x1, y1 in boxes:
        for y in range(y0, y1, 2):
            for x in range(x0, x1, 2):
                corner_alphas.append(px[x, y][3])
    corner_mean = sum(corner_alphas) / max(1, len(corner_alphas))

    cx0, cy0 = int(w * 0.3), int(h * 0.2)
    cx1, cy1 = int(w * 0.7), int(h * 0.85)
    opaque = 0
    trans = 0
    green = 0
    chroma = 0
    chroma_n = 0
    step = 3
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b, a = px[x, y]
            if a < 24:
                trans += 1
                continue
            if a > 200:
                opaque += 1
                chroma += abs(r - g) + abs(g - b) + abs(r - b)
                chroma_n += 1
                if g > 90 and g > r * 1.35 and g > b * 1.35 and (g - r) > 40:
                    green += 1
    interior_opaque = 0
    interior_n = 0
    for y in range(cy0, cy1, step):
        for x in range(cx0, cx1, step):
            interior_n += 1
            if px[x, y][3] > 200:
                interior_opaque += 1
    sampled = opaque + trans
    return {
        "corner_mean_alpha": corner_mean,
        "transparent_frac": trans / max(1, sampled),
        "opaque_frac": opaque / max(1, sampled),
        "interior_opaque_frac": interior_opaque / max(1, interior_n),
        "green_among_opaque": green / max(1, opaque),
        "chroma_mean": chroma / max(1, chroma_n),
        "size": (w, h),
    }


def latest_webm() -> Path | None:
    cands = list(OUTPUT_DIR.glob("keyed_*.webm")) + list(DEMO_DIR.glob("keyed_*.webm"))
    cands = [p for p in cands if p.is_file()]
    if not cands:
        return None
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def qa_clip(path: Path) -> tuple[bool, Path, list[Check]]:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"qa_{path.stem}_{stamp}.log"
    checks: list[Check] = []

    info = ffprobe(path)
    checks.append(
        Check(
            "file",
            info["size"] > 50_000,
            f"{path.name} {info['size'] / (1024 * 1024):.2f} MB "
            f"{info['width']}x{info['height']} {info['duration']:.2f}s",
        )
    )
    checks.append(
        Check(
            "audio",
            bool(info["has_audio"]),
            f"{info['a_codec'] or 'NONE'} ch={info['channels'] or '-'}",
        )
    )
    checks.append(
        Check(
            "alpha",
            bool(info["has_alpha"]),
            f"pix={info['pix_fmt']} alpha_mode={info['alpha_mode'] or '-'} codec={info['v_codec']}",
        )
    )
    checks.append(
        Check(
            "codec",
            info["v_codec"] in {"vp9", "vp8"},
            f"video codec={info['v_codec']} (want vp9 WebM, not a B/W matte movie)",
        )
    )

    duration = info["duration"] or 1.0
    samples = [max(0.15, duration * 0.12), duration * 0.5, min(duration - 0.15, duration * 0.82)]
    frame_stats = []
    for i, t in enumerate(samples):
        png = LOGS_DIR / f"qa_{path.stem}_t{i}.png"
        try:
            im = extract_rgba(path, png, t)
            st = score_frame(im)
            st["t"] = t
            st["png"] = png
            frame_stats.append(st)
        except subprocess.CalledProcessError as exc:
            checks.append(Check(f"frame@{t:.1f}s", False, f"decode failed: {exc}"))

    if frame_stats:
        corner = sum(s["corner_mean_alpha"] for s in frame_stats) / len(frame_stats)
        interior = sum(s["interior_opaque_frac"] for s in frame_stats) / len(frame_stats)
        green = sum(s["green_among_opaque"] for s in frame_stats) / len(frame_stats)
        chroma = sum(s["chroma_mean"] for s in frame_stats) / len(frame_stats)
        checks.append(
            Check(
                "corners-transparent",
                corner < 48,
                f"mean corner alpha={corner:.1f} (want < 48 so Canva background shows through)",
            )
        )
        checks.append(
            Check(
                "subject-present",
                interior > 0.08,
                f"interior opaque fraction={interior:.3f} (subject not keyed out)",
            )
        )
        checks.append(
            Check(
                "color-not-grayscale",
                chroma > 20,
                f"mean |R-G|+|G-B|+|R-B| among opaque={chroma:.1f} (B/W matte would be ~0)",
            )
        )
        checks.append(
            Check(
                "green-gone",
                green < 0.12,
                f"opaque pixels still green={green:.1%}",
                warn=green >= 0.04,
            )
        )
        for st in frame_stats:
            checks.append(
                Check(
                    f"sample-{st['t']:.1f}s",
                    True,
                    f"{st['png'].name} trans={st['transparent_frac']:.0%} "
                    f"opaque={st['opaque_frac']:.0%} interior={st['interior_opaque_frac']:.0%}",
                )
            )

    passed = all(c.ok for c in checks)
    lines = [
        f"qa_target={path}",
        f"qa_log={log_path}",
        *[c.line() for c in checks],
        f"RESULT {'PASS' if passed else 'FAIL'}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("========== QA REPORT ==========")
    for line in lines:
        print(line)
    print("================================")
    print(f"Log: {log_path}")
    return passed, log_path, checks


def main() -> int:
    parser = argparse.ArgumentParser(description="QA a keyed WebM (audio, alpha, color, green gone).")
    parser.add_argument("input", nargs="?", help="Path to keyed .webm (default: newest in output/ or demo/)")
    args = parser.parse_args()
    path = Path(args.input).expanduser() if args.input else latest_webm()
    if path is None:
        print("No keyed WebM found in output/ or demo/. Run autocrop_rvm.py first.", file=sys.stderr)
        return 1
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    passed, _, _ = qa_clip(path)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
