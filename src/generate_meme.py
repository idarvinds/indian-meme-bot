"""Generate one topical Indian meme candidate using Gemini and send it to Telegram."""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import (
    GENERATED_DIR,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    PUBLIC_BASE_URL,
    ROOT,
    STATE_DIR,
    TELEGRAM_API,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    load_json,
    save_json,
)
from src.trends import collect_signals

STATE_FILE = STATE_DIR / "state.json"
REJECTED_FILE = STATE_DIR / "rejected_topics.json"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)


def ask_gemini(signals, rejected):
    if not GEMINI_API_KEY:
        return fallback_idea(signals)

    headlines = "\n".join(f"- {item['title']}" for item in signals["india_news"][:25])
    cricket = "\n".join(f"- {item['title']}" for item in signals["cricket_news"][:8])
    evergreen = "\n".join(
        f"- {item}" for item in signals["priority_topics"]["evergreen_topics"]
    )
    blocked = ", ".join(signals["priority_topics"]["blocked_keywords"])
    rejected_text = "\n".join(
        f"- {item.get('topic', '')}: {item.get('caption', '')}"
        for item in rejected[-10:]
    )

    prompt = f"""You create safe, funny, highly relatable Indian memes for Instagram.
Use only current, broadly relevant Indian topics. Avoid politics, religion, caste, tragedy, sexual content, and personal attacks.
Blocked concepts: {blocked}.

Recent Indian news:
{headlines}

Cricket news:
{cricket}

Evergreen Indian humor topics:
{evergreen}

Do not repeat these rejected ideas:
{rejected_text}

Return ONLY valid JSON with these keys:
topic, why_relevant, category, caption, safety_score, relatability_score.

Rules:
- Caption must be original, Hinglish-friendly, and under 180 characters.
- Choose a broadly relatable Indian topic with clear meme potential.
- Do not use copyrighted dialogue, celebrity photos, or brand names in the caption.
- safety_score and relatability_score must be integers from 1 to 10.
"""

    response = requests.post(
        GEMINI_URL,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        },
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.9,
                "responseMimeType": "application/json",
            },
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(content)


def fallback_idea(signals):
    topics = signals["priority_topics"]["evergreen_topics"]
    topic = random.choice(topics)
    return {
        "topic": topic,
        "why_relevant": "Evergreen Indian relatable humor used when Gemini is unavailable or quota is exhausted.",
        "category": "daily_life",
        "caption": "When the plan is simple, but the group chat turns it into a project.",
        "safety_score": 10,
        "relatability_score": 8,
    }


def render_meme(idea, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1080, 1080), "#101820")
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 54
        )
    except OSError:
        font = ImageFont.load_default()

    caption = idea["caption"]
    words = caption.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) > 920:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    y = 380
    for line in lines:
        width = draw.textlength(line, font=font)
        draw.text(((1080 - width) / 2, y), line, font=font, fill="white")
        y += 72

    draw.text((60, 990), "Indian Meme Bot", font=font, fill="#8ab4f8")
    image.save(output_path, "PNG")


def send_telegram_candidate(candidate, image_path: Path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID GitHub secrets are required."
        )

    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with image_path.open("rb") as photo:
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": (
                    f"🇮🇳 Meme candidate #{candidate['attempt']} — {candidate['date']}\n\n"
                    f"Topic: {candidate['topic']}\n\n"
                    f"{candidate['caption']}\n\n"
                    "Approve to publish to Instagram."
                ),
            },
            files={"photo": photo},
            timeout=60,
        )
    response.raise_for_status()
    return response.json()["result"]["message_id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = load_json(STATE_FILE, {})
    today = datetime.now().strftime("%Y-%m-%d")

    if state.get("date") == today and state.get("status") in (
        "pending",
        "approved_posted",
    ):
        print("A candidate is already pending or approved for today.")
        return

    if state.get("date") != today:
        state = {
            "date": today,
            "status": "generating",
            "attempts": 0,
            "current_candidate": None,
            "approved_candidate": None,
            "rejected": [],
        }

    state["attempts"] += 1
    attempt = state["attempts"]

    if attempt > 10:
        state["status"] = "rejected_limit_reached"
        save_json(STATE_FILE, state)
        print("Rejected limit reached for today.")
        return

    signals = collect_signals()
    rejected = load_json(REJECTED_FILE, [])

    try:
        idea = ask_gemini(signals, rejected)
    except Exception as exc:
        print(f"Gemini generation failed, using fallback: {exc}")
        idea = fallback_idea(signals)

    candidate_id = f"meme_{today.replace('-', '')}_{attempt}"
    image_path = GENERATED_DIR / f"{candidate_id}.png"
    render_meme(idea, image_path)

    relative_image_path = image_path.relative_to(ROOT).as_posix()
    candidate = {
        "id": candidate_id,
        "date": today,
        "attempt": attempt,
        "topic": idea["topic"],
        "category": idea.get("category", "daily_life"),
        "caption": idea["caption"],
        "why_relevant": idea.get("why_relevant", ""),
        "image_path": relative_image_path,
        "public_image_url": (
            f"{PUBLIC_BASE_URL}/{relative_image_path}" if PUBLIC_BASE_URL else ""
        ),
    }

    state["current_candidate"] = candidate
    state["status"] = "pending"

    if args.dry_run:
        print(json.dumps(candidate, indent=2, ensure_ascii=False))
        save_json(STATE_FILE, state)
        return

    message_id = send_telegram_candidate(candidate, image_path)
    candidate["telegram_message_id"] = message_id
    save_json(STATE_FILE, state)
    print(f"Sent candidate {candidate_id} to Telegram.")


if __name__ == "__main__":
    main()
