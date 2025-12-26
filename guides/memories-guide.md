# Creating Memories

Create memory JSON files for campaign memory tracking. Files go in `memories/` folder and support cross-references to characters, locations, and other memories.

## JSON Schema

```json
{
  "id": "memory-id",
  "title": "Display Title",
  "campaign": "campaign-name",
  "text": "The memory text. Can be multiple paragraphs.",

  "type": "vivid-moment",
  "format": "vivid",
  "era": "~15000 BCE",
  "session": "s03",
  "intensity": "high",
  "perspective": "first-person",
  "tags": ["loss", "revelation", "turning-point"],

  "log_entry": "log-00007",
  "story": "tale-of-the-truth",

  "connections": {
    "characters": ["character-id-1", "character-id-2"],
    "locations": ["location-id"],
    "stories": ["story-id"],
    "related_memories": ["other-memory-id"],
    "log_entries": ["log-00007"]
  }
}
```

## Field Reference

### Required

- **id**: Unique identifier (lowercase, hyphenated)
- **text**: The memory content

### Recommended

- **title**: Display title (falls back to id if missing)
- **campaign**: Campaign identifier for filtering across multiple campaigns

### Optional Metadata

- **type**: Category of memory (what kind of event). Common types:
  - `vivid-moment` - Intense, emotionally charged scene
  - `quiet-moment` - Subtle character beat
  - `revelation` - Discovery or realization
  - `turning-point` - Story pivot
  - `world-building` - Setting/lore detail
  - `relationship` - Character interaction

- **format**: Structural format (how it's written). Distinct from type:
  - `vivid` - Present-tense, sensory, reliving the moment ("I am there again")
  - `sequential` - Past-tense blow-by-blow account ("First X, then Y, then Z")
  - `summary` - Condensed overview, key points only

- **era**: Time period. Supports chronological sorting.
  - Examples: `"~15000 BCE"`, `"Session 3"`, `"Early childhood"`, `"2847 CE"`
  - Parsed for sorting: BCE/BC dates sort before CE/AD

- **session**: Session identifier
  - Flexible format: `"s01"`, `"session-01"`, `"Session 1"`, `"01"`
  - Parsed for sorting (extracts the number)

- **intensity**: Emotional weight. Useful for filtering:
  - `low` - Quiet, subtle
  - `medium` - Significant but not overwhelming
  - `high` - Intense, pivotal

- **perspective**: Point of view
  - `first-person` - From a character's internal view
  - `third-person` - External narration
  - `omniscient` - Multiple viewpoints or meta-knowledge

- **tags**: Array of freeform labels for filtering

### Cross-References

Link memories to related log entries and stories:

- **log_entry**: Single log entry id this memory expands upon
- **story**: Single story id derived from this memory

### Connections

Cross-references to other campaign data (in `connections` object):

- **characters**: Array of character ids who appear in this memory
- **locations**: Array of location ids where this memory takes place
- **stories**: Array of story ids this memory relates to
- **related_memories**: Array of memory ids that form a narrative thread
- **log_entries**: Array of log entry ids related to this memory

The tool validates connections and warns if referenced ids don't exist.

## CLI Reference

```bash
# List and filter
memories.py list --campaign NAME
memories.py list --character NAME          # Filter by character
memories.py list --location NAME           # Filter by location
memories.py list --type vivid-moment       # Filter by type
memories.py list --format vivid            # Filter by format
memories.py list --intensity high          # Filter by intensity
memories.py list --tag loss                # Filter by tag
memories.py list --short                   # Show details without text

# Retrieve
memories.py get ID                         # Get specific memory
memories.py random --campaign NAME         # Random memory (with optional filters)

# Search and explore
memories.py search "query" --campaign NAME # Full-text search
memories.py character NAME                 # All memories involving character
memories.py location NAME                  # All memories at location
memories.py connections ID                 # Show all connections for a memory
memories.py chain ID                       # Follow related_memories thread

# Metadata
memories.py meta --campaign NAME           # Show types, tags, intensities summary
memories.py recent --campaign NAME         # Most recent by session
memories.py recent --by-era                # Most recent by era chronology
```

## Workflow

### Step 1: Capture During/After Session

During play, note moments that feel significant:
- Emotional peaks
- Character revelations
- Decisions with consequences
- Quiet scenes that resonate

### Step 2: Write the Memory

Write the memory text. Focus on:
- Sensory details that anchor the moment
- Emotional truth over factual completeness
- What the character experienced, not just what happened

### Step 3: Categorize

Add metadata:
- **type**: What kind of moment was this?
- **intensity**: How emotionally charged?
- **perspective**: Whose viewpoint?
- **tags**: What themes does it touch?

### Step 4: Connect

Link to:
- Characters present or affected
- Location where it happened
- Related memories (for narrative threads)

### Step 5: Save

Save to `memories/{id}.json` or add to a collection file.

Files can contain a single memory object OR an array of memories:

```json
[
  {"id": "mem-1", "text": "...", ...},
  {"id": "mem-2", "text": "...", ...}
]
```

## Example: Vivid Moment

```json
{
  "id": "first-sight-of-leviathan",
  "title": "First Sight of the Leviathan",
  "campaign": "still-here",
  "text": "The hull groaned as we drifted closer. At first I thought it was debris—some dead station, another corpse in the void. Then it moved. Not the movement of metal, but something alive. Something breathing.\n\nTam's hand found mine in the dark. Neither of us spoke. What do you say when you find a god dying in the wreckage of empire?",

  "type": "vivid-moment",
  "era": "Session 1",
  "session": "s01",
  "intensity": "high",
  "perspective": "first-person",
  "tags": ["awe", "discovery", "leviathan", "turning-point"],

  "connections": {
    "characters": ["juno", "tam"],
    "locations": ["graveyard-of-ships"],
    "related_memories": ["leviathan-song", "choosing-to-stay"]
  }
}
```

## Example: Quiet Moment

```json
{
  "id": "tam-repairs-juno-jacket",
  "title": "The Jacket",
  "campaign": "still-here",
  "text": "She didn't ask. Just took the jacket from my hands while I was sleeping, and when I woke it was mended. The stitches were crooked—Tam never had patience for needlework—but they held.\n\nI wore it to the negotiation. Didn't mention the repair. Some things don't need words.",

  "type": "quiet-moment",
  "session": "s04",
  "intensity": "low",
  "perspective": "first-person",
  "tags": ["family", "care", "unspoken"],

  "connections": {
    "characters": ["juno", "tam"]
  }
}
```

## Example: World-Building

```json
{
  "id": "leviathan-history",
  "title": "What the Archives Said",
  "campaign": "still-here",
  "text": "The Empire called them 'biological transit infrastructure.' Built to carry cargo across impossible distances. Grown, not manufactured. Millions of them once swam the void.\n\nThen the Empire fell, and no one remembered how to speak to them. They died slowly. Most are gone now. This one—somehow—survived.",

  "type": "world-building",
  "intensity": "medium",
  "perspective": "omniscient",
  "tags": ["lore", "leviathan", "empire", "extinction"],

  "connections": {
    "locations": ["imperial-archive"],
    "related_memories": ["first-sight-of-leviathan"]
  }
}
```

## Using Memories in Sessions

Pull memories contextually:
- `memories.py character juno` before scenes focused on Juno
- `memories.py random --intensity high` when you need emotional weight
- `memories.py search "leviathan"` when the creature reappears
- `memories.py chain first-sight-of-leviathan` to trace a narrative thread

Memories provide continuity and emotional grounding. Reference them to maintain consistency and deepen resonance.
