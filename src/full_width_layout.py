"""Full-width layouts without cropping, stretching, or side gutters."""
from PIL import Image, ImageDraw

def layout_plan(size, panel_count, has_boxes=False):
    width, height = size
    if width <= 0 or height <= 0 or panel_count not in (1, 2):
        raise RuntimeError('Invalid template dimensions or panel count')
    image_height = max(1, round(height * 1080 / width))
    if has_boxes:
        canvas_height = max(566, image_height)
        band = 0
    else:
        band = max(100, min(160, (1350 - image_height) // panel_count))
        canvas_height = max(566, image_height + panel_count * band)
    if canvas_height > 1350:
        raise RuntimeError('Template is too tall for full-width rendering without cropping; choose a wider template or add in-image caption boxes')
    return image_height, canvas_height, band

def render(idea, output_path):
    from src.visual_memes import picture, text_box
    template = idea.get('template')
    if not template:
        raise RuntimeError('Picture template metadata is required')
    photo = picture(template)
    panels = idea['panel_text']
    boxes = template.get('boxes')
    image_height, canvas_height, band = layout_plan(photo.size, len(panels), bool(boxes))
    photo = photo.resize((1080, image_height), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (1080, canvas_height), 'white')
    if boxes:
        if len(boxes) != len(panels):
            raise RuntimeError('Template boxes must match panel captions')
        top = (canvas_height - image_height) // 2
        canvas.paste(photo, (0, top))
        draw = ImageDraw.Draw(canvas)
        for text, box in zip(panels, boxes):
            x, y, w, h = box
            if min(box) < 0 or x + w > 1 or y + h > 1 or w <= 0 or h <= 0:
                raise RuntimeError('Invalid normalized caption coordinates')
            text_box(draw, text, (int(x * 1080), top + int(y * image_height), max(1, int(w * 1080)), max(1, int(h * image_height))))
    else:
        top = band + (canvas_height - image_height - len(panels) * band) // 2
        canvas.paste(photo, (0, top))
        draw = ImageDraw.Draw(canvas)
        text_box(draw, panels[0], (0, top - band, 1080, band))
        if len(panels) == 2:
            text_box(draw, panels[1], (0, top + image_height, 1080, band))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, 'JPEG', quality=92)
