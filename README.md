# chroma-keyer
Clean green screen with code using AI on Apple Silicon.

## Live Demo
Docs site: [GitHub Pages](https://rifaterdemsahin.github.io/chroma-keyer/)

## What it writes
Each run creates a **unique** Canva-ready file:

- Full-color subject (not black-and-white)
- Green background removed (VP9 WebM with alpha)
- Original audio kept
- Process + performance log

```
output/keyed_<clip>_<timestamp>_<id>.webm
logs/process_<timestamp>_<id>.log
```

## Run from the command prompt

```bash
python3 autocrop_rvm.py
python3 autocrop_rvm.py /path/to/greenscreen.mp4
```

Needs **ffmpeg** (`brew install ffmpeg`) and Python **Pillow**.

Ask an AI agent in this repo to run the same command. Full copy-paste prompt: [process.html](process.html). Changelog: [update.html](update.html).

## Canva
Uploads → Upload files → drop the `.webm` on a video timeline. Transparent pixels let your Canva background show through; sound is already on the clip.

## Engines
- Default: ffmpeg `chromakey` + `despill` after an auto-crop of the green backdrop (keeps color, mic, and audio).
- Optional: `python3 autocrop_rvm.py --engine rvm` — Robust Video Matting on Apple Silicon MPS when PyTorch is installed.

## Google Antigravity / any CLI agent
> Monitor this folder for green-screen `.mov` or `.mp4` files. Run `python3 autocrop_rvm.py <file>`. Keep audio, keep color, remove the green to transparent alpha, write a unique filename under `output/`, and print performance logs.

Set terminal command execution to auto-approve for unattended runs.
