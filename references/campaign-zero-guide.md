# Campaign Zero Guide

Pre-campaign preparation through guided brainstorming. Build the skeleton; discover the flesh in play.

## Contents

- [Philosophy](#philosophy)
- [The Conversation](#the-conversation)
  - [Core: The Load-Bearing Bones](#core-the-load-bearing-bones)
  - [Breadth: Thematic Seeds and Counter-Weights](#breadth-thematic-seeds-and-counter-weights)
  - [Depth: Islands of Detail](#depth-islands-of-detail)
- [The Bundle](#the-bundle)
  - [Bundle Structure](#bundle-structure)
  - [Primer Responsibilities](#primer-responsibilities)
  - [The claude.md File](#the-claudemd-file)
  - [Bundle Checklist](#bundle-checklist)
- [Anti-Patterns](#anti-patterns)
- [After Session 01](#after-session-01)

---

## Philosophy

Campaign prep is a conversation, not a checklist. The goal is to build a **skeleton**—structural scaffolding that guides emergence—not to pre-write the story.

### Skeleton, Not Flesh

Define structure, defer specifics:
- "Magic costs something personal" (skeleton) vs. "Magic drains your memories" (flesh)
- "A faction controls the station" (skeleton) vs. complete org chart (flesh)
- "The protagonist carries guilt" (skeleton) vs. their full backstory (flesh)

The skeleton gives Claude enough to riff coherently. Play adds muscle and skin.

### Author Knowledge vs. Character Knowledge

You can decide things your character doesn't know yet:
- The magic system's rules (even if characters are discovering them)
- What the faction secretly wants (even if it's hidden from the protagonist)
- Why the world is the way it is (even if that's a mystery in-story)

This isn't spoiling discovery—it's giving the GM a foundation to build on.

### Counter-Weight the Protagonist

In solo play, the protagonist is a gravity well. Everything bends toward them. Without deliberate counter-weights, the world becomes an echo chamber.

Seed elements with their own gravity:
- Factions with agendas that don't involve you
- NPCs with problems you didn't cause
- Events happening regardless of your actions
- Tensions that predate your arrival

The world should feel like it existed before you and will continue after.

### Session 01 is Worldbuilding

Most data files are created *after* session 01, not before. The first session is where you discover:
- What the protagonist actually feels like in play
- Which NPCs have chemistry
- What locations matter
- What threads catch fire

Pre-session prep creates a bootstrap. Play creates the world.

---

## The Conversation

Campaign prep works best as guided brainstorming—asking yourself questions, exploring possibilities, finding what resonates. These prompts aren't a checklist; pick what's relevant, skip what isn't.

### Core: The Load-Bearing Bones

These are the minimum bones needed to start session 01.

**The Protagonist**
- Who are you playing? A sketch, not a biography.
- What's their role? (salvager, scholar, exile, healer...)
- What's one driving tension? (guilt, ambition, loyalty vs. freedom, a debt...)
- What do they want? What's stopping them?

Don't over-specify. Leave room for the character to surprise you.

**The Starting Situation**
- Where do we open? A specific place, even if loosely defined.
- What's immediately happening? Not backstory—the present moment.
- What's the first decision or problem?

The opening should drop you into motion, not exposition.

**The Tone Contract**
- What genre feel? (noir, hopeful, gritty, lyrical, tense, absurd...)
- What's the emotional register? (intimate, epic, melancholy, wry...)
- What's on the table? What's off limits?
- Any modifiers to load? (mature-content, combat-realism)

This shapes how Claude narrates, what it introduces, how dark or light things get.

**One Source of Tension**
- What's unresolved that creates forward momentum?
- This can be personal (the protagonist's guilt), situational (a threat), or social (a faction conflict)
- It doesn't need to be the central plot—just enough to move.

### Breadth: Thematic Seeds and Counter-Weights

If themes are too narrow, stories get repetitive. Seed enough that Claude has a palette.

**Thematic Seeds**
Themes can come from multiple sources:
- **Explicit**: "This campaign explores identity, legacy, the cost of survival"
- **Embedded**: A faction built around "reclaiming lost heritage" implies legacy themes
- **Protagonist-rooted**: Their contradictions imply questions the story asks
- **Genre-inherited**: Noir implies moral compromise; space western implies frontier justice

Mix sources. Don't rely only on protagonist-rooted themes—the story shouldn't just be a mirror.

**Counter-Weights**
What exists independent of the protagonist?
- A faction with its own goals
- A conflict brewing that doesn't involve you
- An NPC with their own arc
- Forces in motion that don't care about your character

These prevent the world from collapsing into protagonist-orbit.

**World Rules**
Even if left vague, consider:
- What's possible? (magic, tech, the supernatural)
- What does power look like? Who has it?
- What are the constraints? (scarcity, law, physics, social rules)

You can define "magic works this way" even if characters don't understand it yet. Author knowledge.

### Depth: Islands of Detail

Sometimes you need to go deep on specific elements. Triggers for depth:

**The Protagonist Demands It**
- A court intrigue character needs a court to exist
- A ship captain needs crew dynamics
- A faction operative needs that faction to feel real

**The Premise Demands It**
- "Escape the dying station" needs the station sketched
- "Navigate faction war" needs factions with actual tensions
- "Solve the mystery" needs the mystery to have shape (even without a solution)

**The Tone Demands It**
- Hard sci-fi needs consistent tech rules
- Political drama needs power structures
- Heist needs a target worth the effort

**You're Adapting Material**
- Porting a setting from another source
- Continuing a previous campaign
- Playing in a shared universe

Go deep where it serves the story. Leave fog everywhere else.

---

## The Bundle

The output of campaign zero is a **starter bundle**—files a fresh Claude session can unpack and run as GM.

### Bundle Structure

```
campaign-bundle/
  claude.md              # GM instructions (what to read, what to load)
  setting-primer.md      # The world (permanent)
  campaign-primer.md     # This story's skeleton (permanent)
  session-01-primer.md   # Bootstrap content (disposable)
  namesets/              # Custom namesets (if any)
    culture-name.json
```

### Primer Responsibilities

**Setting Primer** (permanent)
- The world itself, independent of this campaign
- Genre, tone, tech/magic level, social structures
- Could be reused for multiple campaigns in the same setting
- Survives the entire campaign

**Campaign Primer** (permanent)
- The skeleton for *this* story
- Central tensions, key factions in play, thematic seeds
- Counter-weights and forces in motion
- Lives alongside data files, keeps guiding the GM

**Session 01 Primer** (disposable)
- Bootstrap content that becomes real data through play
- Protagonist sketch (becomes character file after session)
- Initial scenario and hooks
- Opening questions to explore
- **Discarded after session 01**, replaced by produced data

### The claude.md File

The `claude.md` tells the GM Claude how to run this campaign. Template:

```markdown
# Campaign: [Name]

You are the GM for this solo RPG campaign.

## Setup

1. Load the `rpg-tools` skill
2. Read the primers in order:
   - `setting-primer.md` - The world
   - `campaign-primer.md` - This story's skeleton
   - `session-01-primer.md` - Where we begin (session 01 only)

## Modifiers

[List any modifiers to load, or "None"]
- `modifiers/mature-content.md` - [if applicable]
- `modifiers/combat-realism.md` - [if applicable]

## Custom Namesets

[List custom namesets, or "Using default namesets"]
- `namesets/[name].json` - [brief description]

## Campaign-Specific Notes

[Anything the GM needs to know that isn't in the primers]
- [Key rulings or conventions]
- [Pronunciation guides]
- [Things to emphasize or avoid]

## What Not to Do

- Don't contradict the primers without discussion
- Don't resolve the central tensions too quickly
- Don't forget the counter-weights exist
```

Keep this file **lean**. Don't duplicate what's already in the rpg-tools skill or the primers. This is glue, not content.

### Bundle Checklist

Before session 01, confirm:

**Files**
- [ ] `claude.md` - GM instructions
- [ ] `setting-primer.md` - World foundation
- [ ] `campaign-primer.md` - Story skeleton
- [ ] `session-01-primer.md` - Bootstrap content
- [ ] Custom namesets (if any)

**Content**
- [ ] Protagonist sketch (in session-01-primer)
- [ ] Starting situation defined
- [ ] Tone contract established
- [ ] At least one source of tension
- [ ] Thematic seeds (multiple sources, not just protagonist)
- [ ] Counter-weights seeded (things independent of protagonist)
- [ ] World rules sketched (even if vague)

**Decisions**
- [ ] Modifiers selected (mature-content? combat-realism?)
- [ ] Namesets chosen or created
- [ ] Content boundaries clear

---

## Anti-Patterns

**Plotting ahead**
Don't decide what happens before it happens. You can set up tensions; you can't script their resolution. The story emerges from play.

**Over-specifying**
Don't lock in details that should emerge. A character's full backstory, a faction's complete hierarchy, a city's every district—these calcify what should stay fluid.

**Protagonist tunnel vision**
Don't make everything about the protagonist. The world should have concerns that don't involve them. Counter-weight deliberately.

**Front-loading all worldbuilding**
Don't exhaust yourself before play begins. Session 01 is worldbuilding. You're building a skeleton, not a complete anatomy.

**Premature data files**
Don't create character/location/memory files before session 01. You don't know what you need yet. The bundle contains primers and notes, not structured data.

**Theme monotony**
Don't seed only one thematic note. "Survival" is a theme; if it's the *only* theme, every session becomes about survival. Breadth prevents repetition.

**Solution-first mysteries**
Don't decide the answer before the question is interesting. Seed mysteries with shape but not solutions. Discovery is the point.

---

## After Session 01

Session 01 produces raw material. After the session:

1. **Create data files** from what emerged:
   - Protagonist → `characters/[id].json`
   - Key NPCs → character files
   - Visited locations → `locations/[id].json`
   - Important events → `memories/` or log entries

2. **Initialize campaign tracking**:
   ```bash
   campaign.py init "Campaign Name"
   ```

3. **Archive or discard** `session-01-primer.md`
   - The bootstrap content is now real data
   - Setting and campaign primers remain

4. **Prepare for session 02** using:
   - `setting-primer.md` (permanent)
   - `campaign-primer.md` (permanent)
   - Data files (characters, locations, memories)
   - [session-setup-guide.md](session-setup-guide.md) for per-session calibration

The campaign is now running. The skeleton has flesh.
