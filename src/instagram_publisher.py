"""Publish only a Telegram-approved meme to Instagram."""

import sys
import time
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import (
    GRAPH_API,
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_USER_ID,
    STATE_DIR,
    load_json,
    save_json,
)

STATE_FILE = STATE_DIR / "state.json"


def publish():
    state = load_json(STATE_FILE, {})
    candidate = state.get("approved_candidate")

    if not candidate or state.get("status") != "approved_pending_instagram":
        print("No approved candidate is waiting for Instagram publishing.")
        return

    image_url = candidate.get("public_image_url")
    if not image_url:
        raise ValueError("PUBLIC_BASE_URL is not configured; Instagram needs a public HTTPS image URL.")

    container = requests.post(
        f"{GRAPH_API}/{INSTAGRAM_USER_ID}/media",
        data={
            "image_url": image_url,
            "caption": candidate["caption"],
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        },
        timeout=60,
    )
    container.raise_for_status()
    creation_id = container.json()["id"]

    for _ in range(12):
        status = requests.get(
            f"{GRAPH_API}/{creation_id}",
            params={"fields": "status_code", "access_token": INSTAGRAM_ACCESS_TOKEN},
            timeout=30,
        )
        status.raise_for_status()
        if status.json().get("status_code") == "FINISHED":
            break
        time.sleep(5)
    else:
        raise TimeoutError("Instagram media container did not become ready.")

    publish_response = requests.post(
        f"{GRAPH_API}/{INSTAGRAM_USER_ID}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        },
        timeout=60,
    )
    publish_response.raise_for_status()

    state["status"] = "approved_posted"
    state["instagram_media_id"] = publish_response.json().get("id")
    save_json(STATE_FILE, state)
    print("Published approved meme to Instagram.")


if __name__ == "__main__":
    publish()
