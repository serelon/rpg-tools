# Creating Locations

Create location JSON files for the hierarchical location loading system. Files go in `locations/` folder.

## JSON Schema

```json
{
  "id": "location-id",
  "name": "Display Name",
  "parent": "parent-location-id",
  "parents": ["alt-parent-1", "alt-parent-2"],
  "tags": ["settlement", "dangerous", "sacred"],

  "minimal": {
    "type": "city/room/region/ship/district",
    "essence": "35 words max - core feel, key features"
  },

  "full": {
    "description": "Detailed physical description",
    "atmosphere": "Mood, sensory details, what it feels like",
    "history": "Relevant background (evocative > exhaustive)",
    "notable_features": ["feature1", "feature2"],
    "dangers": "Hazards, threats (if any)",
    "secrets": "What's not immediately obvious"
  },

  "sections": {
    "npcs": ["character-id1", "character-id2"],
    "connections": {
      "other-location-id": "path description"
    },
    "resources": {},
    "custom": {}
  }
}
```

## Hierarchy & Graph

Locations support both tree hierarchy and graph connections:

### Tree Hierarchy (Containment)

- **parent**: Primary containment (required for tree view)
- **parents**: Additional containment for complex cases

Examples:
- A room's parent is a building
- A building's parent is a district
- A district's parent is a city

### Graph Connections (Travel)

Use `sections.connections` for paths, roads, portals:

```json
"connections": {
  "market-square": "main street, 5 minute walk",
  "wizard-tower": "hidden portal behind bookshelf"
}
```

Connections can be one-way or bidirectional. The tool tracks both directions.

## File Organization

- One JSON file per location: `locations/tavern.json`
- Or grouped by area: `locations/old-town.json` (array of locations)
- Discovered recursively from `locations/` folder

## Workflow

### Step 1: Establish Hierarchy

Before creating individual locations, sketch the containment hierarchy:

```
World
└─ Region
   └─ City
      ├─ District A
      │  ├─ Building 1
      │  └─ Building 2
      └─ District B
```

### Step 2: Create Root Locations First

Start with the largest containers (no parent):

```json
{
  "id": "the-kingdom",
  "name": "The Kingdom of Valdris",
  "parent": null,
  "tags": ["region", "kingdom"],
  "minimal": {
    "type": "kingdom",
    "essence": "Frost-touched realm between mountain and sea. Old magic in the stones, older grudges in the bloodlines."
  }
}
```

### Step 3: Build Down the Tree

Add children with parent references:

```json
{
  "id": "frosthold",
  "name": "Frosthold",
  "parent": "the-kingdom",
  "tags": ["city", "capital", "fortified"],
  "minimal": {
    "type": "city",
    "essence": "Capital carved from glacier. Walls of ancient ice that never melt. Heart of the kingdom, cold in more ways than one."
  }
}
```

### Step 4: Add Connections

For non-hierarchical links (roads, passages, portals):

```json
"sections": {
  "connections": {
    "harbor-district": "King's Road descends through switchbacks",
    "undercity": "secret passage from wine cellar"
  }
}
```

### Step 5: Full Details (As Needed)

Expand locations players interact with:

```json
"full": {
  "description": "The Frozen Crown sits atop the highest tier of Frosthold, its spires carved from blue glacier ice that predates the kingdom. Seven towers ring a central keep, connected by covered bridges.",
  "atmosphere": "Biting cold even in summer. Sound carries strangely - whispers in one room audible three chambers away. The ice walls glow faintly at night.",
  "history": "Built by the First King who bound a frost elemental into the foundations. Each monarch since has added a tower.",
  "notable_features": ["The Throne of Frozen Tears", "The Whispering Gallery", "The Elemental Heart below"],
  "dangers": "The ice remembers grudges. Those who break oaths here find the cold follows them.",
  "secrets": "The frost elemental is dying. Without it, the castle will collapse within a generation."
}
```

## Multi-Parent Locations

Some locations exist in multiple hierarchies:

```json
{
  "id": "shadow-market",
  "name": "The Shadow Market",
  "parent": "undercity",
  "parents": ["merchant-quarter"],
  "tags": ["market", "illegal", "hidden"],
  "minimal": {
    "type": "market",
    "essence": "Exists in the cracks between districts. Enter from the undercity or through certain merchant basements. Everyone pretends not to know."
  }
}
```

## Tags

Common tags to consider:
- **Scale**: region, city, district, building, room
- **Function**: market, temple, fortress, tavern, residence
- **Status**: abandoned, ruined, sacred, cursed, hidden
- **Access**: public, restricted, secret, dangerous

## Anti-Patterns - AVOID

- Exhaustive history for minor locations - evocative > exhaustive
- Missing parent references - breaks tree view
- Connections without descriptions - how do you get there?
- All locations at same detail level - major locations need more
- Forgetting atmosphere - locations need feel, not just facts

## Example: Grouped File

`locations/old-town.json`:
```json
[
  {
    "id": "old-town",
    "name": "Old Town",
    "parent": "frosthold",
    "tags": ["district", "residential", "historic"],
    "minimal": {
      "type": "district",
      "essence": "Original settlement before the city grew. Narrow streets, old families, older secrets. Stone buildings predate the ice castle."
    }
  },
  {
    "id": "grey-goose-inn",
    "name": "The Grey Goose Inn",
    "parent": "old-town",
    "tags": ["tavern", "safe", "information"],
    "minimal": {
      "type": "tavern",
      "essence": "Three hundred years of travelers. The innkeeper knows everything and says nothing. Best mulled wine in the city."
    },
    "sections": {
      "npcs": ["marta-innkeeper", "old-tom"],
      "connections": {
        "market-square": "main door to cobblestone street",
        "undercity": "trapdoor in the cellar (known to regulars)"
      }
    }
  }
]
```
