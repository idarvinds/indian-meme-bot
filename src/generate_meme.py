"""Gemini text generation with picture templates and source-ID grounding."""
import json
import os
import requests
from src.config import GEMINI_API_KEY, PUBLIC_BASE_URL
from src.trends import collect_signals
from src.visual_memes import concept, render, recent_items

API = 'https://generativelanguage.googleapis.com/v1beta'

def api_request(method, resource, **kwargs):
    try:
        response = requests.request(method, API + '/' + resource, headers={'x-goog-api-key': GEMINI_API_KEY}, timeout=60, **kwargs)
    except requests.RequestException:
        raise RuntimeError('Gemini network request failed; retry later') from None
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError('Gemini returned a non-JSON response') from None
    if not response.ok:
        message = str(payload.get('error', {}).get('message', 'Unknown API error'))
        if GEMINI_API_KEY:
            message = message.replace(GEMINI_API_KEY, '[REDACTED]')
        raise RuntimeError('Gemini HTTP ' + str(response.status_code) + ': ' + message)
    return payload

def available_models():
    models, token = [], None
    while True:
        params = {'pageSize': 1000}
        if token:
            params['pageToken'] = token
        page = api_request('GET', 'models', params=params)
        models.extend(m['name'].removeprefix('models/') for m in page.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', []))
        token = page.get('nextPageToken')
        if not token:
            return models

def attach_source(idea, sources):
    if not isinstance(idea, dict):
        raise ValueError('Concept must be an object')
    source_id = idea.get('source_id')
    if not isinstance(source_id, str) or source_id.strip() not in sources:
        raise ValueError('Choose a supplied source_id')
    source_id = source_id.strip()
    idea = dict(idea)
    idea['source_id'] = source_id
    idea['source_url'] = sources[source_id]
    return idea

def ask_gemini(signals, rejected):
    if not GEMINI_API_KEY:
        raise RuntimeError('Missing GEMINI_API_KEY secret')
    model = os.getenv('GEMINI_MODEL', '').strip().removeprefix('models/')
    if model not in available_models():
        raise RuntimeError('Configured Gemini model unavailable; no automatic paid-model switch attempted')
    news = recent_items(signals)
    sources = {'news_' + str(i + 1): item['link'] for i, item in enumerate(news)}
    choices = [{'source_id': 'news_' + str(i + 1), 'title': item['title'], 'published': item['published']} for i, item in enumerate(news)]
    def request(prompt):
        prompt = prompt.replace('source_url', 'source_id').replace('its exact source URL', 'its exact source ID')
        for source_id, url in sorted(sources.items(), key=lambda pair: len(pair[1]), reverse=True):
            prompt = prompt.replace(url, source_id)
        prompt += '\nSOURCE SELECTION: Return source_id from this exact list. Never write or invent a URL. The application attaches the original URL. ' + json.dumps(choices, ensure_ascii=False)
        for attempt in range(2):
            payload = api_request('POST', 'models/' + model + ':generateContent', json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.8, 'responseMimeType': 'application/json'}})
            candidates = payload.get('candidates', [])
            if not candidates:
                raise RuntimeError('Gemini returned no concept')
            text = ''.join(p.get('text', '') for p in candidates[0].get('content', {}).get('parts', []) if not p.get('thought'))
            try:
                return attach_source(json.loads(text), sources)
            except ValueError:
                if attempt == 1:
                    raise RuntimeError('Gemini returned invalid JSON or source_id twice; no ungrounded meme was sent') from None
                print('Retrying invalid JSON/source selection once; maximum two generation calls per candidate')
                prompt += '\nYour previous response had invalid JSON or source_id. Return a JSON object with one exact source_id from the supplied list and all required meme fields.'
        raise RuntimeError('Source selection failed')
    return concept(signals, rejected, request)

def render_meme(idea, output_path):
    render(idea, output_path)

if __name__ == '__main__':
    from src.pipeline import generate
    generate()
