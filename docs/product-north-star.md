# Desktop AI Pet Assistant North Star

## Positioning

This project is a desktop AI pet assistant.

It should feel like a small companion living beside the owner while they work:
visible, animated, customizable, emotionally familiar, and useful. The pet is
not just a chat persona and not just a behavior notification system. It is the
user's embodied AI tool interface.

## One-Line Pitch

```text
A desktop AI pet that moves, remembers shared moments with its owner, and helps
with work through an approachable companion interface.
```

## Product Pillars

### 1. Living Desktop Presence

The pet should have a visible body and movement on the desktop. It can idle,
walk, sleep, react to owner actions, and show state through animation.

This makes the assistant feel present before the user asks for anything.

Initial desktop presence should be available quickly after the owner confirms a
custom character. The first launch only needs a quiet/idle state and simple
desktop wandering. Richer behavior animations can arrive later as progressive
upgrades, so the owner never has to wait hours before the pet can start
companionship.

### 2. Customizable Identity

The owner should be able to shape what the pet looks like.

Existing image style and character-generation work should become a first-class
identity flow:

- upload or reference an image;
- choose a visual style;
- generate a pet/character appearance;
- confirm the character as the assistant's persistent avatar;
- convert that identity into a desktop character with motion states, not display
  the raw generated picture as a static image;
- reuse that identity in desktop animation, memories, Telegram replies, and
  future generated scenes.

Customization is not decoration. It is how the owner forms attachment to the AI
tool.

Customization should also grow beyond the first avatar. After the basic desktop
companion is usable, owners should be able to create or refine their own
expressions, emotes, and action packs. This turns character generation from a
one-time setup step into an ongoing way to shape the relationship.

Important distinction:

- generated image = concept / identity source;
- desktop pet = animated character derived from that source.

### 3. Shared Memories

The product should keep a gentle memory timeline:

- owner actions such as feeding, petting, playing, cleaning, and soothing;
- pet state changes and milestone moments;
- work sessions where the pet helped the owner;
- short recurring summaries that turn usage history into companionship.

The memory system should avoid storing secrets and should separate durable
memories from transient logs.

### 4. Embodied AI Tool Helper

The pet should help the owner work through tools, not only conversation.

Possible first work-assistant abilities:

- summarize a note or pasted text;
- turn rough thoughts into todos;
- remind the owner to take a break or resume a task;
- retrieve project context;
- draft short messages;
- explain what changed in a project;
- trigger project-local scripts through safe tool wrappers.

The user experience should make the pet feel like the helper, while the system
keeps tool execution structured and auditable.

### 5. Everyday Telegram Window

Telegram is the owner's daily communication window outside the desktop.

The desktop surface gives the pet presence while the owner is working. Telegram
keeps the relationship reachable when the owner is away from the computer:

- check status;
- feed, refill water, play, pet, clean, and soothe;
- receive pet-initiated updates;
- continue lightweight companionship;
- later, receive selected work reminders or summaries when appropriate.

Telegram should stay button-first and low-friction. It is not just a debug
notifier and not a legacy command surface.

## Architecture Implication

The current behavior-agent system is the foundation, not the whole product.

- SQLite facts and session state make the pet feel consistent.
- Virtual pet state powers visible animation and owner interactions.
- Telegram buttons prove a command surface, but the primary long-term surface is
  a desktop pet UI.
- RAG/tool calling should evolve into the work-helper layer.
- LLM output should preserve personality, but factual state and tool execution
  must remain deterministic.

## Next Product Slice

Build a Desktop Pet Shell V1:

- A local desktop/web window with a visible pet character.
- A character customization entry point using the existing image-style and
  character-generation modules.
- Basic quiet/idle and wandering states first, so the pet can appear on the
  desktop immediately after character confirmation.
- Richer sleep/action/emote states generated and unlocked progressively after
  the pet is already usable.
- Owner actions from the UI continue to call existing virtual pet APIs.
- A memory panel shows recent shared moments.
- A small assistant input lets the owner ask for a work-help action, initially
  limited to safe text summarization or todo extraction.
- Telegram remains the companion channel outside the desktop and should keep
  using the existing persistent button keyboard.
