"""
Script to AI Video — Replicate Pipeline
=========================================
Workflow:
  1. Generate voiceover MP3 with edge-tts
  2. Split script into N visual prompts (one per ~5s clip)
  3. Run each prompt through Replicate's minimax/video-01 (Hailuo AI)
  4. Download each clip into a temp dir
  5. Stitch clips with moviepy
  6. Transcribe voiceover with Whisper → build subtitle overlays
  7. Composite subtitles + audio over stitched video
  8. Export 1080x1920 MP4

TEACHING NOTES:
  Replicate = a platform that hosts AI models in the cloud.
              You send a prompt, they run the model, you get back a video URL.
              Much simpler than Kling — one API token, one function call.
  minimax/video-01 = Hailuo AI's video model. Great for cinematic content.
"""

import asyncio
import math
import os
import shutil
import tempfile

import time

import edge_tts
import requests
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx import Crop

from features.script_to_video import build_subtitle_clips, transcribe_audio

REEL_W    = 1080
REEL_H    = 1920
REEL_SIZE = (REEL_W, REEL_H)

# Replicate model to use — Hailuo AI (minimax), great for cinematic/action content
REPLICATE_BASE  = "https://api.replicate.com/v1"
REPLICATE_MODEL = "minimax/video-01"  # Hailuo AI — great for cinematic content
POLL_INTERVAL   = 10   # seconds between status checks
POLL_TIMEOUT    = 600  # 10 minutes max per clip


# ---------------------------------------------------------------------------
# Voiceover (same pattern as script_to_video.py)
# ---------------------------------------------------------------------------

async def _tts_async(script: str, voice: str, path: str):
    await edge_tts.Communicate(script, voice).save(path)


def generate_audio(script: str, voice: str = "en-US-ChristopherNeural") -> str:
    """Convert script to MP3 using Microsoft Neural TTS. Returns temp file path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    asyncio.run(_tts_async(script, voice, tmp.name))
    return tmp.name


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------

def _make_prompts(topic: str, script: str, audio_duration: float) -> list:
    """Generate one visual prompt per 5-second clip needed."""
    n_clips = max(2, min(12, math.ceil(audio_duration / 5)))

    words = script.split()
    chunk_size = max(1, len(words) // n_clips)

    prompts = []
    for i in range(n_clips):
        start = i * chunk_size
        end = start + chunk_size if i < n_clips - 1 else len(words)
        chunk = " ".join(words[start:end])
        prompt = (
            f"Cinematic vertical video about {topic}. "
            f"Scene: {chunk}. "
            "Dramatic lighting, high quality, professional cinematography, "
            "9:16 aspect ratio, no text, no watermarks."
        )
        prompts.append(prompt)

    return prompts


# ---------------------------------------------------------------------------
# Replicate API
# ---------------------------------------------------------------------------

def _generate_clip(prompt: str, api_token: str) -> str:
    """
    Submit a video generation job to Replicate and poll until done.
    Returns a video download URL.

    TEACHING NOTE: We use Replicate's HTTP API directly (no Python library)
    because the replicate package is not compatible with Python 3.14.
    This is actually better — fewer dependencies, full control.

    Replicate API flow:
      1. POST /v1/models/{model}/predictions  →  get prediction id
      2. GET  /v1/predictions/{id}            →  poll status
      3. When status == "succeeded", return output URL
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    # Step 1: Submit the prediction
    resp = requests.post(
        f"{REPLICATE_BASE}/models/{REPLICATE_MODEL}/predictions",
        json={"input": {"prompt": prompt, "prompt_optimizer": True}},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    prediction_id = resp.json().get("id")
    if not prediction_id:
        raise RuntimeError(f"Replicate did not return a prediction id. Response: {resp.json()}")

    # Step 2: Poll until done
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        poll = requests.get(
            f"{REPLICATE_BASE}/predictions/{prediction_id}",
            headers=headers,
            timeout=30,
        )
        poll.raise_for_status()
        data   = poll.json()
        status = data.get("status", "")

        if status == "succeeded":
            output = data.get("output")
            # output is usually a list with one URL, or a URL string
            if isinstance(output, list):
                return str(output[0])
            return str(output)

        if status in ("failed", "canceled"):
            raise RuntimeError(f"Replicate prediction {prediction_id} {status}: {data.get('error')}")

        time.sleep(POLL_INTERVAL)

    raise RuntimeError(f"Replicate prediction {prediction_id} timed out after {POLL_TIMEOUT}s.")


def _download_clip(url: str, dest_path: str):
    """Stream-download a video file."""
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)


# ---------------------------------------------------------------------------
# Crop a clip to fill 9:16 (cover crop — no black bars, no stretching)
# ---------------------------------------------------------------------------

def _crop_to_reel(clip):
    """
    Resize + center-crop a clip to exactly REEL_W x REEL_H (1080x1920).

    Works like CSS `object-fit: cover`:
    - Scale so the clip fills the frame in both dimensions
    - Crop the overflow from the center
    This means no black bars and no distortion — same as Instagram does.
    """
    # Scale so the clip covers the full 9:16 frame
    clip_ratio  = clip.w / clip.h
    target_ratio = REEL_W / REEL_H  # 0.5625

    if clip_ratio > target_ratio:
        # Clip is wider than 9:16 (e.g. 16:9 landscape) — fit height, crop sides
        clip = clip.resized(height=REEL_H)
    else:
        # Clip is taller than 9:16 — fit width, crop top/bottom
        clip = clip.resized(width=REEL_W)

    # Center-crop to exact target size
    x1 = (clip.w - REEL_W) // 2
    y1 = (clip.h - REEL_H) // 2
    clip = clip.with_effects([Crop(x1=x1, y1=y1, x2=x1 + REEL_W, y2=y1 + REEL_H)])
    return clip


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def create_ai_reel(
    topic,
    script,
    output_path,
    voice="en-US-ChristopherNeural",
    api_token="",
    progress_cb=None,
    # Keep these for backwards compat if called with old Kling kwargs
    api_key_id=None,
    api_secret=None,
):
    """
    Full pipeline: topic + script + Replicate token → AI-generated Reel.

    Args:
        topic       : Short topic description used to guide visual prompts
        script      : Voiceover text — drives clip count and subtitles
        output_path : Where to save the final .mp4
        voice       : edge-tts voice ID
        api_token   : Replicate API token (from replicate.com/account)
        progress_cb : Optional function(message, 0.0–1.0)
    """
    # Support old Kling-style call (api_key_id passed as positional or kwarg)
    if not api_token and api_key_id:
        api_token = api_key_id

    def _cb(msg, val):
        if progress_cb:
            progress_cb(msg, val)

    temp_dir   = tempfile.mkdtemp()
    audio_path = None
    raw_clips  = []

    try:
        # ----------------------------------------------------------------
        # 1. Voiceover
        # ----------------------------------------------------------------
        _cb("Generating voiceover...", 0.05)
        audio_path     = generate_audio(script, voice=voice)
        audio_clip     = AudioFileClip(audio_path)
        total_duration = audio_clip.duration

        # ----------------------------------------------------------------
        # 2. Build visual prompts
        # ----------------------------------------------------------------
        _cb("Planning video clips...", 0.10)
        prompts = _make_prompts(topic, script, total_duration)
        n = len(prompts)

        # ----------------------------------------------------------------
        # 3. Generate + download each clip via Replicate (one at a time)
        # ----------------------------------------------------------------
        clip_paths = []
        for i, prompt in enumerate(prompts):
            base = 0.15 + 0.55 * (i / n)

            _cb(f"Generating clip {i+1}/{n} with Hailuo AI (~2 min)...", base)
            video_url = _generate_clip(prompt, api_token)

            dest = os.path.join(temp_dir, f"clip_{i:03d}.mp4")
            _cb(f"Downloading clip {i+1}/{n}...", base + 0.04)
            _download_clip(video_url, dest)
            clip_paths.append(dest)

        # ----------------------------------------------------------------
        # 4. Stitch clips end-to-end
        # ----------------------------------------------------------------
        _cb("Stitching clips together...", 0.72)
        raw_clips = [_crop_to_reel(VideoFileClip(p)) for p in clip_paths]
        stitched  = concatenate_videoclips(raw_clips, method="compose")

        if stitched.duration > total_duration:
            stitched = stitched.subclipped(0, total_duration)

        # ----------------------------------------------------------------
        # 5. Subtitles
        # ----------------------------------------------------------------
        _cb("Transcribing audio for subtitles...", 0.78)
        segments       = transcribe_audio(audio_path)
        subtitle_clips = build_subtitle_clips(segments)

        # ----------------------------------------------------------------
        # 6. Composite
        # ----------------------------------------------------------------
        _cb("Compositing subtitles...", 0.86)
        final = CompositeVideoClip([stitched] + subtitle_clips, size=REEL_SIZE)
        final = final.with_duration(total_duration).with_audio(audio_clip)

        # ----------------------------------------------------------------
        # 7. Export
        # ----------------------------------------------------------------
        _cb("Exporting final Reel...", 0.92)
        final.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            logger=None,
            threads=4,
        )

        _cb("Done! AI Reel saved to Desktop.", 1.0)
        return output_path

    finally:
        for clip in raw_clips:
            try:
                clip.close()
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)
        if audio_path:
            try:
                os.unlink(audio_path)
            except Exception:
                pass
