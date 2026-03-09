import os


def get_output_path(input_path=None, suffix="_output", ext=".mp4"):
    """
    Returns a path to save the output file.

    If input_path is given → saves next to that file.
    If not → saves to the user's Desktop.

    Example:
        input_path = "/Videos/spiderman.mp4", suffix = "_reel"
        → returns "/Videos/spiderman_reel.mp4"
    """
    if input_path:
        base = os.path.splitext(input_path)[0]
        return f"{base}{suffix}{ext}"

    desktop = os.path.expanduser("~/Desktop")
    return os.path.join(desktop, f"reel{suffix}{ext}")


def ensure_dir(path):
    """Create a folder (and any parent folders) if it doesn't exist."""
    os.makedirs(path, exist_ok=True)
