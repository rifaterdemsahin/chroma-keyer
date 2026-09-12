# chroma-keyer
Clean green screen with code using AI on Apple Silicon.

**Default:** a terminal AI agent (Grok, Claude, Antigravity/agy) **runs the keyer and QAs the file**. Nothing goes to Canva until `python3 qa.py` reports PASS. The HTML site is optional docs. If you open the docs at all, use **localhost** so the browser can reach local `output/` and `logs/` — not GitHub Pages.

## Agents
| Agent | Install | In this repo |
| --- | --- | --- |
| [Grok Build](https://x.ai/cli) | `curl -fsSL https://x.ai/cli/install.sh \| bash` | `grok` |
| [Claude Code](https://code.claude.com/docs/en/overview) | `curl -fsSL https://claude.ai/install.sh \| bash` | `claude` |
| [Antigravity (agy)](https://antigravity.google/download/) | [download](https://antigravity.google/download/) or CLI install | open folder / Manager |

Paste the monitor prompt from [process.html](process.html). Repo instructions for agents: [AGENTS.md](AGENTS.md).

```bash
python3 autocrop_rvm.py --watch          # monitor input/ (QA each clip)
python3 autocrop_rvm.py clip.mp4         # one file + automatic QA
python3 qa.py                            # re-check newest keyed WebM
python3 serve.py                         # http://127.0.0.1:8876/ (local libraries)
```

## Local servers (not GitHub Pages)
| Library | URL |
| --- | --- |
| Process | http://127.0.0.1:8876/process.html |
| Output player | http://127.0.0.1:8876/output.html |
| Unique clips | http://127.0.0.1:8876/output/ |
| Logs | http://127.0.0.1:8876/logs/ |
| Inbox | http://127.0.0.1:8876/input/ |

Public snapshot only: [GitHub Pages](https://rifaterdemsahin.github.io/chroma-keyer/)

## What it writes
Unique Canva-ready file each run: color subject, green removed (VP9 + alpha), original audio, process log.

```
output/keyed_<clip>_<timestamp>_<id>.webm
logs/process_<timestamp>_<id>.log
```

## QA
`python3 qa.py` (also runs at the end of every encode). Agents must treat FAIL as “not Canva-ready.”

## Canva
Project: https://canva.link/feekl13cfrcl5y5 — upload **QA-PASS** `.webm` only.

## Engines
- Default: ffmpeg chromakey + despill after auto-crop.
- Optional: `--engine rvm` (PyTorch MPS). Needs ffmpeg with libvpx-vp9 and Pillow.
