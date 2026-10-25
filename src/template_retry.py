"""Bounded retries for templates that cannot fit a full-width layout."""
import json
from src.full_width_layout import layout_plan

MAX_TEMPLATE_ATTEMPTS = 3
TALL_LAYOUT_ERROR = 'Template is too tall for full-width rendering without cropping; choose a wider template or add in-image caption boxes'

def select_fitting_concept(build, load_picture, rejected):
    history = list(rejected)
    excluded = set()
    for attempt in range(1, MAX_TEMPLATE_ATTEMPTS + 1):
        idea = build(history, sorted(excluded))
        template_id = str(idea['template']['id'])
        if template_id in excluded:
            print('Template selection repeated an excluded ID; attempt', attempt)
            continue
        with load_picture(idea['template']) as photo:
            try:
                layout_plan(photo.size, len(idea['panel_text']), bool(idea['template'].get('boxes')))
            except RuntimeError as error:
                if str(error) != TALL_LAYOUT_ERROR:
                    raise
                excluded.add(template_id)
                history.append({'template_id': template_id, 'topic': idea.get('topic', ''), 'reason': 'Too tall for uncropped full-width layout'})
                print('Skipping tall template', template_id, '; selection attempt', attempt, 'of', MAX_TEMPLATE_ATTEMPTS)
                continue
        return idea
    raise RuntimeError('No fitting template after three selections; no candidate was delivered or published. Retry generation later.')

def concept(signals, rejected, request):
    from src.visual_memes import concept as original_concept, picture
    def build(history, excluded):
        def constrained_request(prompt):
            if excluded:
                prompt += '\nLAYOUT CONSTRAINT: These template IDs were too tall and MUST NOT be selected again: ' + json.dumps(excluded) + '. Choose a different supplied template and rewrite its panel captions to fit.'
            return request(prompt)
        return original_concept(signals, history, constrained_request)
    return select_fitting_concept(build, picture, rejected)
