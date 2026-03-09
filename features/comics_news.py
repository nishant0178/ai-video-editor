"""
Comics News Fetcher
====================
Fetches latest news, scores articles by virality, and caches daily.
Cache lives at ~/.cache/ai_video_editor/news_{category}.json
If cache < 24 hours old, returns cached results — no extra requests.
"""

import json
import os
import time
from datetime import datetime, timezone

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# Default search queries per category
CATEGORY_QUERIES = {
    "All":    "marvel dc anime manhwa comics news",
    "Marvel": "Marvel comics MCU news",
    "DC":     "DC comics DCU news",
    "Anime":  "anime news new season episode",
    "Manhwa": "manhwa webtoon new chapter news",
}

# Words that signal a story people actually click on
_VIRAL_WORDS = [
    "confirm", "reveal", "shock", "official", "announce", "exclusive",
    "first look", "trailer", "cast", "return", "cancel", "delay", "end",
    "final", "death", "alive", "vs", "beat", "defeat", "strongest",
    "leaked", "break", "record", "ban", "contro", "surpris", "unexpected",
    "wildest", "insane", "destroy", "comeback", "season", "release",
]

CACHE_DIR = os.path.expanduser("~/.cache/ai_video_editor")
CACHE_TTL  = 60 * 60 * 24  # 24 hours in seconds


def _cache_path(category: str, query: str) -> str:
    safe = (query or category).lower().replace(" ", "_")[:40]
    return os.path.join(CACHE_DIR, f"news_{safe}.json")


def _load_cache(path: str):
    """Return (articles, fetched_at_str) if cache is fresh, else (None, None)."""
    try:
        with open(path) as f:
            data = json.load(f)
        fetched_at = data.get("fetched_at", 0)
        if time.time() - fetched_at < CACHE_TTL:
            return data["articles"], _age_label(fetched_at)
    except Exception:
        pass
    return None, None


def _save_cache(path: str, articles: list):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"fetched_at": time.time(), "articles": articles}, f)


def _age_label(fetched_at: float) -> str:
    age = int(time.time() - fetched_at)
    if age < 60:
        return "just now"
    if age < 3600:
        return f"{age // 60}m ago"
    if age < 86400:
        return f"{age // 3600}h ago"
    return f"{age // 86400}d ago"


def _virality_score(article: dict) -> int:
    """Score 0–100 based on how click-worthy the title + body is."""
    text = (article.get("title", "") + " " + article.get("body", "")).lower()
    score = 0
    for word in _VIRAL_WORDS:
        if word in text:
            score += 10
    # Recency bonus — newer = higher
    date_str = article.get("date", "")
    if date_str:
        try:
            # DuckDuckGo returns ISO format
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if age_hours < 6:
                score += 30
            elif age_hours < 24:
                score += 15
            elif age_hours < 72:
                score += 5
        except Exception:
            pass
    return score


def _fetch_from_web(search_term: str, max_results: int) -> list:
    articles = []
    for attempt in range(3):
        try:
            with DDGS(verify=False) as ddgs:
                results = ddgs.news(search_term, max_results=max_results)
                for r in results:
                    articles.append({
                        "title":  r.get("title", ""),
                        "body":   r.get("body", ""),
                        "source": r.get("source", ""),
                        "url":    r.get("url", ""),
                        "date":   r.get("date", ""),
                    })
            if articles:
                break
        except TypeError:
            try:
                with DDGS() as ddgs:
                    results = ddgs.news(search_term, max_results=max_results)
                    for r in results:
                        articles.append({
                            "title":  r.get("title", ""),
                            "body":   r.get("body", ""),
                            "source": r.get("source", ""),
                            "url":    r.get("url", ""),
                            "date":   r.get("date", ""),
                        })
                if articles:
                    break
            except Exception:
                pass
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1)
    return articles


def fetch_news(category="All", query=None, max_results=20, force_refresh=False):
    """
    Fetch and return news articles sorted by virality score.

    Returns:
        (articles, cache_age_str)
        cache_age_str is e.g. "2h ago" or "just now" — shown in the UI.
    """
    search_term = query.strip() if query and query.strip() else CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["All"])
    path = _cache_path(category, query or "")

    if not force_refresh:
        cached, age = _load_cache(path)
        if cached:
            return cached, age

    articles = _fetch_from_web(search_term, max_results * 2)  # fetch more so we can filter

    # Score + sort by virality (highest first)
    for a in articles:
        a["_score"] = _virality_score(a)
    articles.sort(key=lambda a: a["_score"], reverse=True)

    # Keep top max_results
    articles = articles[:max_results]

    if articles:
        _save_cache(path, articles)

    return articles, "just now"
