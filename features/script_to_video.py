"""
Script to Video — Cinematic Pipeline
======================================
Workflow:
  1. Search DuckDuckGo for images based on topic
  2. Apply Ken Burns effect (slow zoom/pan) to each image
  3. Crossfade between images
  4. Optionally add AI voiceover (gTTS)
  5. Burn subtitles (if voiceover is on)
  6. Crop to 9:16 (1080x1920) for Instagram Reels
  7. Export MP4

TEACHING NOTES:
  Ken Burns effect = named after documentary filmmaker Ken Burns.
                     It's a slow zoom-in or zoom-out on a still image.
                     Makes photos feel alive and cinematic.
                     Used in every professional documentary.
  Crossfade        = images fade into each other (opacity goes 0→1)
                     instead of cutting abruptly.
  CompositeVideoClip = moviepy's way of layering clips on top of each other.
                       Like Photoshop layers but for video.
"""

import asyncio
import os
import random
import shutil
import tempfile

import edge_tts
import numpy as np
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    concatenate_videoclips,
)
from PIL import Image
import whisper

from utils.image_fetcher import fetch_images

# Output resolution for Instagram Reels
REEL_W = 1080
REEL_H = 1920
REEL_SIZE = (REEL_W, REEL_H)


# ---------------------------------------------------------------------------
# Step 1: Generate voiceover audio (Microsoft Neural TTS via edge-tts)
# ---------------------------------------------------------------------------

# Available voices — all free, no API key needed
VOICES = {
    "Christopher (Deep & Dramatic)": "en-US-ChristopherNeural",
    "Guy (Clear & Confident)":       "en-US-GuyNeural",
    "Ryan (British Authority)":      "en-GB-RyanNeural",
    "Eric (Energetic)":              "en-US-EricNeural",
}


async def _generate_audio_async(script, voice, path):
    """Async core — edge-tts requires async/await."""
    await edge_tts.Communicate(script, voice).save(path)


def generate_audio(script, voice="en-US-ChristopherNeural"):
    """
    Convert script text to MP3 using Microsoft Neural TTS.

    TEACHING NOTE: edge-tts is an async library (uses Python's async/await).
    Normal Python code is synchronous (one thing at a time).
    asyncio.run() bridges the gap: it runs an async function from sync code.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    asyncio.run(_generate_audio_async(script, voice, tmp.name))
    return tmp.name


# ---------------------------------------------------------------------------
# Step 2: Ken Burns effect on a single image
# ---------------------------------------------------------------------------

def make_ken_burns_clip(image_path, duration, direction=None):
    """
    Load an image and apply a slow Ken Burns zoom effect.

    direction: 'in' = slowly zoom in, 'out' = slowly zoom out
               None = randomly pick one

    How it works:
    - We load the image and crop it to 9:16 ratio using PIL
    - We resize it to slightly LARGER than 1080x1920 (to give zoom room)
    - We use numpy to create a frame-by-frame zoom animation
    - At each frame we crop the correct sub-rectangle from the large image
    """
    if direction is None:
        direction = random.choice(["in", "out"])

    # Amount of zoom (0.12 = 12% larger at full zoom)
    ZOOM = 0.12

    # --- Load and prep image ---
    img = Image.open(image_path).convert("RGB")

    # Crop to 9:16 ratio (center crop)
    img_ratio = img.width / img.height
    target_ratio = REEL_W / REEL_H

    if img_ratio > target_ratio:
        # Image too wide → crop left/right
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        # Image too tall → crop top/bottom
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))

    # First resize to exact target dimensions (fills the full 9:16 frame)
    img = img.resize((REEL_W, REEL_H), Image.LANCZOS)
    # Then scale up slightly to give the zoom animation some room to move
    large_w = int(REEL_W * (1 + ZOOM))
    large_h = int(REEL_H * (1 + ZOOM))
    img = img.resize((large_w, large_h), Image.LANCZOS)
    img_array = np.array(img)

    fps = 30
    total_frames = int(duration * fps)

    def make_frame(t):
        """
        For each moment in time (t), return the correct crop of the image.

        progress goes from 0.0 (start) to 1.0 (end).
        For zoom-in:  we start showing the full large image, then zoom in
                      (show a smaller portion = zoomed in)
        For zoom-out: opposite
        """
        progress = t / duration  # 0.0 → 1.0

        if direction == "in":
            # Start fully zoomed out (showing large_w x large_h)
            # End showing just REEL_W x REEL_H from the center
            current_zoom = ZOOM * progress  # 0 → ZOOM
        else:
            # Start zoomed in, end zoomed out
            current_zoom = ZOOM * (1 - progress)  # ZOOM → 0

        # How much to crop from each edge
        crop_x = int((large_w - REEL_W) * (current_zoom / ZOOM)) // 2 if ZOOM > 0 else 0
        crop_y = int((large_h - REEL_H) * (current_zoom / ZOOM)) // 2 if ZOOM > 0 else 0

        # Clamp to valid range
        crop_x = max(0, min(crop_x, large_w - REEL_W))
        crop_y = max(0, min(crop_y, large_h - REEL_H))

        frame = img_array[crop_y:crop_y + REEL_H, crop_x:crop_x + REEL_W]
        # Safety guarantee: always return exactly REEL_H x REEL_W
        if frame.shape[0] != REEL_H or frame.shape[1] != REEL_W:
            out = np.zeros((REEL_H, REEL_W, 3), dtype=np.uint8)
            h = min(frame.shape[0], REEL_H)
            w = min(frame.shape[1], REEL_W)
            out[:h, :w] = frame[:h, :w]
            return out
        return frame

    # Build clip from the frame function
    # TEACHING NOTE: we MUST set fps here so moviepy knows this clip is 30fps.
    # Without it, CompositeVideoClip doesn't know the frame rate and may
    # render frames at wrong times, causing images to appear cropped/misaligned.
    from moviepy import VideoClip
    clip = VideoClip(make_frame, duration=duration).with_fps(fps)
    return clip


# ---------------------------------------------------------------------------
# Step 3: Build subtitle text overlays
# ---------------------------------------------------------------------------

def build_subtitle_clips(segments, fade_duration=0.15):
    """
    Create styled subtitle overlays for each Whisper segment.

    Style:
    - Bold white text, black stroke (readable on any background)
    - Semi-transparent dark bar behind the text (extra readability)
    - Positioned at 78% down the screen
    """
    clips = []

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        start = seg["start"]
        end = seg["end"]
        seg_duration = end - start
        if seg_duration <= 0:
            continue

        # --- Text clip ---
        try:
            txt = TextClip(
                text=text,
                font_size=58,
                font="Arial",
                color="white",
                stroke_color="black",
                stroke_width=2.5,
                method="caption",
                size=(REEL_W - 80, None),
                text_align="center",
            )
        except Exception:
            # Fallback if font not found
            txt = TextClip(
                text=text,
                font_size=58,
                color="white",
                stroke_color="black",
                stroke_width=2.5,
                method="caption",
                size=(REEL_W - 80, None),
            )

        txt_w, txt_h = txt.size

        # --- Dark background bar behind the text (for readability) ---
        pad = 20
        bar = ColorClip(
            size=(txt_w + pad * 2, txt_h + pad),
            color=(0, 0, 0),
            duration=seg_duration,
        ).with_opacity(0.45)

        # Y position: 78% down the screen
        y_pos = int(REEL_H * 0.78)
        bar_x = (REEL_W - bar.size[0]) // 2
        bar_y = y_pos - pad // 2

        txt = txt.with_duration(seg_duration)
        bar = bar.with_position((bar_x, bar_y))
        txt = txt.with_position(("center", y_pos))

        # Set timing
        bar = bar.with_start(start).with_end(end)
        txt = txt.with_start(start).with_end(end)

        clips.extend([bar, txt])

    return clips


# ---------------------------------------------------------------------------
# Step 4: Transcribe audio for subtitle timestamps
# ---------------------------------------------------------------------------

def transcribe_audio(audio_path):
    """Use Whisper to get per-segment timestamps for subtitles."""
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["segments"]


# ---------------------------------------------------------------------------
# Step 5: Main pipeline
# ---------------------------------------------------------------------------

def create_reel(topic, script, output_path, voiceover=True, voice="en-US-ChristopherNeural", progress_cb=None):
    """
    Full pipeline: topic + script → Instagram Reel.

    Args:
        topic       : Search query for images, e.g. "Spider-Man Marvel"
        script      : Voiceover text (used if voiceover=True)
        output_path : Where to save the .mp4
        voiceover   : If True, adds AI voice + subtitles. If False, silent slideshow.
        voice       : Microsoft Neural TTS voice ID (see VOICES dict above)
        progress_cb : Optional function(message, 0.0–1.0)
    """

    temp_dir = tempfile.mkdtemp()

    try:
        # ----------------------------------------------------------------
        # 1. Fetch images
        # ----------------------------------------------------------------
        image_paths = fetch_images(
            query=topic,
            num_images=8,
            save_dir=os.path.join(temp_dir, "images"),
            progress_cb=progress_cb,
        )

        # ----------------------------------------------------------------
        # 2. Generate voiceover (if enabled)
        # ----------------------------------------------------------------
        audio_clip = None
        total_duration = None

        if voiceover and script.strip():
            if progress_cb:
                progress_cb("Generating voiceover...", 0.22)
            audio_path = generate_audio(script, voice=voice)
            audio_clip = AudioFileClip(audio_path)
            total_duration = audio_clip.duration
        else:
            # No voiceover — each image shows for 4 seconds
            total_duration = len(image_paths) * 4.0

        # ----------------------------------------------------------------
        # 3. Build Ken Burns clips for each image
        # ----------------------------------------------------------------
        if progress_cb:
            progress_cb("Applying Ken Burns effect...", 0.35)

        # TEACHING NOTE: We want each image to show for at least 3 seconds.
        # If the audio is short (e.g. 10s) and we have 8 images, that's only
        # 1.25s per image — way too fast. So we trim the image list to fit.
        # Formula: max images = floor(audio_duration / min_seconds_per_image)
        MIN_PER_IMAGE = 3.0  # seconds — feels cinematic, not rushed
        max_images = max(1, int(total_duration / MIN_PER_IMAGE))
        image_paths = image_paths[:max_images]

        per_image_duration = total_duration / len(image_paths)
        directions = ["in", "out"] * (len(image_paths) // 2 + 1)

        image_clips = []
        for i, img_path in enumerate(image_paths):
            clip = make_ken_burns_clip(
                img_path,
                duration=per_image_duration,
                direction=directions[i],
            )
            image_clips.append(clip)

        # ----------------------------------------------------------------
        # 4. Crossfade between images
        # ----------------------------------------------------------------
        if progress_cb:
            progress_cb("Adding crossfade transitions...", 0.5)

        FADE = 0.4  # seconds of crossfade overlap

        # moviepy 2.0 crossfade: use with_effects([CrossFadeIn(...)])
        from moviepy.video.fx import CrossFadeIn

        timed_clips = []
        current_time = 0.0
        for i, clip in enumerate(image_clips):
            if i == 0:
                timed_clips.append(clip.with_start(0))
            else:
                start_t = current_time - FADE
                faded = clip.with_start(start_t).with_effects([CrossFadeIn(FADE)])
                timed_clips.append(faded)
            current_time += per_image_duration - FADE

        # Layer all image clips together
        slideshow = CompositeVideoClip(timed_clips, size=REEL_SIZE)
        slideshow = slideshow.with_duration(total_duration)

        # ----------------------------------------------------------------
        # 5. Add subtitles (only if voiceover is on)
        # ----------------------------------------------------------------
        all_layers = [slideshow]

        if voiceover and audio_clip is not None:
            if progress_cb:
                progress_cb("Transcribing audio for subtitles...", 0.62)
            segments = transcribe_audio(audio_path)
            subtitle_clips = build_subtitle_clips(segments)
            all_layers.extend(subtitle_clips)

        # ----------------------------------------------------------------
        # 6. Composite everything
        # ----------------------------------------------------------------
        if progress_cb:
            progress_cb("Compositing final video...", 0.78)

        final = CompositeVideoClip(all_layers, size=REEL_SIZE)
        final = final.with_duration(total_duration)

        if voiceover and audio_clip is not None:
            final = final.with_audio(audio_clip)

        # ----------------------------------------------------------------
        # 7. Export
        # ----------------------------------------------------------------
        if progress_cb:
            progress_cb("Exporting Reel (this takes a few minutes)...", 0.88)

        final.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            logger=None,
            threads=4,
        )

        if progress_cb:
            progress_cb("Done! Reel saved to Desktop.", 1.0)

        return output_path

    finally:
        # Clean up temp files
        shutil.rmtree(temp_dir, ignore_errors=True)
        if voiceover and "audio_path" in dir():
            try:
                os.unlink(audio_path)
            except Exception:
                pass
