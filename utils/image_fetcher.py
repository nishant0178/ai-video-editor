"""
Image Fetcher
=============
Searches DuckDuckGo for images (with Bing as fallback) and downloads them ALL IN PARALLEL.

TEACHING NOTES:
  ThreadPoolExecutor = runs multiple downloads at the same time.
  SSL verify=False   = Mac Python sometimes has broken SSL certs.
                       For a personal local tool this is fine.
  Bing fallback      = if DuckDuckGo rate-limits us, we scrape Bing image search.
                       Both return real web images — perfect for superhero/comics.
"""

import os
import re
import ssl
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

import requests
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from PIL import Image

# Fix for Mac SSL certificate issues — disables SSL verification for image downloads
# This is fine for a personal local tool
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _download_one(args):
    """Download a single image URL. Returns save_path or None on failure."""
    index, url, save_dir = args
    try:
        # Use urllib with our permissive SSL context
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=_ssl_ctx) as resp:
            data = resp.read()
        img = Image.open(BytesIO(data)).convert("RGB")
        if img.width < 400 or img.height < 400:
            return None
        save_path = os.path.join(save_dir, f"img_{index:02d}.jpg")
        img.save(save_path, "JPEG", quality=90)
        return save_path
    except Exception:
        return None


def _search_bing_fallback(query, n):
    """
    Scrape Bing Images as a fallback when DuckDuckGo fails.

    TEACHING NOTE: Bing embeds image URLs in its HTML as JSON data.
    We use regex to pull them out — no API key needed.
    murl = "media URL" = the full-size image URL.
    """
    try:
        url = "https://www.bing.com/images/search"
        params = {"q": query, "count": n * 3, "first": 1}
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(url, params=params, headers=headers, verify=False, timeout=10)
        urls = re.findall(r'"murl":"(https?://[^"]+)"', resp.text)
        return urls[:n * 3]
    except Exception:
        return []


def fetch_images(query, num_images=6, save_dir=None, progress_cb=None):
    """Search DuckDuckGo (with Bing fallback) and download images in parallel."""

    if save_dir is None:
        save_dir = tempfile.mkdtemp()
    os.makedirs(save_dir, exist_ok=True)

    if progress_cb:
        progress_cb(f"Searching: {query}...", 0.04)

    # Search DuckDuckGo — disable SSL verification to fix Mac cert issues
    image_urls = []
    for attempt in range(3):
        try:
            with DDGS(verify=False) as ddgs:
                results = ddgs.images(query, max_results=num_images * 4, safesearch="moderate")
                for r in results:
                    image_urls.append(r["image"])
            if image_urls:
                break
        except TypeError:
            # Older version of duckduckgo_search doesn't support verify=
            try:
                with DDGS() as ddgs:
                    results = ddgs.images(query, max_results=num_images * 4, safesearch="moderate")
                    for r in results:
                        image_urls.append(r["image"])
                if image_urls:
                    break
            except Exception:
                pass
        except Exception:
            pass

        if attempt < 2:
            time.sleep(2)

    # Bing fallback — if DuckDuckGo returned nothing
    if not image_urls:
        if progress_cb:
            progress_cb("DuckDuckGo unavailable, trying Bing...", 0.06)
        image_urls = _search_bing_fallback(query, num_images)

    if not image_urls:
        raise ValueError(
            f"Could not search images for '{query}'.\n\n"
            "Try running this in Terminal to fix SSL:\n"
            "/Applications/Python\\ 3.14/Install\\ Certificates.command"
        )

    if progress_cb:
        progress_cb(f"Downloading {num_images} images in parallel...", 0.08)

    downloaded = []
    args = [(i, url, save_dir) for i, url in enumerate(image_urls)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_download_one, arg): arg for arg in args}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                downloaded.append(result)
                if progress_cb:
                    progress_cb(
                        f"Downloaded {len(downloaded)}/{num_images} images...",
                        0.08 + 0.12 * (len(downloaded) / num_images),
                    )
            if len(downloaded) >= num_images:
                for f in futures:
                    f.cancel()
                break

    if not downloaded:
        raise ValueError(f"Could not download any images for '{query}'. Check your internet connection.")

    return sorted(downloaded)
