# Campaign State System

Track campaign state across sessions with event logs, character state, branches for multi-protagonist campaigns, and a complete audit trail of all changes.

## System Overview

The campaign state system provides:

- **Campaign Log** - Chronicle events with dates, characters, locations, and narrative tags
- **Branch Management** - Support parallel storylines with different protagonists
- **State Tracking** - Monitor volatile character state (location, inventory, conditions)
- **Character Development** - Update development-tier fields with automatic changelog
- **Audit Trail** - Complete history of all state changes and character updates
- **Calendar System** - Flexible date handling (structured dates or narrative descriptions)
- **Export/Import** - Back up and restore campaigns to zip archives

## Campaign Initialization

### Creating a New Campaign

```bash
# Initialize with default offset calendar (Y3.D45 format)
campaign.py init "Campaign Name"

# Initialize with specific calendar type
campaign.py init "Campaign Name" --calendar offset
```

This creates:
- `campaign/config.json` - Campaign configuration, branches, calendar settings
- `campaign/state.json` - Current campaign state (active branch, character states)

Initial config includes a "main" branch by default.

### View Campaign Configuration

```bash
# Human-readable summary
campaign.py show

# JSON output
campaign.py show --json
```

Output shows:
- Campaign name
- Calendar type and configuration
- All branches with protagonists and status

## Export and Import

Back up campaigns or move them between systems.

### Export Campaign

```bash
# Export with automatic filename (campaign-name-YYYYMMDD.zip)
campaign.py export

# Export with custom filename
campaign.py export --output backup.zip

# JSON output (returns manifest)
campaign.py export --json
```

Exports all JSON files from:
- `campaign/` - Config, state, log, changelog
- `characters/`, `locations/`, `memories/`, `stories/`, `namesets/`

Creates a manifest with counts for each directory.

### Import Campaign

```bash
# Import to current directory
campaign.py import backup.zip

# Import to specific folder
campaign.py import backup.zip --into ./restored-campaign

# JSON output
campaign.py import backup.zip --json
```

Validates archive structure and reports contents.

## Branch Management

Use branches for:
- Multi-protagonist campaigns with parallel storylines
- Alternate timelines or "what if" scenarios
- Different perspectives on the same events

### List Branches

```bash
# Show all branches and mark active
campaign.py branch list

# JSON output
campaign.py branch list --json
```

### Create a Branch

```bash
# Basic branch
campaign.py branch create branch-id "Branch Name"

# Branch with protagonists
campaign.py branch create juno-arc "Juno's Story" --protagonists juno,tam

# Fork from another branch
campaign.py branch create alt-timeline "Alternate Path" --from main
```

### Switch Active Branch

```bash
campaign.py branch switch branch-id
```

The active branch is used for:
- Log entries (automatically tagged with current branch)
- State changes (tracked per branch context)
- Character filtering (show only branch protagonists)

## Campaign Log

The log tracks narrative events chronologically with rich metadata.

### Adding Log Entries

```bash
# Basic entry with structured date
log.py add "Juno found the derelict ship" --date Y3.D45

# Entry with loose/narrative date
log.py add "The festival begins" --date-loose "three days after arrival"

# Entry with full metadata
log.py add "Confrontation in the market" \
  --date Y3.D47 \
  --branch main \
  --characters juno:defining,tam:present,marco:witness \
  --locations "market-district" \
  --tags combat,revelation \
  --importance major \
  --session s05

# Importance levels: minor, normal, major, critical
```

**Character Roles** (for `--characters`):
- `defining` - Character-defining moment
- `present` - Actively involved
- `witness` - Observing but not central
- `mentioned` - Referenced but not present

**Date Formats**:
- Structured: `Y3.D45` (parsed and sorted chronologically)
- Loose: `"after the festival"` (narrative, sorts after structured dates)

### Listing Log Entries

```bash
# All entries (chronological order)
log.py list

# Filter by branch
log.py list --branch main

# Filter by character involvement
log.py list --character juno

# Filter by location
log.py list --location market-district

# Filter by importance
log.py list --importance major

# Filter by tag
log.py list --tag combat

# Date range
log.py list --from Y3.D40 --to Y3.D50

# Limit results
log.py list --limit 10

# Verbose output (full details)
log.py list --verbose

# JSON output
log.py list --json
```

### View Specific Entry

```bash
# Show full entry details
log.py show log-00001

# JSON output
log.py show log-00001 --json
```

### Delete Entry

```bash
log.py delete log-00001
```

## State Tracking

State tracking manages volatile character attributes that change frequently during play.

### What Goes in State vs Character Profile

**State** (volatile, session-level):
- Current location
- Current inventory items
- Active conditions (wounded, exhausted, etc.)
- Temporary relationships or allegiances
- Resource counts (credits, supplies, etc.)

**Character Profile** (development-level):
- Personality traits
- Permanent abilities or powers
- Background and history
- Long-term relationships
- Physical description

### View Campaign State

```bash
# Show all state
campaign.py state show

# Show state for specific character
campaign.py state show --character juno

# JSON output
campaign.py state show --json
```

### Set Character State

```bash
# Basic state change
campaign.py state set juno location "market-district" \
  --reason "Arrived seeking information" \
  --session s05

# Inventory
campaign.py state set juno inventory.credits "450" \
  --reason "Paid Marco for intel"

# Conditions
campaign.py state set tam condition.wounded "true" \
  --reason "Injured in market fight"
```

Every state change is automatically logged to the changelog with:
- Session identifier
- Branch context
- Old and new values
- Reason for change

### State and Branches

State is global but branch-aware. When you switch branches, state remains but queries can be filtered by branch context (via changelog entries).

## Character Development

Use the character update command to modify development-tier fields in character JSON files.

### Update Character Fields

```bash
# Update a top-level field
characters.py update juno \
  --field "minimal.essence" \
  --value "Salvager haunted by choice. Saved a dying ship, can't save herself." \
  --reason "Character growth after session 5" \
  --session s05

# Update nested section
characters.py update juno \
  --field "sections.relationships.tam" \
  --value "Sister. Love wrapped in friction. Learning to see the adult, not the child." \
  --reason "Relationship evolution" \
  --session s05

# Update full profile fields
characters.py update juno \
  --field "full.motivations" \
  --value "Keep crew alive. Find purpose beyond survival. Understand what she saved." \
  --reason "Arc development"

# JSON output
characters.py update juno --field X --value Y --reason Z --json
```

Updates are automatically:
- Saved to the character JSON file
- Logged to changelog with tier="development"
- Timestamped with session context

### Development Tiers

Character data is divided into tiers:

**Minimal Tier** (always loaded):
- role, essence, voice - Core identity

**Full Tier** (loaded with --depth full):
- appearance, personality, background, motivations, voice_samples

**Sections** (loaded on-demand):
- relationships, powers, combat, timeline, secrets, custom sections

Updates to minimal/full fields use `characters.py update`. Updates to state-level attributes use `campaign.py state set`.

## Changelog Queries

The changelog is an append-only audit trail of all changes (state and development).

### View Changelog

```bash
# All changes
campaign.py changelog show

# Filter by character
campaign.py changelog show --character juno

# Filter by session
campaign.py changelog show --session s05

# Filter by field pattern
campaign.py changelog show --field location

# Filter by tier (state or development)
campaign.py changelog show --tier state
campaign.py changelog show --tier development

# Limit results (most recent N)
campaign.py changelog show --limit 10

# JSON output
campaign.py changelog show --json
```

### Changelog Entry Structure

Each entry contains:
- **id** - Unique change identifier (change-00001)
- **session** - Session when change occurred
- **branch** - Active branch during change (if applicable)
- **character** - Character affected
- **tier** - "state" or "development"
- **field** - Field path that changed
- **from** - Previous value
- **to** - New value
- **reason** - Why the change was made
- **created** - Timestamp

### Audit Use Cases

```bash
# Review all changes to a character across campaign
campaign.py changelog show --character juno

# See what happened in a specific session
campaign.py changelog show --session s05

# Track location changes
campaign.py changelog show --field location

# Review character development changes only
campaign.py changelog show --tier development --character juno
```

## Calendar System

The campaign uses configurable calendar systems for in-world dates.

### Offset Calendar

Default calendar type. Simple renamed/renumbered dates.

**Format**: `Y{year}.D{day}` or `Year {year}, Day {day}`

Examples:
- `Y3.D45` - Year 3, Day 45
- `Y-1.D100` - Year -1, Day 100 (before epoch)
- `Year 5, Day 12` - Verbose format

**Configuration** (in `campaign/config.json`):
```json
{
  "calendar": {
    "type": "offset",
    "config": {
      "year_prefix": "Y",
      "day_prefix": "D",
      "epoch": "After Founding"
    }
  }
}
```

Dates are parsed and sorted chronologically. Negative years sort before positive.

### Loose Dates

For narrative flexibility, use loose dates when precise dates aren't needed:

```bash
log.py add "Memory surfaces" --date-loose "three days after the festival"
log.py add "Arrival at station" --date-loose "during the long night"
```

Loose dates:
- Sort after all structured dates
- Not parsed or validated
- Useful for flashbacks, memories, or vague timeframes

### Calendar Extensibility

The calendar system is modular. Future calendar types can be added to `scripts/lib/calendars/` without changing log or campaign tools.

## Campaign Digest

The digest command provides a tiered overview of campaign events, useful for context recall.

### Usage

```bash
# Basic digest
log.py digest

# Filter by character involvement
log.py digest --character juno

# Override tier limits
log.py digest --pillar-limit 5 --arc-sessions 10 --current-sessions 3

# JSON output
log.py digest --json
```

### Digest Tiers

1. **PILLARS** - Critical events from all time (limited by pillar_limit)
2. **RECENT ARC** - Major+ events from last N sessions (arc_sessions)
3. **CURRENT** - All events from last N sessions (current_sessions)

### Configuration

Configure digest defaults in `campaign/config.json`:

```json
{
  "digest": {
    "pillar_limit": 10,
    "arc_sessions": 20,
    "current_sessions": 5
  }
}
```

CLI arguments override config values. Config values override hardcoded defaults.

## Integration Patterns

### Session Start

```bash
# Switch to active branch if needed
campaign.py branch switch juno-arc

# Review recent events
log.py list --branch juno-arc --limit 5

# Check character state
campaign.py state show --character juno
```

### During Session

```bash
# Log major events as they happen
log.py add "Event description" --date Y3.D45 --characters juno:defining

# Update character location
campaign.py state set juno location "new-location" \
  --reason "Traveled to new location" \
  --session s06

# Update inventory or conditions as needed
campaign.py state set juno inventory.medkits "3" \
  --reason "Used one during fight"
```

### Session End

```bash
# Log session-ending events
log.py add "Session cliffhanger" --date Y3.D46 --session s06

# Update character development if needed
characters.py update juno \
  --field "sections.relationships.tam" \
  --value "Updated relationship description" \
  --reason "Evolved during session 6" \
  --session s06

# Review what changed this session
campaign.py changelog show --session s06
```

### Character Filtering by Branch

```bash
# Show only protagonists from a specific branch
characters.py list --branch juno-arc

# Combined with other filters
characters.py list --branch juno-arc --faction still-here-crew
```

### Character Filtering by Location

```bash
# Show characters currently at a location
characters.py list --location market-district
```

Location filtering uses campaign state. Characters must have `location` set via `campaign.py state set`.

## File Structure

```
campaign/
  config.json      # Campaign configuration and branches
  state.json       # Current campaign state
  log.json         # Event log entries
  changelog.json   # Audit trail of all changes

characters/
  juno.json        # Character profiles (development tier)
  tam.json
  ...

locations/         # Location data (reference only)
  ...
```

## Example Workflow: Multi-Branch Campaign

```bash
# Initialize campaign
campaign.py init "Still Here"

# Create branches for different protagonists
campaign.py branch create juno-arc "Juno's Journey" --protagonists juno,tam
campaign.py branch create ossian-arc "Ossian's Path" --protagonists ossian

# Work on Juno's arc
campaign.py branch switch juno-arc
log.py add "Found the derelict" --date Y3.D45 --characters juno:defining,tam:present
campaign.py state set juno location "graveyard-of-ships" --reason "Following distress signal"

# Switch to Ossian's arc
campaign.py branch switch ossian-arc
log.py add "Vision in the temple" --date Y3.D45 --characters ossian:defining
campaign.py state set ossian location "temple-ruins" --reason "Seeking guidance"

# Later: review both timelines
log.py list --branch juno-arc
log.py list --branch ossian-arc

# View all characters in each arc
characters.py list --branch juno-arc
characters.py list --branch ossian-arc
```

## Best Practices

### Log Entries
- Log major plot events, not minutiae
- Use importance levels to distinguish critical moments
- Tag character roles accurately (defining vs present vs witness)
- Use structured dates when possible, loose dates for flexibility

### State Management
- Update state as it changes during sessions
- Always provide meaningful reasons for changelog
- Use session identifiers consistently
- Review state at session start to maintain continuity

### Character Development
- Update character profiles when permanent changes occur
- Distinguish between temporary state and lasting development
- Use changelog to track character growth over time
- Reference session context for all development changes

### Branch Usage
- Create branches for genuinely parallel storylines
- Keep protagonist lists updated
- Use branch filtering to focus on relevant characters
- Consider convergence points where branches might merge

### Changelog Review
- Review session changelog at end of each session
- Use changelog to prepare session recaps
- Reference changelog when writing character summaries
- Use tier filtering to separate state churn from development

## Anti-Patterns - AVOID These

- **Don't** log every minor action (save for important events)
- **Don't** mix state and development (use correct tier)
- **Don't** forget to provide reasons for changes
- **Don't** create branches unnecessarily (only for parallel storylines)
- **Don't** use loose dates when structured dates are possible
- **Don't** skip session identifiers (needed for changelog filtering)
- **Don't** update character files directly (use `characters.py update`)
- **Don't** forget to switch branches when working on different arcs
