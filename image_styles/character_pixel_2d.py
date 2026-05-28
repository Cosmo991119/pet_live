"""2D chibi pixel character style prompt."""

PROMPT = """
Transform the uploaded photo into the same refined Q-version anime pixel-art visual style.
Preserve the main subject from the uploaded image and convert only the rendering style: polished
chibi pixel-art character illustration, game character standing illustration, or clean sticker asset.

Core visual style:
- Q-version anime pixel art with big-head-small-body proportions.
- Polished high-resolution pixel-art finish, crisp square pixel edges, and subtle anti-aliasing.
- Expressive large eyes, simplified cute facial features, and a modern cute but slightly cool mood.
- Delicate layered pixel shading with clean hand-placed sprite clusters.
- Detailed pixel clusters in hair, clothing, held objects, and visible accessories.
- Soft clean lighting with low-saturation graphic shadows and separated color regions.

Source preservation:
- Preserve the subject's pose logic, facing direction, body rhythm, hairstyle silhouette, outfit
  silhouette, dominant colors, makeup cues, held objects, and accessories.
- Keep recognizable details from the source, but simplify them into readable pixel clusters.
- Do not copy clothing, species traits, body parts, colors, or props from older examples or reference
  prompts.

Composition and background:
- Exactly one clean standalone character-style cutout, centered with generous transparent margin.
- Full body when possible; use a three-quarter crop only when the source photo is cropped that way.
- Transparent background only.
- No floor, ground plane, base, cast shadow, contact shadow, mirror reflection, glossy floor
  reflection, frame, UI, text, label, watermark, background scene, sticker sheet, collage, or
  duplicate character.

Negative style constraints:
- No photorealism, render, smooth painterly illustration, fuzzy haze, noisy dithering, muddy texture,
  dirty smudges, heavy black borders, low-contrast color wash, or realistic skin/fur texture.
""".strip()
