"""Collect lightweight, free India-relevant trend signals."""

import feedparser
import requests
from datetime import datetime, timezone

from .config import ROOT

NEWS_RSS = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
CRICKET_RSS = "https://news.google.com/rss/search?q=India+cricket+match&hl=en-IN&gl=IN&ceid=IN:en"


def fetch_rss(url: str, limit: int = 20):
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:limit]:
        items.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
        })
    return items


def collect_signals():
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "india_news": fetch_rss(NEWS_RSS),
        "cricket_news": fetch_rss(CRICKET_RSS, limit=10),
        "priority_topics": load_priority_topics(),
    }


def load_priority_topics():
    path = ROOT / "config" / "priority_topics.json"
    with path.open(encoding="utf-8") as f:
        return __import__("json").load(f)
