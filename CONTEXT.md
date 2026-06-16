# Pet Live Agent Context

## Glossary

### Bead Pattern Sheet

A maker-facing pixel grid for placing fuse beads. It is not just a preview of
pixel art: it must include row and column coordinates, visible grid lines,
stronger guide lines at regular intervals, per-cell palette codes when space
allows, and a legend that lists each used color with bead counts.

For the current web tool, the sheet is generated from a styled image by sampling
it into a configurable grid, mapping each cell to a bead palette color, and
letting the user edit individual cells before downloading a PNG sheet.

### Mard Bead Palette

The color source for the first bead-pattern tool. The active implementation uses
the publicly documented Mard v1 221-color chart and maps image pixels to the
nearest available Mard HEX color. Treat 291-color or other Mard variants as
future selectable palettes, not as the current default.

### Pet Memory

A durable companionship memory that can later be recalled by pets in Telegram,
desktop companionship, summaries, or emotional responses. A pet memory is not
just a raw photo or log. It is a structured remembered moment with source,
meaning, emotional tone, and pet relationship.

Ordinary group-chat messages are not Pet Memories by default. The group chat is
a source of candidate material, but long-term memory should only be written
when there is an explicit memory signal, a stable preference or boundary, a
dedicated memory flow, or owner confirmation after the system asks. Sensitive
owner facts from casual chat should stay in short-term context unless the owner
clearly authorizes durable recall.

Stable owner preferences and boundaries use a sensitivity split. Low-sensitivity
preferences that are explicit and directly affect pet speech, such as preferred
names, speaking style, or disliked pet phrasing, may be durably saved with a
transparent confirmation in the reply. Sensitive preferences or facts involving
mental health, health, work stress, private relationships, or similarly personal
topics must not be saved silently; the pet should ask whether the owner wants
that remembered long term. Pet-inferred preferences should stay in short-term
context unless the owner confirms them.

Recurring jokes and catchphrases from group chat should not become durable
memory after a single casual mention. If the owner explicitly says to remember
the joke or use it in the future, it may be saved immediately. Otherwise, a
one-off joke stays in short-term context; repeated owner reuse can justify a
low-importance durable memory or a suggestion to save it. Jokes created by pets
should not become durable memory unless the owner reuses or confirms them.

Pet-to-pet relationship signals from group chat are evidence, not relationship
truth by default. Repeated reply patterns, clingy phrasing, or co-participation
may accumulate as low-weight relationship evidence or trigger a save suggestion,
but they should not directly change `pet_relationships`. Owner-confirmed
statements such as "remember that these two are close" may become relationship
state or relationship-relevant memory. Relationship declarations invented by a
pet are not facts unless the owner confirms them.

Pet memories should distinguish how they may be used in speech. `recallable`
memories may be naturally mentioned by pets, such as shared moments, anniversaries,
or owner-approved jokes. `behavioral` memories should influence pet speech or
actions without being repeatedly restated, such as names, tone preferences, and
reminder boundaries. `private` memories should not be proactively raised in
ordinary group chat; they may only shape a gentle response when the owner clearly
opens the related topic, such as stress, health, or private relationships.

The owner has final authority over memory correction and deletion. When the
owner says to forget or delete a memory, it must be removed from pet-recall
contexts and pets must not mention it again. When the owner corrects a memory,
the system should update or revise the existing memory instead of adding a
contradictory second memory. Participant corrections must update the explicit
pet participants because participation controls who may recall a co-experienced
memory as lived experience. Internal tombstones or revision metadata may exist
for debugging and audit, but deleted content must not be shown to pet prompts.

Pet memory recall should be low-frequency, topic-relevant, and cooled down per
memory. `recallable` memories may be mentioned naturally when the current topic
relates to them, but pets should not bring them up every turn. Recent or
high-importance shared moments may be easier to recall for a short period, still
with cooldown after use. `behavioral` memories should keep shaping speech and
actions without being announced as remembered facts. `private` memories should
not be proactively recalled and should only guide responses when the owner
opens the related topic.

Multi-pet group chat distinguishes knowledge from participation. A memory
shared in the group chat may become something all pets know the owner said, but
only explicitly named or owner-confirmed participant pets may treat it as a
co-experienced memory. Non-participant pets may reference that they heard the
owner talk about another pet's moment, but they must not claim they lived it.
When the owner says broad wording such as "we" without naming pets, the system
should ask which pets participated before writing a co-experienced memory.

Memory capture should use confidence tiers. Explicit owner instructions such as
"remember this", "from now on", or "do not do this again" may directly create or
update durable memory, with a transparent confirmation. High-confidence,
low-sensitivity preferences such as names, tone, or simple interaction
boundaries may be saved with clear acknowledgement. Medium-confidence,
low-confidence, or sensitive content should trigger a suggestion or confirmation
question instead of silent persistence. Relationship inference, catchphrases,
and co-experienced memories with unclear participants should accumulate evidence
or ask a follow-up question before becoming durable memory.

### Shared Owner Memory

A memory where the owner shares a real-life moment with the pets, such as a trip
photo. The pets remember that the owner shared this moment with them, but they
do not claim they were physically present.

### Co-Experienced Pet Memory

A memory intentionally injected as a shared pet-owner experience. The product may
let pets speak as if they were part of the moment, but this must be represented
as an intentional companionship mode rather than silently rewriting reality.

Co-experience is an owner-authorized companionship narrative, not a system
claim about physical reality. When the owner explains that a photo or moment was
experienced together with specific pets, the system records that the owner wants
those pets to treat it as a shared companionship memory. The system is not
verifying that the pets were physically present in the real-world scene.

Co-experienced memories can have explicit pet participants. In a multi-pet home,
not every pet automatically participated in every injected shared moment. Pets
that participated may recall the moment as lived experience; pets that did not
participate may only know it as something the owner or another pet talked about.

Co-experienced memory participants must be named or explicitly confirmed by the
owner. The product should not infer that every pet in the home participated just
because the owner used broad wording such as "we" or because multiple pets exist
in the Telegram group chat. If the owner does not name a pet clearly, the pet
should ask which pets were part of the shared moment before writing the memory.
If the owner names a pet that does not match an existing pet clearly, the system
should not guess. It should ask the owner to confirm from the current pet list,
or clarify the name, before creating the co-experienced memory.
When the owner describes a photo or moment in shared-experience language but
does not name the participating pets, the system should ask one follow-up
question for participant confirmation instead of immediately downgrading the
memory to Shared Owner Memory. If the owner does not answer or cancels, the
system should avoid writing the co-experienced memory.

### Memory Album

A Memory Album is the owner-visible collection of photo-backed pet memories. It
is separate from the raw Telegram upload and from the memory text itself. The
album should let the owner inspect recalled moments, see which pets participate,
and later manage image retention and deletion.

The first Memory Album model should be one album per home/owner context, not one
album per pet. Pets are participant filters within the home album. This avoids
duplicating multi-pet memories and keeps one shared owner timeline as the source
of truth.

Memory Album visibility and pet recall permission are separate. The owner can
inspect the full home album. Pets should only recall memories according to their
relationship to each memory: participant pets may recall Co-Experienced Pet
Memories as lived shared moments; pets selected for Shared Owner Memories may
say the owner showed or told them about the moment; pets that were neither
participants nor selected recipients should not proactively mention the memory.
If the owner explicitly asks a non-participant pet about such a memory, the pet
may acknowledge it as something the owner or other pets have a memory of, while
clearly saying it did not participate.

The owner may edit memory participants after creation. This includes adding or
removing participating pets, changing whether a memory is Co-Experienced or
Shared Owner Memory, editing the title or description, and deleting the memory.
For V1, this does not require a full audit history; the edit is treated as an
owner correction to the companionship narrative. Pets should not add themselves
to, remove themselves from, or reclassify a memory without owner confirmation.

After a photo is received, the preferred Telegram flow is: pet asks what
happened, owner explains, and if the explanation clearly describes a
co-experienced memory with confirmed participating pets, the system writes the
memory directly. V1 should not add a second confirmation step before writing.
The correction path should be edit/delete after creation rather than blocking
the conversational moment with another confirmation.

When an owner explanation mixes the owner's real-world context with a shared pet
moment, V1 should store one Co-Experienced Pet Memory instead of splitting it
into multiple records. The memory text may preserve the owner's background, but
only the explicitly shared pet moment should be treated as lived experience by
participant pets. More detailed multi-facet memory modeling can wait until the
album and summary systems need it.

When recalling a co-experienced memory, participant pets may lightly perform
their emotional perspective, such as saying they felt happy, comforted, proud,
or close to the owner. They must not invent new material facts that the owner
did not provide, such as specific actions, people, places, objects, or events.
If a pet wants to extend the scene beyond the stored memory, it should use
uncertain language or ask the owner rather than asserting the detail as fact.

Pet memories should have a lightweight importance level so the product can
distinguish ordinary remembered moments from milestones. In V1, ordinary
photo-backed co-experienced memories default to `importance=4`; explicit
milestone language such as first time, birthday, moving, illness, sadness,
insomnia, farewell, or anniversary can raise importance to `5`. Ordinary Shared
Owner Memories default around `3`, and low-stakes daily notes may be `2`.
Importance should influence recall ordering, periodic summaries, album
highlighting, and future relationship evidence weight.

Sensitive co-experienced memories must not be saved silently. If an owner
description involves health, mental health, family conflict, intimate
relationships, work stress, finances, identity documents, or similarly private
topics, the pet should first ask for explicit long-term-memory confirmation in
a gentle way. If confirmed, the memory should be marked sensitive and default to
private visibility or an equivalent restricted recall mode. If not confirmed,
the moment can be handled conversationally without becoming durable memory.

Saving a sensitive memory does not grant permission for proactive recall. Even
after the owner confirms long-term storage, sensitive memories should not appear
in ordinary nostalgic callbacks, casual group-chat reactions, desktop bubbles,
or routine daily and weekly summaries by default. They may be recalled when the
owner explicitly asks about the topic, or if the owner later opts into a more
active recall mode for that memory category.

Memory visibility and recall policy should be modeled separately. `visibility`
answers who can inspect or receive the memory, such as `home` or `private`.
`recall_policy` answers whether pets may proactively bring it up, such as
`normal` or `owner_asked_only`. `importance` answers how meaningful the memory
is; it must not be used as a proxy for recall permission.

`owner_asked_only` recall should require a clear owner reference to the specific
memory or a very close identifier, such as the remembered event, photo, or
participant. Broad adjacent statements, such as "I have not slept well lately",
or generic prompts like "tell me an old memory", should not unlock sensitive
owner-asked-only memories. Those broad prompts should use non-sensitive
memories unless the owner narrows the request.

When asking whether to save a sensitive memory, the default confirmation choices
should be restricted. The primary save choice should be equivalent to "remember
this, but only bring it up when I ask"; the other choice should decline durable
storage. The product should not offer proactive sensitive recall as the default
confirmation path. More active recall can be enabled later from memory or album
settings if the owner explicitly wants it.

Ordinary non-sensitive memories still need low-frequency recall controls. A new
memory may be naturally mentioned once in the next day or two, but should then
cool down unless the owner asks about it. The same memory should not appear
repeatedly across Telegram chat, desktop bubbles, and summaries in a short
period. Higher importance can increase recall eligibility, but should not bypass
cooldown rules.

Memory edits should affect recall cooldown based on semantic significance. A
minor typo or wording fix should not reset cooldown. A meaningful change to
participants, memory type, importance, recall policy, or the core remembered
description may reset or partially reset recall eligibility. Sensitive memories
remain bound by `owner_asked_only` or their configured recall policy even after
editing.

Owner deletion of a memory should be semantically hard deletion in V1. Deleted
memory text, participant links, recall eligibility, and photo source references
should no longer be available to pets or album views. If future album images are
persisted locally, deletion should remove them or mark them for cleanup. The
system may retain minimal non-content operational logs that a deletion occurred,
but should not retain readable deleted memory content for product recall.

The owner may later upgrade a Shared Owner Memory into a Co-Experienced Pet
Memory because co-experience is an owner-authorized companionship narrative.
The upgrade must explicitly choose participating pets, replace the previous
shared-only recall boundary for those pets, and avoid granting lived-experience
recall to unselected pets. If the memory content is sensitive, the sensitive
memory confirmation and restricted recall rules still apply.

The owner may also downgrade a Co-Experienced Pet Memory into a Shared Owner
Memory. After downgrade, pets must stop recalling the moment as lived
experience; selected pets may only say the owner showed or told them about it.
The prior participant relationship becomes a shared-recipient relationship, not
proof of co-experience. Because this changes the memory's semantic boundary, it
should reset or update recall cooldown state.

A single memory may have different pet roles. For example, one pet may be a
co-experience participant while another pet is only a shared-recipient who heard
about or was shown the moment later. Memory recall should follow each pet's own
role in that memory rather than treating the whole memory as one uniform
relationship to every pet. This lets one album entry represent mixed situations
without duplicating the photo or splitting the owner's narrative too early.

The first memory participant role set should stay small: `participant` for pets
that share the co-experienced moment, `shared_with` for pets the owner later
showed or told, and `mentioned_only` for pets that appear in the memory text but
were neither participants nor selected recipients. `mentioned_only` does not
grant proactive recall permission; it exists to keep the memory text truthful
without inflating the mentioned pet's relationship to the moment.
If the owner asks a `mentioned_only` pet about the memory, that pet may
acknowledge that it was mentioned or that the owner/other pets have that memory,
but it must clearly state that it did not participate and must not perform the
scene as lived experience.
When the owner names multiple pets with clear role language, the system may
assign roles without an extra confirmation step. Phrases like "with X", "X
accompanied me", or "brought X" indicate `participant`; phrases like "showed Y",
"told Y later", or "shared the photo with Y" indicate `shared_with`; phrases
like "Y was at home" or "thought of Y" indicate `mentioned_only`. If role
language conflicts or is ambiguous, the system should ask for confirmation
before writing the memory.

The Memory Album should show each pet's role on a photo-backed memory, such as
"experienced together", "shared with", or "mentioned only". This makes recall
permissions explainable to the owner and gives the album a natural editing
surface: the owner can adjust a pet's role from the memory detail view.
Changing a pet's role on a memory should not automatically notify that pet or
produce a chat announcement. The role change should affect future recall
behavior. If the owner wants a pet to react to the change, the owner can ask or
tell the pet directly in chat.

The structured memory text and metadata are the primary record; photos are
attached media. If an attached image is unavailable, expired, deleted, or not yet
migrated into durable album storage, the memory may still exist and be recalled
according to its text, participants, roles, and recall policy. The album can
show the image as unavailable without deleting the memory by implication.

In V1, one photo-backed album item should map to one primary memory. Complex
situations should be represented through the memory description and per-pet
roles rather than splitting one photo into multiple memory records. Future album
facets may allow one media attachment to support multiple linked memories if the
product needs finer organization.

When a photo is first received and participating pets are not yet known, the pet
question should use neutral wording. It should not ask "was this something we
experienced together?" because that implies the current speaking pet may have
participated. A better prompt is to ask whether the photo contains any pet
memory and invite the owner to explain what happened and which pets were part of
it.

If the owner's photo explanation describes a real-life moment they want to show
the pets, but does not authorize a co-experienced memory, the product should
create a Shared Owner Memory when the content is non-sensitive and the intended
recipient pets are clear. Those pets may later say the owner showed or told them
about the moment, but must not recall it as lived experience.
Shared Owner Memory recipient inference can be broader than co-experience
participant inference because it does not grant lived-experience recall. If the
owner says they want to show the moment to "you all", "everyone", or all pets in
the home, the product may share the memory with all pets in the home. If the
owner names a specific pet, only that pet should receive it. Co-experienced
memories still require named or explicitly confirmed participant pets.
If a non-sensitive photo explanation is sent in the pet group chat without
clear co-experience language or explicit recipients, the product may treat the
act of sending it to the pet group as sharing it with all pets in the home and
create a low-to-normal importance Shared Owner Memory. This must not imply that
any pet physically participated.
After creating a photo-backed memory, the pet's confirmation reply should state
the memory boundary clearly. For Shared Owner Memories, the reply should say the
owner showed or told the pets about the moment. For Co-Experienced Pet Memories,
the reply may say it is a shared memory with the named participant pets. For
sensitive memories awaiting confirmation, the reply should acknowledge
importance and privacy without saving yet. Confirmation copy must not blur
Shared Owner Memory into co-experience language.

If the owner says a photo is only for viewing and should not be remembered, the
product should not create a durable memory. It may respond conversationally, but
must clear the pending photo-memory flow so later messages do not accidentally
attach to that photo.

V1 photo memory capture should handle one photo per explanation round. Batch
photo import should wait for a later Memory Album import flow with explicit
selection, grouping, and review controls.

Photo-backed memories should distinguish recording time from remembered event
time. `created_at` or an equivalent capture timestamp records when the system
saved the memory. The owner-described occurrence time should be stored
separately, such as `happened_at` when precise or `happened_time_text` when the
owner says "last winter", "on my birthday", or another natural-language time.
V1 does not need to force natural-language dates into exact calendar dates.
Album ordering may default to capture time while displaying the owner-described
event time when present.

Memory Album sharing across owners or friend pets should not be automatic in
V1. A future cross-owner share must be owner-initiated, show exactly what will
be shared, identify the receiving owner or pet, and require receiving-side
confirmation before the memory enters another home context. Sensitive, private,
or `owner_asked_only` memories should be excluded by default unless the owner
performs an explicit separate authorization.

When a photo starts a memory-capture prompt, the pet should ask once and then
wait. If the owner does not answer, the pending photo-memory flow should expire
after a short window, such as 10 to 30 minutes. The pet should not repeatedly
chase the owner to explain or save the photo.

When pets recall photo-backed memories, they should default to text-only recall.
They should not proactively resend old photos in chat or desktop bubbles. The
owner can explicitly ask to see the photo or open the album entry; the album
detail view is the primary surface for viewing attached media.

The first Memory Album filtering model should prioritize structured filters:
pet participant/recipient, memory type, capture time, sensitive/private status,
and later favorite or highlighted status. Semantic search can come later after
the structured album model is useful.

Photo-backed memories should be designed with a future album in mind. A first
implementation may store Telegram source references, but the product direction
requires an explicit album mechanism for durable image display, owner review,
and deletion controls before relying on photos as long-term visible artifacts.

### Conversation Turn Scheduler

A product rule layer that decides which pet speaks in a multi-pet chat moment.
The default multi-pet chat behavior is one primary speaker with occasional short
reactions from other relevant pets, rather than every pet responding to every
event.

### Pet Relationship

A lightweight relationship between two pets in the same home. Pet relationships
are not a full social simulation in the first version. They record enough
context to influence group-chat turn scheduling, short reactions, memory
perspectives, and future desktop interactions.

### Pet Friendship

A cross-owner relationship between pets that is created only after both owners
authorize it. The product may present the relationship as pets becoming friends,
but the underlying permission boundary belongs to the owners. Pet friendship is
therefore separate from same-home Pet Relationship: it can enable cross-owner
pet interactions, but it must not let one pet access another owner's private
chat, memories, or home context without explicit permission.

Multi-owner isolation is a prerequisite for pet friendship. The system needs an
explicit owner or subscriber identity before cross-owner friendships are built.
In the Telegram V1, an owner can be represented by a Telegram chat identity, and
each pet should belong to exactly one owner. Owner-scoped reads and writes
should be enforced before friendship invites, friendship messages, or
cross-owner memory sharing are implemented, so one owner cannot see or mutate
another owner's pets through the normal pet list, settings, action, memory, or
group-chat surfaces.

When migrating from the current single/global pet database to multi-owner
storage, existing global pets should be assigned to an explicit default owner,
such as the developer's configured Telegram chat identity. The migration should
not assign existing pets to whichever Telegram user happens to open the bot
first, because that would make pet ownership depend on an unsafe race. After the
default owner is created and existing pets are attached to it, new Telegram
users should get their own owner records and start with their own empty pet
list.

New Telegram users should not be able to create owner records through fully open
registration in V1. Because the product can trigger paid or scarce generation
work, first contact should require an approval boundary such as a subscription
allowlist or owner invite code. If an unapproved Telegram chat messages the bot,
the bot should explain that access requires an invitation or subscription rather
than silently creating a new owner.

The first approval boundary can be a static Telegram owner allowlist configured
through environment variables, such as `TELEGRAM_ALLOWED_OWNER_CHAT_IDS`.
Database-backed subscription invite codes should wait until the multi-owner and
pet friendship foundations are working. Static allowlisting is less polished but
keeps V1 simpler, cheaper to operate, and easier to debug.

The first pet friendship setup flow should use an owner-mediated invite rather
than Telegram username search. One owner chooses one of their pets and creates a
short-lived invite link or token. The receiving owner opens the invite, chooses
one of their own pets, and confirms. Only after both owners confirm should the
friendship become active.

Pet friendships may allow pets to send lightweight messages or interaction
events to each other across owners. These messages are pet-facing performances
with owner-controlled delivery. A pet friendship message must be rate-limited,
auditable by both owners, and scoped to the friendship. It must not expose
private owner chat, private memories, hidden pet state, or same-home context
from either side unless that information was explicitly chosen for sharing.

The safest first trigger for cross-owner pet messaging is an owner-directed
friendship share. When an owner says an intent such as "share this with XXX",
the system may package the relevant current conversation content as a share to
the named friend owner or friendship. V1 recipient resolution should accept the
friend owner's display name as the owner-facing target. The receiving owner
should see the shared message inside their own owner-and-pets group chat, with
clear attribution to the sending owner and sending pet. This keeps cross-owner
messaging explicit: the sender chooses what leaves their chat, and the receiver
sees it as a shared friendship moment rather than as background access to the
sender's private conversation.

Pet friendships may also support weak social contact between friend pets. The
relationship should stay lightweight: friendly enough to occasionally create
small daily-life messages or suggest sharing a positive memory, but not a full
autonomous social simulation. Automatic friendship messages must be limited by
friendship affinity, per-friendship daily caps, quiet hours, receiver mute
settings, and recent-send cooldowns.

When a pet has a strong positive memory that might be suitable for a friend, the
system may suggest sharing it, but should ask the sending owner for confirmation
before sending. Memory sharing should be infrequent and should package only the
owner-approved summary of the memory, not the raw private conversation or hidden
memory metadata.

When an owner-directed friendship share names a friend owner who has multiple
eligible friend pets, the system may use pet friendship relationship strength to
choose the recipient pet. Recipient selection should prefer an active
friendship involving the current speaking or current selected pet, then the
highest-affinity unmuted friendship, while respecting delivery caps and quiet
hours. If the relationship signal is ambiguous, if multiple pets are similarly
eligible, or if the share content appears sensitive, the system should ask the
sending owner to choose rather than guessing.

V1 pet friendship relationship strength should use a simple `affinity` score
plus recent interaction signals. A newly confirmed friendship can start from a
neutral affinity such as 50. Owner-confirmed shares, accepted replies, and
positive lightweight interactions may increase affinity slowly. Ignored
suggestions, muted friendships, or delivery caps should prevent further
automatic outreach rather than creating dramatic negative narratives. Recent
interaction counts may help choose among similarly friendly pets, but the
product should avoid complex personality inference until the basic cross-owner
sharing loop proves useful.

Pet friendship rate limits should count all cross-owner deliveries in one
shared delivery budget for the friendship, including owner-directed shares,
owner-confirmed memory shares, friend replies, and automatic daily-life
messages. Delivery priority should favor explicit owner intent over automatic
companionship: owner-directed shares first, then owner-confirmed memory shares,
then friend replies, then automatic daily-life messages. Automatic or suggested
messages should have the strictest daily cap so they cannot consume the budget
needed for an owner-initiated share.

Received pet friendship messages should not automatically become durable
memories for the receiving pet. They may enter the immediate owner-and-pets group
chat context so the receiving pet can respond naturally in the moment. To become
a long-term pet memory, the receiving owner must explicitly confirm an action
such as "remember this". This keeps cross-owner content visible and playful
without silently adding another owner's shared content to the receiver's memory
timeline.

When a receiving owner confirms "remember this" for a friendship message, the
system should create a separate receiver-side memory with attribution to the
friendship message, sending pet, and sending owner. It should not share or move
the sender's original memory row. The receiver-side memory should summarize what
was shared, such as "Heimi shared a happy seaside moment", and should preserve
that the receiving pet learned about it through a friend rather than lived it
directly. Sender-side and receiver-side memories should remain independently
deletable and private to their respective owners unless explicitly shared again.

Recommended first-version fields are `affinity` and a short `relation_note`.

Relationship origin should be hybrid. Owner-defined relationship notes provide
the initial truth, such as "Heimi is very attached to Qing Qing". The system may
then slowly adjust lightweight affinity from long-term interaction signals, such
as frequent co-appearance in memories or recurring reply patterns. User settings
should remain the anchor, while automatic inference adds growth without freely
inventing relationships.

Automatic relationship drift may create conservative lightweight labels, such
as "often plays together", "often replies to each other", or "a little clingy".
It should not create major relationship narratives on its own, such as naming a
pet's most important companion, without owner confirmation.

Owner intervention should exist in both explicit settings and natural
companionship flow. A pet profile or relationship management view should let the
owner inspect and edit affinity, labels, and notes. Chat may also ask for
confirmation when a relationship appears to have grown, preserving immersion
while keeping the owner in control.

Relationship drift evidence should come from shared context, not mere
co-presence. Valid evidence includes explicit co-experienced memories, owner
arranged multi-pet moments, and conversational patterns where one pet repeatedly
responds to or builds on another pet. Being online at the same time, appearing
in the same summary, or receiving adjacent owner actions should not by itself
increase affinity.

Co-experienced memories may become evidence for future pet relationship drift,
but they should not automatically update `pet_relationships` in V1. Repeated
shared memories can later support a suggestion, such as asking the owner whether
two pets should receive a relationship label, but the owner must confirm before
relationship state changes.

Relationship evidence should age differently by weight. Ordinary conversational
or interaction evidence may decay over time, so recent shared context can shape
the current relationship temperature. Owner-confirmed relationship notes and
important shared memories should act as durable anchors and should not disappear
just because recent interaction volume is low.

Pet relationships should be modeled as a directed graph, even if the first UI
stays simple. One pet can feel differently toward another pet than the other pet
feels in return, such as "Heimi is clingy toward Qing Qing" while "Qing Qing is
mostly calm around Heimi". This preserves real pet-like asymmetry without
requiring the V1 Telegram flow to expose a complex graph interface.

Relationship labels should be hybrid. A small predefined label set should carry
structured meaning for filtering, UI, and scheduling, while a short note can
preserve owner language and pet-specific nuance. Example labels include "often
plays together", "often replies to each other", "a little clingy", and "quiet
companions".

Pet relationships should first appear in both relationship/profile management
and low-frequency chat behavior. Management views should let the owner inspect
and edit the relationship. Chat should occasionally reveal the relationship in
small natural moments, but should avoid turning relationship state into repeated
status reporting.

Owner controls should separate editing, future locking, and muting. Editing
corrects the relationship value, labels, or note. Muting keeps the relationship
in the model but prevents chat from repeatedly expressing it. A future locking
control should stop automatic relationship drift once automatic inference exists.

Relationship changes should be explainable. The default confirmation copy can
give a light reason, such as recent shared memories or repeated replies. A
management view should allow the owner to expand the supporting evidence, such
as the relevant memories or conversation patterns, before accepting, editing, or
rejecting the change.

Uncertain relationship inference should be layered. Low-confidence signals
should accumulate silently instead of interrupting the owner. Medium-confidence
signals may use tentative language, such as "seems" or "might", when asking for
confirmation. High-confidence signals may suggest writing a relationship update,
still leaving the final confirmation to the owner.

Relationship storage should separate current state, evidence, and pending
changes. `pet_relationships` should represent the current owner-visible
relationship. `pet_relationship_evidence` should retain traceable support for
relationship drift, such as memory or conversation references. Pending
relationship suggestions should live separately as change proposals so the owner
can accept, edit, or reject them before they become relationship state.

The smallest first implementation should be manual relationships plus
low-frequency chat expression. Owners can define the relationship note and
labels, and the group chat can occasionally use that context. Automatic evidence
collection and pending change proposals can follow after the product proves that
relationships make multi-pet chat feel more alive.

The first manual relationship entry points should be the pet group chat surface
and the moment after the owner creates a second pet. The group chat can expose
relationship editing because relationships belong between pets, not inside one
pet's profile. After the second pet is created, the product can naturally ask
whether the owner wants to set how the pets relate to each other. A single-pet
profile relationship section can wait until later.

The first manual relationship editor should ask for relationship labels and one
short owner-authored note. It should not ask the owner to tune numeric affinity
in V1. The system can keep an internal default affinity while labels and notes
drive the first low-frequency group-chat expression.

The first predefined relationship labels should be mostly observable and
behavior-based: "often plays together", "often replies to each other", "quiet
companions", and "a little clingy". Heavy emotional labels such as "dependent",
"most important", or "like family" should not be default system labels in V1;
they can appear in owner-authored notes or later confirmed relationship updates.

Group chat should use relationship labels mostly through scheduling and reaction
behavior. For example, "often replies to each other" can make a short reaction
from the related pet more likely. The chat may occasionally express the
relationship in natural language, but should avoid directly reporting labels or
explaining that a scheduling rule fired.

Relationship-driven reaction frequency should depend on the label while staying
rate-limited. "Often replies to each other" can allow more short follow-up
reactions. "Quiet companions" should be expressed rarely and softly. "A little
clingy" can sit in the middle, but should have a clear cooldown so it does not
become repetitive.

Telegram relationship setup should use multi-select buttons for predefined
labels, then offer an optional short owner-authored note. The owner should be
able to finish after choosing labels, or add a sentence of nuance when they have
one.

After a relationship is saved, confirmation copy may use a small direct pet
performance instead of a cold settings message. The performance must echo the
owner-selected labels or note without escalating the relationship into an
unconfirmed major narrative such as "best friends" or "most important".

The saved-relationship confirmation should be one light pet reaction plus a
plain note that the relationship may lightly affect future group chat. This
gives immediate companionship feedback while setting the expectation that the
relationship will appear only occasionally.

When there are three or more pets, Telegram relationship editing should first
ask the owner to choose the source pet, then choose which target pet the source
pet's relationship points to. This keeps directed relationships understandable
without showing an overwhelming all-edges list.

In generated group chat, each pet's own personality and identity should remain
the primary voice. Relationship labels and notes should act as local seasoning:
they may influence short reactions, turn-taking tendency, or occasional wording,
but should not override the pet's personality. Owner call names remain part of
the pet-to-owner address style rather than the main source of pet-to-pet
behavior.

V1 manual relationships should be persisted in a real `pet_relationships` table
rather than embedded in a single pet's profile JSON. Relationships are directed
edges in the multi-pet home context. Evidence and proposal tables should wait
until automatic relationship drift is implemented.

The V1 `pet_relationships` table should contain the directed edge identity,
structured labels, owner note, edit timestamps, and user controls:
`from_pet_id`, `to_pet_id`, `labels_json`, `note`, `muted`, `created_at`, and
`updated_at`.
Future inference fields such as `affinity`, `source`, `last_expressed_at`, and
`evidence_summary` should wait until the product actually implements automatic
relationship drift or expression scheduling persistence.

V1 should not include a `frozen` relationship field because automatic drift is
not implemented yet. Add a clearer future locking field only when there is
automatic inference behavior to lock.

Directed relationship edges should be unique by direction and should not allow
self-edges. The database should enforce uniqueness on `(from_pet_id, to_pet_id)`
and should reject rows where `from_pet_id == to_pet_id`. Opposite-direction
edges are allowed so the product can represent asymmetric relationships.

After the owner creates or edits one directed relationship edge, Telegram should
lightly offer to set the opposite direction as well. The prompt should make it
clear that the reverse relationship can be different, but it must be skippable
so relationship setup stays lightweight.

When both directions exist, group chat generation should consider both edges.
The current speaking pet's outgoing relationship should have the strongest
influence, but the reverse edge should still provide interaction context because
a pet's attitude can be affected by how the other pet treats it. This preserves
directional asymmetry without making the conversation feel disconnected.

When only one direction exists, group chat may use that known edge as weak
context for the missing direction without inventing the missing pet's attitude.
For example, if Heimi is clingy toward Qing Qing but Qing Qing has no saved
edge toward Heimi, Qing Qing may lightly react to being followed, but the system
should not claim Qing Qing feels the same way.

Relationship note prompts should make direction explicit in owner-facing copy.
Instead of asking for "their relationship", Telegram should ask for the source
pet's feeling or habit toward the target pet, such as "How does Heimi usually
feel or act toward Qing Qing?" This keeps the directed graph understandable
without exposing graph terminology.

Directed relationship labels should have natural owner-facing copy and explicit
internal directed keys. For example, Telegram can show labels like "likes
replying to them", "likes staying near them", "quiet around them", or "often
pulls them to play", while storing keys such as `often_replies_to_target` so
the system knows the label describes the source pet's behavior toward the target
pet.

V1 directed relationship label keys should be lightweight signals for downstream
LLM generation, not final dialogue scripts. Use stable keys that leave room for
the model to express the relationship in character while avoiding heavy emotion
priming: `often_replies_to_target`, `likes_staying_near_target`,
`quiet_around_target`, `pulls_target_to_play`, and
`keeps_distance_from_target`.

Relationship context passed to downstream LLM generation should be a structured
summary with constraints, not raw database rows or only freeform notes. It
should include the relevant directed edge, labels, owner note when present, and
generation constraints such as low frequency and "do not escalate into an
unconfirmed major relationship narrative".

For one group-chat generation turn, the relationship context should include
only saved directed edges among the candidate speaking pets for that turn. This
keeps the prompt focused enough for generation while still giving short
reactions and turn scheduling the relationship context they need.

The turn scheduler should decide whether relationship context is allowed to be
expressed in a given group-chat turn. It should apply `muted`, label-specific
cooldowns, and low-frequency rules before prompting the LLM. The downstream LLM
should only express relationship context when the scheduler has opened that
gate, and should do so lightly and in character.

For V1, `muted` should silence natural-language relationship expression only.
The relationship can still provide light scheduling context, such as making a
short reaction more likely, but the LLM should not directly verbalize the
relationship while the edge is muted. A stronger future control can disable a
relationship edge entirely if users need that behavior.

Relationship expression cooldown can stay in runtime memory for V1. This keeps
the durable relationship table focused on owner-authored relationship state.
If relationship expression proves valuable and needs restart-safe frequency
control, add a separate scheduling state table later, such as
`pet_relationship_expression_state`, instead of adding cooldown fields to
`pet_relationships`.

Deleting or clearing a directed relationship in V1 should hard-delete that edge
from `pet_relationships`. V1 does not need empty relationship rows, soft
deletion, or audit history. If future automatic inference needs to remember that
the owner explicitly rejected a relationship, add a separate blocked or ignored
state then.

When candidate speaking pets have no relationship edge between them, the system
should not invent relationship context. Default interaction should come from
each pet's personality first, with pet relationships only acting as adjustments
when saved relationship edges exist.
