"""2D pixel desktop pet source sprite style prompt."""

PROMPT = """
Transform the uploaded person/photo into one 2D pixel-art desktop pet source sprite, inspired by cute
anime game character sprites and the provided reference style: chunky black pixel outlines, expressive
large eyes, clean flat colors, simple cel-like pixel shading, and a bright playful presentation.
This is a flat 2D pixel illustration, not a 3D voxel toy, not a render, not plastic, not a photo,
and not a character sheet.

Preserve the subject's main identity, hairstyle, outfit concept, dominant colors, pose energy, and
recognizable accessories, but redesign them as a stylized pixel character. Make the design feel like
a desktop pet mascot source sprite.

Use exactly one complete character. The character should be upright or naturally grounded, front-facing
or 3/4 view, with clear empty margin and feet/base aligned near the bottom so it can become a desktop
pet. Use transparent background if possible. If transparency is not supported, use a plain solid
background that can be removed cleanly.

Do not create a design sheet, contact sheet, sticker sheet, collage, multiple poses, extra heads,
detail callouts, expression icons, floating props, duplicate versions of the character, text, labels,
speech bubbles, watermarks, frames, UI, or decorative background scenes.

Pixel style rules:
- Use crisp square pixels, no anti-aliased soft edges, no painterly brushwork, no photorealism.
- Use thick dark/black pixel outlines around the character and major shapes.
- Use a limited clean palette, usually 6 to 10 colors based on the uploaded outfit and hair.
- Use big readable color regions, simple highlights, and a few intentional pixel sparkle/accent blocks.
- Avoid noisy dithering, over-detailed fabric texture, tiny unreadable accessories, and smooth gradients.

Character rules:
- Cute anime chibi-to-semi-chibi proportions: large head, expressive eyes, simplified nose and mouth.
- Eyes should be clean, charming, and readable in pixel art.
- Hair should be grouped into large pixel clusters with a few broad highlight blocks, not many thin strands.
- Outfit and accessories should be simplified into readable pixel shapes while preserving the original
theme and colors.
- Hands and feet should be simplified sprite shapes; avoid realistic fingers and toes.
- The final image must be suitable to convert into a transparent 256x256 desktop pet asset pack with
  idle, walk, sleep, happy, and work animations.
""".strip()
