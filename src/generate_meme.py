"""Generate one topical Indian meme candidate and send it to Telegram."""

import argparse
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import (
    GENERATED_DIR,
    PERPLEXITY_API_KEY,
    PUBLIC_BASE_URL,
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


def ask_perplexity(signals, rejected):
    if not PERPLEXITY_API_KEY:
        return fallback_idea(signals)

    headlines = "\n".join(
        f"- {item['title']}" for item in signals["india_news"][:25]
    )
    cricket = "\n".join(f"- {item['title']}" for item in signals["cricket_news"][:8])
    evergreen = "\n".join(f"- {item}" for item in signals["priority_topics"]["evergreen_topics"])
    blocked = ", ".join(signals["priority_topics"]["blocked_keywords"])
    rejected_text = "\n".join(f"- {item.get('topic', '')}: {item.get('caption', '')}" for item in rejected[-10:])

    prompt = f"""You create safe, funny, highly relatable Indian memes for Instagram.
Use only current, broadly relevant Indian topics. Avoid politics, religion, caste, tragedy, sexual content, and personal attacks.
Blocked concepts: {blocked}.

Recent Indian news:\n{headlines}

Cricket news:\n{cricket}

Evergreen Indian humor topics:\n{evergreen}

Do not repeat these rejected ideas:\n{rejected_text}

Return only valid JSON with keys: topic, why_relevant, category, caption, safety_score, relatability_score.
Caption must be original, Hinglish-friendly, under 180 characters, and suitable for a simple image meme.
"""

    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "sonar",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
        },
        timeout=45,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    start, end = content.find("{"), content.rfind("}") + 1
    return json.loads(content[start:end])


def fallback_idea(signals):
    topics = signals["priority_topics"]["evergreen_topics"]
    topic = random.choice(topics)
    return {
        "topic": topic,
        "why_relevant": "Evergreen Indian relatable humor used when live trend generation is unavailable.",
        "category": "daily_life",
        "caption": "When the plan is simple, but the group chat turns it into a project.",
        "safety_score": 10,
        "relatability_score": 8,
    }


def render_meme(idea, output_path: Path):
    image = Image.new("RGB", (1080, 1080), "#101820")
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 54)
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
                    f"Approve to publish to Instagram."
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

    if state.get("date") == today and state.get("status") in ("pending", "approved_posted"):
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
    idea = ask_perplexity(signals, rejected)

    candidate_id = f"meme_{today.replace('-', '')}_{attempt}"
    image_path = GENERATED_DIR / f"{candidate_id}.png"
    render_meme(idea, image_path)

    candidate = {
        "id": candidate_id,
        "date": today,
        "attempt": attempt,
        "topic": idea["topic"],
        "category": idea.get("category", "daily_life"),
        "caption": idea["caption"],
        "why_relevant": idea.get("why_relevant", ""),
        "image_path": str(image_path.relative_to(image_path.parents[2])),
        "public_image_url": f"{PUBLIC_BASE_URL}/{image_path.relative_to(image_path.parents[2])}" if PUBLIC_BASE_URL else "",
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
