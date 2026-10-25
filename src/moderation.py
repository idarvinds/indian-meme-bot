import os
from src import pipeline

ORIGINAL_TELEGRAM = pipeline.telegram
UI_METHODS = {'answerCallbackQuery', 'editMessageReplyMarkup', 'sendMessage'}

def telegram(method, data):
    try:
        result = ORIGINAL_TELEGRAM(method, data)
    except RuntimeError:
        if method in UI_METHODS:
            print('Warning: Telegram UI notification failed; saved decision processing continues:', method)
            return None
        raise
    if method == 'getUpdates':
        print('Telegram updates received:', len(result))
        for update in result:
            callback = update.get('callback_query')
            if not callback:
                continue
            state = pipeline.load_json(pipeline.STATE, {})
            candidate = state.get('current_candidate') or {}
            message = callback.get('message', {})
            action, _, candidate_id = callback.get('data', '').partition(':')
            checks = {
                'moderator_matches': str(callback.get('from', {}).get('id', '')) == os.getenv('TELEGRAM_MODERATOR_USER_ID', '').strip(),
                'chat_matches': str(message.get('chat', {}).get('id', '')) == str(pipeline.TELEGRAM_CHAT_ID).strip(),
                'message_matches': message.get('message_id') == candidate.get('telegram_message_id'),
                'candidate_matches': candidate_id == candidate.get('id'),
                'pending': state.get('status') == 'pending',
                'today': state.get('date') == pipeline.today(),
                'action_valid': action in ('approve', 'reject'),
            }
            print('Callback validation:', checks)
    return result

def main():
    moderator = os.getenv('TELEGRAM_MODERATOR_USER_ID', '').strip()
    if not moderator.isdigit():
        raise RuntimeError('Add TELEGRAM_MODERATOR_USER_ID as your positive numeric PERSONAL user ID in repository Actions Secrets; not the channel or bot ID.')
    os.environ['TELEGRAM_MODERATOR_USER_ID'] = moderator
    pipeline.TELEGRAM_CHAT_ID = str(pipeline.TELEGRAM_CHAT_ID).strip()
    bot = ORIGINAL_TELEGRAM('getMe', {})
    chat = ORIGINAL_TELEGRAM('getChat', {'chat_id': pipeline.TELEGRAM_CHAT_ID})
    if str(chat['id']) != pipeline.TELEGRAM_CHAT_ID:
        raise RuntimeError('TELEGRAM_CHAT_ID must contain the numeric chat ID, not a username')
    webhook = ORIGINAL_TELEGRAM('getWebhookInfo', {})
    if webhook.get('url'):
        raise RuntimeError('This bot has an active webhook. Polling cannot run simultaneously. Remove the old webhook or use a dedicated bot; no webhook was changed automatically.')
    print('Bot verified:', bot.get('username'), '| chat type:', chat.get('type'))
    state = pipeline.load_json(pipeline.STATE, {})
    print('Moderation state before processing:', state.get('status', 'idle'))
    pipeline.telegram = telegram
    try:
        pipeline.moderate()
    finally:
        pipeline.telegram = ORIGINAL_TELEGRAM
    state = pipeline.load_json(pipeline.STATE, {})
    print('Moderation state after processing:', state.get('status', 'idle'))

if __name__ == '__main__':
    main()
