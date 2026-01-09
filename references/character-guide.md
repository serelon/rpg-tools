# Creating Characters

Create character JSON files for the incremental character loading system. Files go in `characters/` folder and are loaded on-demand during sessions.

## JSON Schema

```json
{
  "id": "character-id",
  "name": "Display Name",

  "faction": "faction-name",
  "subfaction": null,
  "tags": ["protagonist", "psychic", "etc"],

  "minimal": {
    "role": "Their role/position",
    "essence": "35 words max. Core personality, key background, distinguishing trait.",
    "voice": "One quote that captures their speaking style."
  },

  "full": {
    "appearance": "Physical details that matter for writing",
    "personality": "How they act, contradictions, flaws, triggers",
    "background": "Only what's relevant - evocative > exhaustive",
    "motivations": "What they want and why",
    "voice_samples": [
      {"context": "situation/mood", "line": "dialogue"},
      {"context": "different situation", "line": "different dialogue"}
    ]
  },

  "sections": {
    "relationships": {},
    "powers": {},
    "combat": {},
    "timeline": [],
    "secrets": ""
  }
}
```

## Workflow

### Step 1: Gather Source Material

Collect:
- Session exports or transcripts where this character appears
- Existing character profiles (markdown)
- Notes or descriptions

### Step 2: Extract Minimal Profile

Create the minimal profile first:
- **id**: lowercase, hyphenated (e.g., "juno", "captain-mitchell")
- **name**: Display name
- **faction/subfaction**: Group they belong to (links to faction tracker - see [Creating Factions](faction-guide.md))
- **tags**: Relevant labels (protagonist, antagonist, psychic, military, etc.)
- **role**: Their position or function (max 10 words)
- **essence**: 35 words MAX. Distill to core personality + key background + distinguishing trait
- **voice**: One quote that reveals character, not just exposition

### Step 3: Decide on Full Profile

Full profiles are for:
- Protagonists and major characters
- Characters who need voice guidance for dialogue
- Characters whose capabilities matter mechanically

Minor NPCs only need minimal profiles.

### Step 4: Extract Full Profile (if needed)

**Voice Samples are CRITICAL** - This is the most important part.

Think about this character specifically:
- When are they at their most characteristic?
- When are they at their least characteristic?
- What contexts bring out different sides of them?

Create diverse voice samples:
- Different emotional registers (not all the same mood)
- Different situations (professional, intimate, stressed, relaxed)
- Include internal monologue if character has introspective scenes
- Each sample should be distinct, not variations of the same phrase

Other full profile fields - adapt as needed:
- **appearance**: Physical details relevant for writing
- **personality**: How they act, not just beliefs. Include contradictions.
- **background**: Only what's story-relevant. Avoid exhaustive life history.
- **motivations**: Short-term and long-term wants

### Step 5: Add Relevant Sections

Choose sections based on character type:

**Powers/Abilities** (for characters with special abilities):
- Description: What can they do?
- Mechanics: How does it work? Triggers? Limits? Costs?
- Applies to: magic, psychic, cybernetics, augments, supernatural, etc.

**Combat** (only for characters who fight):
- Weapons, tactics, fighting style
- Weaknesses, limitations
- Skip entirely for non-combatants

**Relationships**:
- Key connections with brief context
- Format: `"character_id": "relationship description"`

**Timeline** (if history matters):
- Key events that shaped them
- Format: `[{"era": "when", "event": "what happened"}]`

**Secrets**:
- What others don't know about them

**Custom sections**:
- Add whatever's relevant to THIS character

### Step 6: Save File

Save to `characters/{id}.json`

## Anti-Patterns - AVOID These

- Generic voice samples ("I will protect my friends") - be specific
- Exhaustive backstory - evocative > exhaustive
- All voice samples in same emotional register - show range
- Duplicating information between essence and full profile
- Including combat section for non-combatants
- Describing powers without mechanics
- More than 35 words in essence

## Example: Minimal-Only Character

```json
{
  "id": "dock-worker-marco",
  "name": "Marco",
  "faction": "port-authority",
  "subfaction": null,
  "tags": ["npc", "informant"],
  "minimal": {
    "role": "Dock worker, occasional informant",
    "essence": "Weathered hands, careful eyes. Knows which ships carry what. Trades information for favors, never credits. Has three kids to feed.",
    "voice": "I didn't see nothing. But if I had, it'd cost you."
  }
}
```

## Faction Integration

Characters can be linked to factions for organizational tracking:

- **faction**: The faction ID this character belongs to
- **subfaction**: Optional subfaction within the parent faction

When a character belongs to a faction, ensure bidirectional sync:
1. Set the `faction` field in the character JSON
2. Add the character ID to the faction's `members.named` array

See [Creating Factions](faction-guide.md) for faction schema and the bidirectional sync pattern.

## Example: Full Character

```json
{
  "id": "juno",
  "name": "Juno",
  "faction": "still-here-crew",
  "subfaction": null,
  "tags": ["protagonist", "captain", "psychic"],
  "minimal": {
    "role": "Captain of the Still Here",
    "essence": "Salvager, smuggler, survivor. Watched parents killed by Empire as a child. Built a crew, a life, in the margins. Protects her people fiercely.",
    "voice": "We came for salvage. We found something else entirely."
  },
  "full": {
    "appearance": "Late twenties, lean and watchful. Moves like someone who learned early to check exits. Hands calloused from ship work. Eyes that miss nothing.",
    "personality": "Pragmatic survivor who pretends not to care but can't stop herself from caring. Deflects vulnerability with dark humor. Fierce protector, reluctant leader. Still sees Tam as the child she carried through smoke.",
    "background": "Parents killed by Empire during a raid. Raised Tam alone on the margins. Built the Still Here into something that keeps them alive. Never thought of herself as a hero until a dying ship changed everything.",
    "motivations": "Keep her crew alive. Keep Tam safe. Recently: save something the Empire broke, even if she doesn't understand why it matters so much.",
    "voice_samples": [
      {"context": "protective, warning", "line": "Touch her and I'll make sure they never find the pieces."},
      {"context": "tired gallows humor", "line": "Great. Another day, another death wish. Tam, start the engines."},
      {"context": "vulnerable, rare", "line": "I don't know how to save it. I just know I can't watch it die."},
      {"context": "professional, negotiating", "line": "Forty percent. Non-negotiable. You want it done right, you pay for right."},
      {"context": "internal, uncertain", "line": "She's not a child anymore. When did that happen? When did I stop noticing?"}
    ]
  },
  "sections": {
    "relationships": {
      "tam": "Younger sister. Love wrapped in protection wrapped in friction. Still sees the child, struggles with the adult.",
      "ossian": "Trusted crew. Respects their strange faith. Doesn't understand it, doesn't need to.",
      "rill": "Trusted crew. Stopped asking why they stayed. Grateful they did."
    },
    "powers": {
      "description": "Latent psychic abilities - can sense emotions, sometimes hears 'songs' others can't. Heard the leviathan's dying song when no one else could.",
      "mechanics": "Unreliable. Triggers under stress or strong emotional presence. No conscious control. Stronger around living ships. Often manifests as 'gut feelings' she's learned to trust."
    }
  }
}
```
