# Indian Meme Bot

Daily India-trend meme generator with Telegram human approval and Instagram publishing.

## Flow

1. GitHub Actions runs daily.
2. It collects India-relevant trends from Google News RSS, Google Trends India, cricket sources, and a priority topic file.
3. It generates a meme concept and renders an image using Pillow.
4. It sends the meme to a private Telegram channel with **Approve** and **Reject** buttons.
5. On approval, it publishes the exact approved image to Instagram.
6. On rejection, it generates another candidate and sends it to Telegram again.
7. Once one meme is approved for the day, no further candidates are generated.

## Required GitHub secrets

Add these under **Settings → Secrets and variables → Actions**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`
- `PERPLEXITY_API_KEY`

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

## Instagram requirements

- Instagram Business or Creator account.
- Long-lived Instagram access token generated through Meta's Instagram API setup.
- `instagram_business_basic` and `instagram_business_content_publish` permissions.
- Public HTTPS URL for the generated meme image.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/generate_meme.py --dry-run
```

## Workflows

- `.github/workflows/generate-meme.yml` — daily candidate generation.
- `.github/workflows/telegram-moderator.yml` — polls Telegram approval buttons.
