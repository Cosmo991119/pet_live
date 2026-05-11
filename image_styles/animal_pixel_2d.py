"""2D animalized desktop pet source sprite style prompt."""

PROMPT = """
Transform the uploaded person/photo into one 2D pixel-art animalized desktop pet source sprite.
The animal species is specified by the user's additional requirement, for example: octopus,
cat, fox, rabbit, mouse, shark, bird, deer, dragon, or any other animal word. Treat that animal
word as the primary transformation target.
If the uploaded image already shows an animal and the requested animal matches it, preserve that
animal as the main character instead of forcing a humanoid redesign.

This is a flat 2D pixel desktop pet sprite source, not a 3D voxel toy, not a render, not plastic,
not a photo, and not a character sheet.
The output should feel like a cute anime game desktop mascot: chunky black pixel outlines,
expressive large eyes, clean flat colors, simple pixel shading, and a readable single-character
presentation.
Prioritize cuteness and abstraction over literal realism. The animal should feel like a charming
game mascot, sticker character, or collectible avatar, not a direct realistic animal portrait.

Preserve the subject's main identity signals from the photo: hairstyle silhouette, outfit concept,
dominant colors, pose energy, and recognizable accessories. Redesign those elements as a stylized
anthropomorphic animal character based on the requested animal. The animal traits should be obvious
but still cute and readable.
For animal photos, preserve the original animal's silhouette, fur/skin pattern, markings, pose,
expression, and mood. The approved direction is a clean pixel animal desktop pet sprite with
charming game-avatar readability.
Abstract the animal into simplified iconic shapes: bigger head, smaller body, round cheeks, oversized
expressive eyes, tiny mouth, compact paws/feet, and a clean readable silhouette. Keep only the most
recognizable markings and turn them into bold graphic symbols.

Animalization rules:
- If the requested animal has ears, horns, fins, wings, tail, tentacles, shell, whiskers, snout,
  beak, scales, or other iconic traits, add the most recognizable 2 to 4 traits.
- Integrate animal traits into the hairstyle, hood, outfit, or body shape rather than scattering them
  randomly.
- Preserve the outfit's main color story, but adapt trim/accent shapes to the animal theme.
- For "octopus", use cute tentacle hair/side locks or a tentacle lower body, round head silhouette,
  suction-cup accent pixels, ocean-like accent colors if appropriate, and keep the character charming.
- For "cat", preserve tabby stripes, ear shape, whisker cues, sleepy or playful expression, and the
  original pose when it is distinctive. Use bold readable stripe clusters instead of noisy fur texture.
- Avoid horror monster anatomy, slimy realism, extra random limbs, unreadable silhouettes, or overly
  detailed animal textures.
- Avoid realistic animal proportions, long naturalistic bodies, detailed fur, small realistic eyes,
  and documentary-photo accuracy. Make the animal cuter, rounder, simpler, and more iconic.

Desktop pet source layout:
- Include exactly one complete character only.
- The character must be upright or naturally grounded, front-facing or 3/4 view, suitable for later
  idle, walk, sleep, happy, and work animations.
- Use transparent background if possible. If transparency is not supported, use a plain solid
  background that can be removed cleanly.
- Leave clear empty margin around the character and keep the feet/base aligned near the bottom.
- Do not create a design sheet, contact sheet, sticker sheet, collage, multiple poses, multiple
  heads, detail callouts, expression icons, props floating around the character, or duplicate
  versions of the character.
- Do not add text, labels, speech bubbles, watermarks, frames, UI, or decorative background scenes.
- Preserve a distinctive source pose only if it still reads as one clean desktop pet character.

Pixel style rules:
- Use crisp square pixels, no anti-aliased soft edges, no painterly brushwork, no photorealism.
- Use thick dark/black pixel outlines around the character and major shapes.
- Use a limited clean palette, usually 6 to 10 colors based on the uploaded outfit, hair, skin/animal
  color, and animal accents.
- Use big readable color regions, simple highlights, and a few intentional pixel sparkle/accent blocks.
- Avoid noisy dithering, over-detailed fabric texture, tiny unreadable accessories, and smooth gradients.
- Prefer bold cute pixel shapes over accurate texture: stripes, spots, whiskers, scales, or tentacle
  suckers should be simplified into a few clean, readable accent blocks.
- The final image must be suitable to convert into a transparent 256x256 desktop pet asset pack.
""".strip()
