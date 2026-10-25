import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from src import generate_meme as generator
from src.config import ROOT, STATE_DIR, TELEGRAM_API, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, load_json, save_json

STATE = STATE_DIR / 'state.json'
OFFSET = STATE_DIR / 'telegram_offset.json'
REJECTED = STATE_DIR / 'rejected_topics.json'

def today():
    return datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d')

def telegram(method, data):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError('Missing TELEGRAM_BOT_TOKEN secret')
    try:
        result = requests.post(f'{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/{method}', json=data, timeout=35).json()
    except requests.RequestException:
        raise RuntimeError('Telegram network request failed') from None
    if not result.get('ok'):
        raise RuntimeError('Telegram: ' + result.get('description', 'request failed'))
    return result['result']

def send_candidate(candidate, image_path):
    if not TELEGRAM_CHAT_ID:
        raise RuntimeError('Missing TELEGRAM_CHAT_ID secret')
    buttons = {'inline_keyboard': [[{'text': 'Approve', 'callback_data': 'approve:' + candidate['id']}, {'text': 'Reject and regenerate', 'callback_data': 'reject:' + candidate['id']}]]}
    with image_path.open('rb') as photo:
        try:
            payload = requests.post(f'{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendPhoto', data={'chat_id': TELEGRAM_CHAT_ID, 'caption': (candidate['topic'] + '\n\n' + candidate['caption'] + '\n\n' + candidate.get('why_relevant', ''))[:1000], 'reply_markup': json.dumps(buttons)}, files={'photo': photo}, timeout=60).json()
        except requests.RequestException:
            raise RuntimeError('Telegram photo upload failed') from None
    if not payload.get('ok'):
        raise RuntimeError('Telegram: ' + payload.get('description', 'photo upload failed'))
    return payload['result']['message_id']

def generate():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError('Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets first')
    state = load_json(STATE, {})
    if state.get('date') == today() and state.get('status') not in ('idle', 'rejected', 'generating'):
        print('No generation needed; status:', state.get('status'))
        return
    if state.get('date') != today():
        state = {'date': today(), 'attempts': 0, 'rejected': []}
    if state.get('attempts', 0) >= 10:
        print('Daily candidate limit reached; no additional API request made')
        return
    state['attempts'] = state.get('attempts', 0) + 1
    signals = generator.collect_signals()
    if not generator.GEMINI_API_KEY:
        raise RuntimeError('Missing GEMINI_API_KEY; refusing to send a generic fallback')
    idea = generator.ask_gemini(signals, load_json(REJECTED, []))
    if not isinstance(idea.get('caption'), str) or not idea['caption'].strip() or not idea.get('topic'):
        raise RuntimeError('Gemini returned an invalid meme concept')
    candidate_id = 'meme_' + today().replace('-', '') + '_' + str(state['attempts'])
    path = ROOT / 'generated' / (candidate_id + '.jpg')
    generator.render_meme(idea, path)
    from PIL import Image
    with Image.open(path) as image:
        image.convert('RGB').save(path, 'JPEG', quality=92)
    candidate = dict(idea, id=candidate_id, date=today(), attempt=state['attempts'], image_path=path.relative_to(ROOT).as_posix(), public_image_url=generator.PUBLIC_BASE_URL + '/generated/' + path.name)
    candidate['telegram_message_id'] = send_candidate(candidate, path)
    state.update(status='pending', current_candidate=candidate, approved_candidate=None)
    save_json(STATE, state)
    print('Candidate delivered to Telegram:', candidate_id)

def moderate():
    moderator = os.getenv('TELEGRAM_MODERATOR_USER_ID', '').strip()
    if not moderator:
        raise RuntimeError('Add TELEGRAM_MODERATOR_USER_ID secret; moderation fails closed without it')
    offset = load_json(OFFSET, {'next': 0})['next']
    updates = telegram('getUpdates', {'offset': offset, 'timeout': 0, 'allowed_updates': ['callback_query']})
    for update in updates:
        callback = update.get('callback_query')
        if callback:
            state = load_json(STATE, {})
            candidate = state.get('current_candidate') or {}
            message = callback.get('message', {})
            action, _, candidate_id = callback.get('data', '').partition(':')
            authorized = str(callback.get('from', {}).get('id', '')) == moderator and str(message.get('chat', {}).get('id', '')) == str(TELEGRAM_CHAT_ID)
            active = state.get('status') == 'pending' and state.get('date') == today() and candidate_id == candidate.get('id') and message.get('message_id') == candidate.get('telegram_message_id')
            if not authorized or not active or action not in ('approve', 'reject'):
                telegram('answerCallbackQuery', {'callback_query_id': callback['id'], 'text': 'Unauthorized or expired decision'})
            else:
                if action == 'approve':
                    state.update(status='approved_pending_instagram', approved_candidate=candidate)
                else:
                    rejected = load_json(REJECTED, [])
                    rejected.append(candidate)
                    save_json(REJECTED, rejected[-100:])
                    state.setdefault('rejected', []).append(candidate_id)
                    state.update(status='rejected', current_candidate=None)
                save_json(STATE, state)
                telegram('answerCallbackQuery', {'callback_query_id': callback['id'], 'text': 'Approved' if action == 'approve' else 'Rejected; replacement queued'})
                telegram('editMessageReplyMarkup', {'chat_id': TELEGRAM_CHAT_ID, 'message_id': message['message_id'], 'reply_markup': {'inline_keyboard': []}})
        save_json(OFFSET, {'next': update['update_id'] + 1})
    state = load_json(STATE, {})
    if state.get('date') == today() and state.get('status') == 'rejected':
        generate()
    state = load_json(STATE, {})
    if state.get('date') != today() or state.get('status') != 'approved_pending_instagram':
        print('No approved candidate waiting for publication')
        return
    if os.getenv('INSTAGRAM_PUBLISH_ENABLED', '').lower() != 'true':
        print('Approved candidate saved. Instagram publishing is disabled for testing.')
        return
    candidate = state['approved_candidate']
    response = requests.get(candidate['public_image_url'], timeout=30)
    if response.status_code != 200 or not response.headers.get('Content-Type', '').startswith('image/'):
        raise RuntimeError('Approved image is not yet publicly available; retry after image hosting deployment')
    state['status'] = 'publishing'
    save_json(STATE, state)
    try:
        from src.instagram_publisher import publish
        transient = dict(state, status='approved_pending_instagram')
        save_json(STATE, transient)
        publish()
    except Exception:
        state['status'] = 'publish_needs_review'
        save_json(STATE, state)
        raise RuntimeError('Publishing failed; inspect Instagram before retrying to avoid duplicates') from None
    telegram('sendMessage', {'chat_id': TELEGRAM_CHAT_ID, 'text': 'Approved meme published to Instagram: ' + candidate['id']})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['generate', 'moderate'])
    args = parser.parse_args()
    generate() if args.mode == 'generate' else moderate()
