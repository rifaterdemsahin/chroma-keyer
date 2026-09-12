#!/usr/bin/env python3
"""Green-screen keyer for Canva-ready color video with transparency + audio.

Default engine is ffmpeg chromakey (keeps the subject in color, including
props like a microphone). Optional --engine rvm uses Robust Video Matting
on Apple Silicon when PyTorch is installed.

Every run writes a unique output filename and a matching process/performance log.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = ROOT / "logs"


class ProcessLogger:
    def __init__(self, log_path: Path, run_id: str):
        self.log_path = log_path
        self.run_id = run_id
        self.t0 = time.perf_counter()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(log_path, "w", encoding="utf-8")
        self.info(f"run_id={run_id}")
        self.info(f"log={log_path}")

    def _stamp(self) -> str:
        return f"{time.perf_counter() - self.t0:8.3f}s"

    def info(self, message: str) -> None:
        line = f"[{self._stamp()}] {message}"
        print(line, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def which_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise SystemExit("ffmpeg is required. Install with: brew install ffmpeg")
    return path


def which_ffprobe() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise SystemExit("ffprobe is required (comes with ffmpeg).")
    return path


def probe_media(input_path: Path) -> dict:
    raw = subprocess.check_output(
        [
            which_ffprobe(),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ],
        text=True,
    )
    data = json.loads(raw)
    video = next(s for s in data["streams"] if s.get("codec_type") == "video")
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    fps_txt = video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"
    num, den = fps_txt.split("/")
    fps = float(num) / float(den or 1)
    tags = video.get("tags") or {}
    alpha_mode = str(tags.get("alpha_mode") or tags.get("ALPHA_MODE") or "")
    pix = video.get("pix_fmt") or ""
    has_alpha = pix.startswith("yuva") or pix in {"rgba", "argb", "bgra"} or alpha_mode == "1"
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
        "duration": float(data.get("format", {}).get("duration") or video.get("duration") or 0),
        "frames": int(video.get("nb_frames") or 0),
        "pix_fmt": pix,
        "v_codec": video.get("codec_name"),
        "has_audio": audio is not None,
        "has_alpha": has_alpha,
        "alpha_mode": alpha_mode,
        "a_codec": None if audio is None else audio.get("codec_name"),
        "sample_rate": None if audio is None else audio.get("sample_rate"),
        "channels": None if audio is None else audio.get("channels"),
    }


def unique_names(input_path: Path) -> dict:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in input_path.stem).strip("-_")
    base = f"keyed_{stem}_{stamp}_{uid}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "run_id": f"{stamp}_{uid}",
        "base": base,
        "webm": OUTPUT_DIR / f"{base}.webm",
        "log": LOGS_DIR / f"process_{stamp}_{uid}.log",
    }


def extract_analysis_frame(input_path: Path, dest: Path, logger: ProcessLogger) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        which_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        "0.4",
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        str(dest),
    ]
    logger.info("extract analysis frame: " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def detect_green_crop(frame_path: Path, padding: int = 16) -> dict:
    """Lock a crop *inside* the green backdrop so room clutter is excluded."""
    im = Image.open(frame_path).convert("RGB")
    w, h = im.size
    px = im.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    greens: list[tuple[int, int, int]] = []
    step = 2
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y]
            if g > 100 and g > r * 1.4 and g > b * 1.4 and (g - r) > 40:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
                greens.append((r, g, b))
    if not greens:
        raise ValueError("No green screen detected in the analysis frame.")

    # Inset (do not expand) so sofa/photos/window stay out of the Canva plate.
    min_x = min(min_x + padding, max_x - 32)
    min_y = min(min_y + padding, max_y - 32)
    max_x = max(max_x - padding, min_x + 32)
    max_y = max(max_y - padding, min_y + 32)
    min_x = max(0, min_x)
    min_y = max(0, min_y)
    max_x = min(w - 1, max_x)
    max_y = min(h - 1, max_y)

    crop_w = max_x - min_x + 1
    crop_h = max_y - min_y + 1
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    if crop_w < 16 or crop_h < 16:
        raise ValueError("Detected green crop is too small.")

    greens.sort(key=lambda c: c[1])
    key_r, key_g, key_b = greens[len(greens) // 2]
    return {
        "x": min_x,
        "y": min_y,
        "w": crop_w,
        "h": crop_h,
        "key_hex": f"0x{key_r:02X}{key_g:02X}{key_b:02X}",
        "key_rgb": (key_r, key_g, key_b),
        "green_samples": len(greens),
        "frame_size": (w, h),
    }


def _progress_seconds(stats: dict[str, str]) -> float:
    t = stats.get("out_time") or ""
    if t and t != "N/A" and ":" in t:
        hh, mm, ss = t.split(":")
        return int(hh) * 3600 + int(mm) * 60 + float(ss)
    us = stats.get("out_time_us")
    if us and us.isdigit():
        return int(us) / 1_000_000
    ms = stats.get("out_time_ms")
    if ms and ms.isdigit():
        val = int(ms)
        return val / 1_000_000 if val > 10_000_000 else val / 1000
    return 0.0


def run_ffmpeg_with_progress(cmd: list[str], logger: ProcessLogger, duration: float) -> None:
    logger.info("ffmpeg: " + " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    last_log = 0.0
    stats: dict[str, str] = {}
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        stats[key] = value
        if key in {"out_time_ms", "out_time_us", "out_time", "progress", "speed", "frame"}:
            now = time.perf_counter()
            if key == "progress" or now - last_log >= 1.0:
                out_s = _progress_seconds(stats)
                pct = min(100.0, out_s / duration * 100.0) if duration else 0.0
                logger.info(
                    f"encode frame={stats.get('frame', '?')} "
                    f"time={out_s:.1f}s/{duration:.1f}s ({pct:5.1f}%) "
                    f"speed={stats.get('speed', '?')} fps={stats.get('fps', '?')}"
                )
                last_log = now
            if key == "progress" and value == "end":
                break
    err = proc.stderr.read() if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        logger.info("ffmpeg stderr (tail):\n" + "\n".join(err.splitlines()[-40:]))
        raise subprocess.CalledProcessError(rc, cmd)
    if stats:
        logger.info(
            f"ffmpeg finished frame={stats.get('frame', '?')} "
            f"speed={stats.get('speed', '?')} fps={stats.get('fps', '?')}"
        )


def encode_canva_webm(
    input_path: Path,
    output_path: Path,
    crop: dict,
    media: dict,
    logger: ProcessLogger,
    similarity: float,
    blend: float,
    despill: float = 0.25,
) -> None:
    vf = (
        f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']},"
        f"chromakey={crop['key_hex']}:{similarity}:{blend},"
        f"despill=type=green:mix={despill}:expand=0,"
        "format=yuva420p"
    )
    cmd = [
        which_ffmpeg(),
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-auto-alt-ref",
        "0",
        "-lag-in-frames",
        "0",
        "-b:v",
        "0",
        "-crf",
        "32",
        "-deadline",
        "good",
        "-cpu-used",
        "4",
        "-row-mt",
        "1",
        "-metadata:s:v:0",
        "alpha_mode=1",
    ]
    if media["has_audio"]:
        cmd += ["-c:a", "libopus", "-b:a", "128k", "-ac", "2"]
    else:
        cmd += ["-an"]
        logger.info("WARNING: source has no audio track")
    cmd += ["-progress", "pipe:1", "-nostats", str(output_path)]
    run_ffmpeg_with_progress(cmd, logger, media["duration"])


def run_rvm_engine(
    input_path: Path,
    output_path: Path,
    crop: dict,
    media: dict,
    logger: ProcessLogger,
) -> None:
    try:
        import cv2
        import numpy as np
        import torch
    except ImportError as exc:
        raise SystemExit(
            "RVM engine needs torch, opencv-python, and numpy. "
            "Install: pip3 install torch torchvision opencv-python numpy\n"
            f"Missing import: {exc}"
        ) from exc

    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    logger.info(f"RVM device={device}")

    logger.info("Loading Robust Video Matting (mobilenetv3)...")
    t_load = time.perf_counter()
    model = torch.hub.load("PeterL1n/RobustVideoMatting", "mobilenetv3", trust_repo=True)
    model = model.to(device).eval()
    logger.info(f"model loaded in {time.perf_counter() - t_load:.2f}s")

    tmp = output_path.parent / f".frames_{output_path.stem}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    cap = cv2.VideoCapture(str(input_path))
    rec = [None] * 4
    frame_i = 0
    t_loop = time.perf_counter()
    ymin, ymax = crop["y"], crop["y"] + crop["h"]
    xmin, xmax = crop["x"], crop["x"] + crop["w"]

    with torch.no_grad():
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            cropped = frame[ymin:ymax, xmin:xmax]
            rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
            src = torch.from_numpy(rgb).float().permute(2, 0, 1).unsqueeze(0).div(255).to(device)
            _fgr, pha, *rec = model(src, *rec, downsample_ratio=0.25)
            alpha = (pha.squeeze().clamp(0, 1).cpu().numpy() * 255).astype("uint8")
            if alpha.ndim == 3:
                alpha = alpha[0]
            # Keep original color (not the RVM grayscale matte, not a B&W dump).
            rgba = cv2.cvtColor(cropped, cv2.COLOR_BGR2BGRA)
            rgba[:, :, 3] = alpha
            cv2.imwrite(str(tmp / f"{frame_i:06d}.png"), rgba)
            frame_i += 1
            if frame_i % 30 == 0:
                elapsed = time.perf_counter() - t_loop
                fps = frame_i / elapsed if elapsed else 0
                logger.info(f"RVM frame={frame_i} elapsed={elapsed:.1f}s infer_fps={fps:.2f}")

    cap.release()
    elapsed = time.perf_counter() - t_loop
    logger.info(f"RVM wrote {frame_i} PNG frames in {elapsed:.1f}s ({frame_i / elapsed if elapsed else 0:.2f} fps)")

    fps = media["fps"] or 30
    cmd = [
        which_ffmpeg(),
        "-hide_banner",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(tmp / "%06d.png"),
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-auto-alt-ref",
        "0",
        "-lag-in-frames",
        "0",
        "-b:v",
        "0",
        "-crf",
        "32",
        "-deadline",
        "good",
        "-cpu-used",
        "4",
        "-row-mt",
        "1",
        "-metadata:s:v:0",
        "alpha_mode=1",
        "-shortest",
    ]
    if media["has_audio"]:
        cmd += ["-map", "1:a:0?", "-c:a", "libopus", "-b:a", "128k", "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += ["-progress", "pipe:1", "-nostats", str(output_path)]
    run_ffmpeg_with_progress(cmd, logger, media["duration"])
    shutil.rmtree(tmp, ignore_errors=True)


def verify_output(output_path: Path, logger: ProcessLogger) -> dict:
    info = probe_media(output_path)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(
        f"output probe v={info['v_codec']} pix={info['pix_fmt']} "
        f"alpha={info['has_alpha']} alpha_mode={info['alpha_mode'] or '-'} "
        f"{info['width']}x{info['height']} {info['fps']:.3f}fps "
        f"audio={info['a_codec'] or 'none'} size={size_mb:.2f}MB"
    )
    if not info["has_alpha"]:
        logger.info(f"WARNING: no alpha detected (pix={info['pix_fmt']})")
    if not info["has_audio"]:
        logger.info("WARNING: output has no audio")
    return info


def resolve_input(cli_path: str | None) -> Path:
    if cli_path:
        path = Path(cli_path).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Input not found: {path}")
        return path
    preferred = ROOT / "2025-09-28-07-57.mp4"
    if preferred.exists():
        return preferred
    inbox = ROOT / "input"
    candidates = []
    for folder in (inbox, ROOT):
        if not folder.exists():
            continue
        for ext in ("*.mp4", "*.mov", "*.MP4", "*.MOV", "*.webm", "*.mkv", "*.MKV"):
            candidates.extend(folder.glob(ext))
    candidates = [p for p in candidates if p.is_file() and p.name != Path(__file__).name]
    if not candidates:
        raise SystemExit("No input video found. Pass a path: python3 autocrop_rvm.py clip.mp4")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


VIDEO_EXTS = {".mp4", ".mov", ".MP4", ".MOV", ".m4v", ".M4V", ".mkv", ".MKV", ".webm"}


def process_clip(input_path: Path, args: argparse.Namespace) -> int:
    names = unique_names(input_path)
    logger = ProcessLogger(names["log"], names["run_id"])
    try:
        logger.info(f"input={input_path}")
        logger.info(f"engine={args.engine}")
        media = probe_media(input_path)
        logger.info(
            f"source {media['width']}x{media['height']} {media['fps']:.3f}fps "
            f"{media['v_codec']}/{media['pix_fmt']} duration={media['duration']:.2f}s "
            f"frames={media['frames']} audio={media['a_codec'] or 'none'} "
            f"{media['sample_rate'] or '-'}Hz ch={media['channels'] or '-'}"
        )

        frame_path = LOGS_DIR / f"analysis_{names['run_id']}.png"
        extract_analysis_frame(input_path, frame_path, logger)
        crop = detect_green_crop(frame_path, padding=args.padding)
        logger.info(
            f"crop x={crop['x']} y={crop['y']} w={crop['w']} h={crop['h']} "
            f"key={crop['key_hex']} rgb={crop['key_rgb']} samples={crop['green_samples']}"
        )

        t_enc = time.perf_counter()
        if args.engine == "rvm":
            run_rvm_engine(input_path, names["webm"], crop, media, logger)
        else:
            encode_canva_webm(
                input_path,
                names["webm"],
                crop,
                media,
                logger,
                similarity=args.similarity,
                blend=args.blend,
                despill=args.despill,
            )
        encode_s = time.perf_counter() - t_enc
        out_info = verify_output(names["webm"], logger)
        total = time.perf_counter() - logger.t0
        realtime = (media["duration"] / encode_s) if encode_s else 0
        logger.info(f"encode_seconds={encode_s:.2f} realtime_factor={realtime:.2f}x")
        logger.info(f"total_seconds={total:.2f}")
        logger.info(f"OUTPUT {names['webm']}")
        print()
        print("========== RUN SUMMARY ==========")
        print(f"Run ID     : {names['run_id']}")
        print(f"Engine     : {args.engine}")
        print(f"Output     : {names['webm']}")
        print(
            f"Format     : VP9 WebM + alpha "
            f"(pix={out_info['pix_fmt']} alpha_mode={out_info['alpha_mode'] or out_info['has_alpha']})  "
            f"{out_info['width']}x{out_info['height']}"
        )
        print(f"Audio      : {out_info['a_codec'] or 'none'} (source audio preserved)")
        print(f"Color      : full color subject — green background removed")
        print(f"Elapsed    : {total:.2f}s   encode {encode_s:.2f}s ({realtime:.2f}x realtime)")
        print(f"Log        : {names['log']}")
        print("Canva      : Uploads → Upload files → drop the .webm on the video timeline")
        print("=================================")
        logger.info("starting agent QA")
        from qa import qa_clip

        qa_ok, qa_log, _ = qa_clip(names["webm"])
        logger.info(f"QA {'PASS' if qa_ok else 'FAIL'} log={qa_log}")
        print(f"QA         : {'PASS' if qa_ok else 'FAIL'}  {qa_log}")
        if not qa_ok:
            logger.info("QA failed — do not send this file to Canva")
            return 1
        return 0
    except Exception as exc:
        logger.info(f"FAILED {type(exc).__name__}: {exc}")
        raise
    finally:
        logger.close()


def list_inbox(folder: Path) -> list[Path]:
    files: list[Path] = []
    for path in folder.iterdir():
        if path.is_file() and path.suffix in VIDEO_EXTS:
            files.append(path)
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def watch_inbox(folder: Path, args: argparse.Namespace) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, float, int]] = set()
    print(f"[watch] monitoring {folder} for .mp4/.mov  (Ctrl+C to stop)", flush=True)
    print("[watch] drop a green-screen clip in; a unique output/ file + logs/ entry will appear.", flush=True)
    while True:
        for path in list_inbox(folder):
            st = path.stat()
            key = (str(path.resolve()), st.st_mtime, st.st_size)
            if key in seen:
                continue
            print(f"[watch] new clip {path.name} ({st.st_size / (1024 * 1024):.1f} MB)", flush=True)
            try:
                rc = process_clip(path, args)
            except Exception as exc:
                print(f"[watch] FAILED {path.name}: {exc}", flush=True)
                rc = 1
            seen.add(key)
            if rc != 0:
                print(f"[watch] FAILED {path.name} rc={rc}", flush=True)
        time.sleep(2.5)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove green screen, keep color + audio, write a unique Canva-ready WebM."
    )
    parser.add_argument("input", nargs="?", help="Source .mp4 / .mov clip")
    parser.add_argument("--engine", choices=("chromakey", "rvm"), default="chromakey")
    parser.add_argument("--similarity", type=float, default=0.10, help="chromakey similarity (0-1)")
    parser.add_argument("--blend", type=float, default=0.04, help="chromakey edge blend (0-1)")
    parser.add_argument("--padding", type=int, default=16, help="pixels to inset the green crop box")
    parser.add_argument("--despill", type=float, default=0.25, help="green despill mix (0-1)")
    parser.add_argument(
        "--watch",
        nargs="?",
        const="input",
        metavar="DIR",
        help="Monitor DIR (default: input/) and key each new clip. For Grok / Claude / Antigravity.",
    )
    args = parser.parse_args()

    if args.watch is not None:
        folder = Path(args.watch).expanduser()
        if not folder.is_absolute():
            folder = ROOT / folder
        try:
            return watch_inbox(folder, args)
        except KeyboardInterrupt:
            print("\n[watch] stopped", flush=True)
            return 0

    input_path = resolve_input(args.input)
    return process_clip(input_path, args)


if __name__ == "__main__":
    sys.exit(main())
