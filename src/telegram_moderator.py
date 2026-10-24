"""Poll Telegram for approval/rejection and update meme state."""

import json
import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import (
    STATE_DIR,
    TELEGRAM_API,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    load_json,
    save_json,
)
from src.generate_meme import main as generate_next

STATE_FILE = STATE_DIR / "state.json"
REJECTED_FILE = STATE_DIR / "rejected_topics.json"
OFFSET_FILE = STATE_DIR / "telegram_offset.txt"


def get_updates():
    offset = 0
    if OFFSET_FILE.exists():
        offset = int(OFFSET_FILE.read_text().strip() or 0)

    response = requests.get(
        f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
        params={"offset": offset, "timeout": 25, "allowed_updates": json.dumps(["callback_query"])},
        timeout=35,
    )
    response.raise_for_status()
    return response.json().get("result", [])


def answer_callback(callback_id, text):
    requests.post(
        f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": text},
        timeout=20,
    )


def edit_message(message_id, text):
    requests.post(
        f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/editMessageCaption",
        json={"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id, "caption": text},
        timeout=20,
    )


def process_callback(callback):
    state = load_json(STATE_FILE, {})
    candidate = state.get("current_candidate")
    if not candidate:
        return

    data = callback.get("data", "")
    action, _, candidate_id = data.partition(":")
    if candidate_id != candidate["id"]:
        answer_callback(callback["id"], "This candidate is no longer active.")
        return

    if action == "approve":
        state["status"] = "approved_pending_instagram"
        state["approved_candidate"] = candidate
        save_json(STATE_FILE, state)
        answer_callback(callback["id"], "Approved. Publishing to Instagram.")
        edit_message(
            candidate.get("telegram_message_id"),
            "✅ Approved. Publishing to Instagram...",
        )
    elif action == "reject":
        rejected = load_json(REJECTED_FILE, [])
        rejected.append({
            "id": candidate["id"],
            "topic": candidate["topic"],
            "caption": candidate["caption"],
            "category": candidate.get("category"),
        })
        save_json(REJECTED_FILE, rejected)

        state["rejected"].append(candidate["id"])
        state["current_candidate"] = None
        state["status"] = "rejected"
        save_json(STATE_FILE, state)

        answer_callback(callback["id"], "Rejected. Generating a new meme.")
        edit_message(
            candidate.get("telegram_message_id"),
            "❌ Rejected. Generating another meme...",
        )
        generate_next()


def main():
    updates = get_updates()
    for update in updates:
        callback = update.get("callback_query")
        if callback:
            process_callback(callback)
        OFFSET_FILE.write_text(str(update["update_id"] + 1))


if __name__ == "__main__":
    main()
