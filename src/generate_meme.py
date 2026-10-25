"""Gemini text generation with picture-template rendering."""
import json
import os
import requests
from src.config import GEMINI_API_KEY, PUBLIC_BASE_URL
from src.trends import collect_signals
from src.visual_memes import concept, render

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

def ask_gemini(signals, rejected):
    if not GEMINI_API_KEY:
        raise RuntimeError('Missing GEMINI_API_KEY secret')
    model = os.getenv('GEMINI_MODEL', '').strip().removeprefix('models/')
    if model not in available_models():
        raise RuntimeError('Configured Gemini model unavailable; no automatic paid-model switch attempted')
    def request(prompt):
        payload = api_request('POST', 'models/' + model + ':generateContent', json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.9, 'responseMimeType': 'application/json'}})
        candidates = payload.get('candidates', [])
        if not candidates:
            raise RuntimeError('Gemini returned no concept')
        text = ''.join(p.get('text', '') for p in candidates[0].get('content', {}).get('parts', []) if not p.get('thought'))
        try:
            idea = json.loads(text)
        except ValueError:
            raise RuntimeError('Gemini returned invalid JSON') from None
        if not isinstance(idea, dict):
            raise RuntimeError('Gemini concept must be an object')
        return idea
    return concept(signals, rejected, request)

def render_meme(idea, output_path):
    render(idea, output_path)

if __name__ == '__main__':
    from src.pipeline import generate
    generate()
