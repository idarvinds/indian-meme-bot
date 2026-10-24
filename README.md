# Indian Meme Bot

Daily India-trend meme generator with Telegram human approval and Instagram publishing.

## Flow

1. GitHub Actions runs daily at 9:00 AM IST.
2. It collects India-relevant trends from Google News RSS, cricket news, and a priority topic file.
3. It asks Gemini for a safe, topical meme concept and Hinglish caption.
4. It renders a 1080x1080 meme image using Pillow.
5. It sends the meme to a private Telegram channel with **Approve** and **Reject** buttons.
6. On approval, it publishes the exact approved image to Instagram.
7. On rejection, it generates another candidate and sends it to Telegram again.
8. Once one meme is approved for the day, no further candidates are generated.

## Required GitHub secrets

Add these under **Settings → Secrets and variables → Actions**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY`
- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`

`GEMINI_MODEL` defaults to `gemini-2.5-flash`.

## Gemini free tier

The bot normally uses one Gemini request per day. Each rejected candidate uses one additional request. The configured maximum is 10 rejections per day, so worst-case usage is 11 requests daily.

Check your project-specific quota at: https://aistudio.google.com/rate-limit

## Instagram requirements

- Instagram Business or Creator account.
- Long-lived Instagram access token generated through Meta's Instagram API setup.
- `instagram_business_basic` and `instagram_business_content_publish` permissions.
- GitHub Pages enabled so generated images have public HTTPS URLs.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.generate_meme --dry-run
```
