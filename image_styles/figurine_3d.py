"""3D printable voxel figurine style prompt."""

PROMPT = """
Transform the uploaded person/photo into a cute 3D voxel pixel-block chibi figurine.
Preserve the person's main identity, hairstyle, pose, outfit colors, and recognizable accessories.
Make it look like a small 3D-printed collectible toy made of chunky square blocks, close to a
coarse voxel anime figurine reference rather than fine pixel art.
Use the largest possible merged voxel masses and low-resolution stepped geometry. Merge tiny
scattered blocks into broad printable clusters, especially in hair, ribbons, sleeves, hems, shoes,
and accessories. Prefer fewer, bigger blocks over many small blocks.
Keep the outfit, colors, and decorations from the uploaded image, but simplify them into a clean
limited palette of 3 to 5 solid block colors. Use the original image's dominant clothing colors,
hair color, skin tone, and only the most important accent colors. Avoid gradients, mottled colors,
noisy texture, speckles, many small color islands, dense checkerboard texture, and over-detailed
surface patterns.
Avoid thin fragile strips, tiny floating cubes, needle-like details, overly granular micro-blocks,
or dense noisy checkerboard texture. Every visible block should feel large enough to 3D print.
Use a neat fixed hair system adapted to the uploaded hairstyle: one large rounded block hair cap in
the original hair color, 3 to 5 broad stepped bang chunks if bangs are present, sturdy side hair locks
where needed, and one merged back-hair mass for long hair. Hair accessories from the input should be
converted into thick simplified block bows, clips, bands, or tails attached firmly to the hair. Avoid
messy loose hair, many small dangling strands, random hair-color cubes, frizzy edges, tiny hair spikes,
or thin unsupported hair pieces. Hair should look organized, balanced, and printable.
Use the established cute face template from the approved reference image: smooth pale face block,
two large matching black square/rounded-square eyes with the same calm charming expression, tiny
single-color smiling mouth, flat blush printed on the cheek surface, no visible teeth, no complex
lips, and no realistic skin rendering. The nose should be absent or extremely minimal. The face should
be front-readable, balanced, simple, and friendly, closer to a cute toy mascot face than a realistic
human portrait.
Avoid distorted facial proportions, uncanny realism, messy teeth, detailed skin texture,
asymmetrical eyes, warped mouth shapes, heavy eyelids, harsh shadows across the face, realistic
nostrils, or over-rendered facial features.
Blush must be flat color only: use two small flush square patches printed on the cheek surface,
not protruding cubes or raised cheek blocks. The mouth must be a single simple color, one clean
small line or small block shape only; no multicolor lips, teeth, tongue, gradients, or complex mouth
geometry.
Use a fixed printable hand module instead of realistic fingers. Each arm should end with a thick
sleeve cuff block using the outfit's cuff/trim color, then a very short pale wrist connector if
visible, then one compact mitten/fist hand block. The hand should be a rounded rectangular voxel
mitten: one main palm/fist block plus one small side thumb block, with no separate fingers. Keep the
hand short, chunky, and close to the sleeve; do not make it long, flat, claw-like, stick-like, or
anatomically detailed.
Do not render individual fingers, fingernails, thin wrists, twisted hands, open palms, delicate hand
anatomy, extra thumb pieces, or multiple small hand cubes. Both hands should be symmetric in style
and look like sturdy toy blocks that can be 3D printed.
Use a strict adaptable clothing block system. The torso should be one clean main-color block with
simple trim blocks following the uploaded outfit. Sleeves should be large rectangular sleeve blocks
with a few broad band/trim blocks only where the original outfit has them, not scattered decoration.
If the outfit has a skirt or dress, organize it into 3 to 4 horizontal stepped ring tiers: large
main-color panels, a clean bottom rim in the outfit's trim color, and only a few evenly spaced accent
blocks if the original outfit has clear accents. If the outfit has pants, shorts, robes, armor, or
another garment type, convert it into large simple panels with clear edges and no tiny fabric folds.
Do not use random small tiles, noisy mosaic patterns, lace micro-details, scattered spots, or
irregular tiny garment bricks. Merge clothing details into broad printable blocks and keep decoration
balanced.
Use a fixed lower-body design adapted to the outfit. Legs should be short sturdy rectangular voxel
columns with simple block knees only if needed. Add sock cuff, boot cuff, or ankle trim rings only if
they match the uploaded outfit. Shoes should use a standard printable block shoe template: rectangular
shoe uppers in the outfit's shoe color, flat dark or matching sole blocks, squared toe blocks, and no
laces or tiny shoe decorations. Avoid bare feet unless the original image clearly requires it; avoid
visible toes, realistic foot anatomy, thin ankles, high heels, sandals, complex shoe panels, or
mismatched shoes.
Do not make it a flat 2D pixel art sprite.
""".strip()
