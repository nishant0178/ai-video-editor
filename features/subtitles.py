"""
Auto Subtitles — Standalone Feature
=====================================
Takes any existing video, transcribes it with Whisper,
and burns subtitles directly into the video.

Useful when you have existing clips (Marvel trailers, comic footage)
and just want to add captions before posting.
"""

import whisper
from moviepy import CompositeVideoClip, TextClip, VideoFileClip

from features.script_to_video import build_subtitle_clips  # reuse our subtitle builder


def burn_subtitles(video_path, output_path, progress_cb=None):
    """
    Transcribe a video with Whisper and burn subtitles into it.

    Args:
        video_path  : Path to the input video
        output_path : Where to save the captioned video
        progress_cb : Optional function(message, 0.0–1.0) for UI updates
    """

    # Load the video
    if progress_cb:
        progress_cb("Loading video...", 0.1)
    clip = VideoFileClip(video_path)

    # Transcribe using Whisper
    # Whisper is smart enough to work directly on video files —
    # it extracts the audio internally
    if progress_cb:
        progress_cb("Transcribing audio (this takes ~30s)...", 0.3)
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    segments = result["segments"]

    # Build subtitle overlays using the same function from script_to_video
    if progress_cb:
        progress_cb("Adding subtitles...", 0.65)
    subtitle_clips = build_subtitle_clips(segments, clip.size)

    # Layer subtitles on top of the video
    final = CompositeVideoClip([clip] + subtitle_clips)

    # Export
    if progress_cb:
        progress_cb("Exporting...", 0.85)
    final.write_videofile(
        output_path,
        fps=clip.fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    if progress_cb:
        progress_cb("Done! Subtitles added.", 1.0)

    return output_path
