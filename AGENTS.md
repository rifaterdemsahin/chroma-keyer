# chroma-keyer — agent runbook

This repo is run from a **terminal AI agent** (Grok Build, Claude Code, Google Antigravity / agy). The HTML pages are optional docs. Do not wait for a browser UI.

You **run the keyer and quality-assure the output**. A file does not leave this folder for Canva until `qa.py` reports **PASS**.

## Default job

1. `cd` to this repo.
2. Key green-screen clips with `python3 autocrop_rvm.py`.
3. Keep **color**, **original audio**, **transparent alpha**. Never write a black-and-white matte.
4. Unique filename under `output/`. Log under `logs/`. Print the RUN SUMMARY.
5. Monitor the encode (FPS, speed, failures). Do not leave a hung ffmpeg.
6. **QA:** `python3 qa.py PATH.webm` (also invoked automatically after encode). Read `logs/qa_*.log` and the sampled PNGs. FAIL ⇒ do not upload; fix and re-run.

## Commands

```bash
python3 autocrop_rvm.py                         # one clip + automatic QA
python3 autocrop_rvm.py /path/to/clip.mp4
python3 autocrop_rvm.py --watch                 # monitor input/ forever (QA each clip)
python3 qa.py                                   # QA newest keyed WebM
python3 qa.py output/keyed_….webm               # QA a specific file
python3 serve.py                                # optional localhost docs at :8876
```

Needs Homebrew `ffmpeg` (libvpx-vp9) and Python Pillow. Optional `--engine rvm` needs PyTorch.

## QA gate (required)

`qa.py` must PASS:

| Check | Meaning |
| --- | --- |
| audio | Soundtrack present |
| alpha | `alpha_mode=1` |
| codec | VP9, not a B/W matte |
| corners-transparent | Green backdrop gone |
| subject-present | Person/mic not keyed out |
| color-not-grayscale | Subject still in color |
| green-gone | No leftover green on opaque pixels |

Exit code 1 = FAIL. Do not tell the user the clip is Canva-ready unless RESULT is PASS.

## Monitor

- Watch stdout + `logs/process_*.log` + `logs/qa_*.log`.
- Inbox: `input/` (drop .mp4/.mov). Library: `output/`, `logs/`.
- Local preview (not GitHub Pages): `http://127.0.0.1:8876/output/` after `python3 serve.py`.

## Canva

Upload **only QA-PASS** `.webm` files to https://canva.link/feekl13cfrcl5y5 (Uploads → timeline, unmute if needed).
