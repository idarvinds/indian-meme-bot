# Picture-template library

The generator fetches up to 25 one/two-caption formats from Imgflip's free popularity feed on each candidate request, then asks Gemini for short panel text. Popularity is NOT proof of current Indian virality. No Imgflip account or paid image-generation API is used.

## Custom Indian templates

Upload permitted blank JPEG/PNG images under templates/ and add entries to catalog.json:

```json
[{
  "id": "my-reaction",
  "name": "My permitted two-panel reaction",
  "path": "templates/my-reaction.jpg",
  "panels": 2,
  "boxes": [[0.52, 0.04, 0.46, 0.42], [0.52, 0.54, 0.46, 0.42]],
  "source": "Record permission or license here"
}]
```

Boxes are normalized x/y/width/height within the image. They must match its actual blank regions. If boxes are omitted, captions go in white bands above and below the image, preserving the picture. Local entries override matching external IDs.

## Limitations and safety

- No claim that all popular templates are new or India-specific.
- Public image availability is not a reuse license. Review template rights before publication, and prefer your own or permitted assets.
- Source URL must match a supplied headline published within 24 hours. This validates provenance, not the truth of every joke.
- Digit-containing image text and captions are blocked to avoid unsupported numerical price/score claims.
- No Google Drive sync is installed. Connected chat authorization does not automatically grant GitHub Actions Drive access.
- Old pending memes are not reset. Reject an existing candidate and process moderation to generate a picture-based replacement.
- Additional Change Template/Rewrite Joke controls are not installed in this version. Existing Approve/Reject stays unchanged.
