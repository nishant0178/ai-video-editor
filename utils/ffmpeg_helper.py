from moviepy import VideoFileClip


def crop_to_vertical(clip):
    """
    Crops any video/image clip to 9:16 ratio (Instagram Reels / YouTube Shorts).

    How it works:
    - If the video is too WIDE (landscape): we chop off the left and right sides
    - If the video is too TALL: we chop off the top and bottom
    - Then we resize to exactly 1080x1920 (standard Reels resolution)

    This is called "center cropping" — we always keep the middle of the frame.
    """
    target_ratio = 9 / 16  # width / height for vertical video
    w, h = clip.size
    current_ratio = w / h

    if current_ratio > target_ratio:
        # Video is wider than 9:16 — crop the sides
        new_w = int(h * target_ratio)
        x_center = w // 2
        clip = clip.crop(x1=x_center - new_w // 2, x2=x_center + new_w // 2)

    elif current_ratio < target_ratio:
        # Video is taller than 9:16 — crop top and bottom
        new_h = int(w / target_ratio)
        y_center = h // 2
        clip = clip.crop(y1=y_center - new_h // 2, y2=y_center + new_h // 2)

    # Resize to 1080x1920 — the standard HD vertical resolution
    return clip.resize((1080, 1920))
