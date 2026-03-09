"""
Silence Remover
================
Detects and cuts silent sections from a video.
Result: a tighter, faster-paced video with no dead air.

TEACHING NOTES:
  pydub   = audio analysis library. Think of audio as a waveform —
            silence is where the waveform is very small (low dB).
            pydub scans the audio and finds ranges where dB < threshold.
  moviepy = once we know WHICH parts to keep, moviepy cuts the video
            at those points and joins the pieces back together.

  dB (decibels) = unit of loudness. Silence is around -40 to -50 dB.
  The threshold (-40 dB default) means: "treat anything quieter than
  this as silence."
"""

from pydub import AudioSegment
from pydub import silence as pydub_silence
from moviepy import VideoFileClip, concatenate_videoclips


def remove_silence(
    video_path,
    output_path,
    silence_thresh=-40,    # dB — anything quieter than this = silence
    min_silence_len=500,   # milliseconds — ignore silences shorter than this
    padding_ms=100,        # milliseconds — keep a tiny bit of silence at edges (sounds natural)
    progress_cb=None,
):
    """
    Remove silent sections from a video.

    Args:
        video_path       : Path to input video
        output_path      : Where to save the result
        silence_thresh   : dB threshold. -40 is a good default.
                           Lower = stricter (cuts more). Higher = more lenient.
        min_silence_len  : Minimum silence length (ms) to cut. 500ms = 0.5 seconds.
                           We don't cut tiny pauses — only proper dead air.
        padding_ms       : Keep this many ms around each kept segment.
                           Without padding, cuts can sound abrupt.
        progress_cb      : Optional function(message, 0.0–1.0) for UI updates
    """

    # --- Step 1: Analyse audio ---
    if progress_cb:
        progress_cb("Analysing audio...", 0.2)

    # Load audio from the video file using pydub
    audio = AudioSegment.from_file(video_path)

    # detect_silence returns a list of [start_ms, end_ms] ranges that are silent
    silent_ranges = pydub_silence.detect_silence(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
    )

    # --- Step 2: Convert silent ranges → non-silent ranges ---
    # silent_ranges tells us what to REMOVE.
    # We flip it to get what to KEEP.
    total_duration_ms = len(audio)
    non_silent_ranges = []

    prev_end = 0
    for start_ms, end_ms in silent_ranges:
        # Add padding — keep a little audio before the silence starts
        keep_start = prev_end
        keep_end = start_ms + padding_ms  # keep a tiny bit into the silence

        if keep_start < keep_end:
            non_silent_ranges.append((keep_start / 1000, keep_end / 1000))  # convert ms → seconds

        prev_end = max(prev_end, end_ms - padding_ms)  # start next segment slightly before silence ends

    # Don't forget the last chunk after the final silence
    if prev_end < total_duration_ms:
        non_silent_ranges.append((prev_end / 1000, total_duration_ms / 1000))

    if not non_silent_ranges:
        # No silence found — nothing to cut
        if progress_cb:
            progress_cb("No silence detected. Nothing to cut.", 1.0)
        return None

    # --- Step 3: Cut video at non-silent ranges ---
    if progress_cb:
        progress_cb(f"Cutting {len(silent_ranges)} silent sections...", 0.6)

    clip = VideoFileClip(video_path)
    subclips = []
    for start_s, end_s in non_silent_ranges:
        # Clamp to video duration to avoid out-of-bounds errors
        end_s = min(end_s, clip.duration)
        if start_s < end_s:
            subclips.append(clip.subclip(start_s, end_s))

    # Join all the kept pieces back together
    final = concatenate_videoclips(subclips)

    # --- Step 4: Export ---
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
        progress_cb("Done! Silence removed.", 1.0)

    return output_path
