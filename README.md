# AI Reel Generator

A local desktop app for creating Instagram Reels from scripts. No subscriptions, no cloud — runs entirely on your machine.

![Python](https://img.shields.io/badge/Python-3.14-blue) ![Platform](https://img.shields.io/badge/Platform-macOS-lightgrey)

## Features

**Comics & Anime News**
- Real-time news feed for Marvel, DC, Anime, and Manhwa
- Sorted by virality (trending stories first)
- Daily caching — loads instantly on repeat visits
- One-click "Use for Reel" to turn any article into a video

**Script to Video**
- Type a topic → app searches and downloads images automatically
- Ken Burns effect (slow zoom/pan) on every image
- Crossfade transitions between images
- Microsoft Neural TTS voiceover (4 voices)
- Auto-generated subtitles via OpenAI Whisper
- Exports 1080x1920 MP4 (Instagram Reel format)

**Script to AI Video**
- Generates real cinematic video clips using Hailuo AI (via Replicate)
- Same voiceover + subtitle pipeline
- Requires a Replicate API token (~$0.50–1.00 per clip)

## Setup

```bash
git clone https://github.com/nishant0178/ai-video-editor.git
cd ai-video-editor

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

## Requirements

- Python 3.11+
- macOS (tested on macOS 15)
- For AI Video: [Replicate API token](https://replicate.com/account/api-tokens)

## Tech Stack

- **GUI** — CustomTkinter
- **Video** — moviepy, ffmpeg
- **Voiceover** — edge-tts (Microsoft Neural TTS)
- **Subtitles** — OpenAI Whisper (local, no API key)
- **Image search** — DuckDuckGo + Bing fallback
- **AI Video** — Replicate HTTP API (Hailuo AI / minimax-video-01)
- **News** — DuckDuckGo News with virality scoring
