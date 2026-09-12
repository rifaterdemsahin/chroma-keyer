# chroma-keyer — agent runbook

This repo is run from a **terminal AI agent** (Grok Build, Claude Code, Google Antigravity / agy). The HTML pages are optional docs. Do not wait for a browser UI.

## Default job

1. `cd` to this repo.
2. Key green-screen clips with `python3 autocrop_rvm.py`.
3. Keep **color**, **original audio**, **transparent alpha**. Never write a black-and-white matte.
4. Unique filename under `output/`. Log under `logs/`. Print the RUN SUMMARY.
5. Monitor the encode (FPS, speed, failures). Do not leave a hung ffmpeg.

## Commands

```bash
python3 autocrop_rvm.py                         # one clip (sample or newest)
python3 autocrop_rvm.py /path/to/clip.mp4       # named clip
python3 autocrop_rvm.py --watch                 # monitor input/ forever
python3 serve.py                                # optional localhost docs at :8876
```

Needs Homebrew `ffmpeg` (libvpx-vp9) and Python Pillow. Optional `--engine rvm` needs PyTorch.

## Monitor

- Watch stdout + `logs/process_*.log`.
- Success: `alpha_mode=1`, audio codec present, unique `output/keyed_*.webm`.
- Inbox: `input/` (drop .mp4/.mov). Library: `output/`, `logs/`.
- Local preview (not GitHub Pages): `http://127.0.0.1:8876/output/` after `python3 serve.py`.

## Canva

Upload the unique `.webm` to https://canva.link/feekl13cfrcl5y5 (Uploads → timeline, unmute if needed).
