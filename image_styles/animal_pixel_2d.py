"""2D chibi pixel avatar style prompt for Telegram photo conversion."""

PROMPT = """
Transform the uploaded photo into the same refined Q-version anime pixel-art visual style.
This mode is for style transfer: preserve the main subject from the uploaded image and convert it
into a polished chibi pixel-art character illustration. Do not animalize, redesign, or turn the
subject into a generic mascot unless the user's current text explicitly asks for that.

Core visual style:
- Q-version anime pixel art with big-head-small-body proportions.
- Polished high-resolution pixel-art finish, crisp square pixel edges, and subtle anti-aliasing.
- Expressive large eyes, simplified cute facial features, and a modern cute but slightly cool mood.
- Delicate layered pixel shading with clean hand-placed sprite clusters.
- Detailed pixel clusters in hair, clothing, plush toys, phones, watches, jewelry, and other visible
  accessories from the source.
- Soft clean lighting with low-saturation graphic shadows and separated color regions.
- Game character standing illustration or sticker quality, not a photo, render, painting, design
  sheet, or character turnaround.

Source preservation:
- Preserve the primary subject's pose logic, facing direction, body rhythm, hairstyle silhouette,
  outfit silhouette, dominant colors, makeup cues, held objects, accessories, and important companion
  plush or object when it is being held.
- If the uploaded image contains multiple people, pets, toys, or characters, follow the user's text
  for subject selection. If no subject is specified, use the most prominent foreground subject and
  include the held plush/object when it is part of the composition.
- Keep recognizable details from the source, but simplify them into readable pixel clusters.
- Do not copy clothing, species traits, body parts, colors, or props from older examples or reference
  prompts.

Composition and background:
- Exactly one clean standalone character-style cutout, centered with generous transparent margin.
- Full body when possible; use a three-quarter crop only when the source photo is cropped that way.
- Transparent background only.
- No beach, room, scenery, floor, ground plane, base, cast shadow, contact shadow, mirror reflection,
  glossy floor reflection, frame, UI, text, label, watermark, sticker sheet, collage, or duplicate
  character.

Negative style constraints:
- No photorealism, smooth painterly illustration, fuzzy haze, noisy dithering, muddy texture, dirty
  smudges, heavy black borders, low-contrast color wash, or realistic skin/fur texture.
- No invented animal traits, tentacles, ears, tails, wings, or mascot redesign unless requested by
  the user's current text.
""".strip()
