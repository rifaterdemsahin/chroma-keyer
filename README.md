# chroma-keyer
Clean green screen with code using AI on Apple Silicon.

## Live Demo
Check out the automated WebGPU chroma keyer here: [Live Demo on GitHub Pages](https://rifaterdemsahin.github.io/chroma-keyer/)

## Overview
This project implements an automated, browser-native green screen removal tool. It processes video footage in real-time, removing the green background without the need for manual human intervention typically required in traditional NLE software like DaVinci Resolve.

## M1 Apple Silicon AI Keying Pipeline

This repository includes a robust video matting pipeline optimized for Apple Silicon (M1/M2/M3) Unified Memory architecture.

### 1. Local Python Pre-Processing Engine (`autocrop_rvm.py`)
A script leveraging **Robust Video Matting (RVM - MobileNetV3)** and **PyTorch with MPS (Metal Performance Shaders)** back-end.
- Automatically crops outer non-green boundaries on the first frame.
- Outputs a hardware-accelerated Alpha Matte video sequence.
- **Run:** `python autocrop_rvm.py`

### 2. Static Web Suite (`index.html` & `process.html`)
A zero-dependency file ingestion dashboard and WebGPU AI runner for generating real-time alpha matte previews directly in the browser via `@xenova/transformers`.

### Google Antigravity Agent Automation Setup

Google Antigravity provides an agentic IDE workspace powered by Gemini 3.1 Pro. It can monitor your local workspace folders and run autonomous subagents to render files asynchronously.

1. **Launch Google Antigravity** and open your project folder containing `autocrop_rvm.py`.
2. Open the **Manager View** (Agent Command Center).
3. Assign the following task prompt to the agent:

> *"Monitor the `/input` folder in this workspace for incoming green screen `.mov` or `.mp4` video files. Automatically run `autocrop_rvm.py` using PyTorch on Apple Silicon (`--device mps`). Generate black-and-white alpha matte files to the `/output` folder with identical frame counts and timing, and log the GPU FPS performance to `render_log.txt`."*

4. Set **Terminal Command Execution** in Antigravity settings to **Always Proceed (Turbo Mode)** to allow the agent to launch PyTorch batch commands without requiring manual confirmation prompts.

## Verification of Performance Improvements
- **Playback Performance:** Import the generated `output_alpha.mp4` file into DaVinci Resolve as an Alpha matte overlay. Resolve timeline playback will maintain a locked 24/30 FPS without frame drops, as it reads pre-rendered image masks rather than calculating neural network passes on the fly.
- **GPU Footprint:** Check **Activity Monitor -> Memory**. Dedicated Python/MPS batch runs avoid the heavy VRAM overhead of running Resolve's GUI, color engine, and Magic Mask AI simultaneously.
