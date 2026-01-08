# Creating Factions

Create faction JSON files for tracking organizations with agency. Factions are treated as characters with structure, resources, and relationships. Files go in `factions/` folder.

## Design Philosophy

Factions are characters with agency. They have:
- **Identity** - Name, symbol, values, trajectory
- **Structure** - Hierarchy of subfactions, autonomy settings
- **Members** - Named characters, named units, abstracted pools
- **Relationships** - First-class edges to other factions and characters
- **Economy** - Accounts, costs, inventory, assets
- **Resources** - Faction-defined tracked values

## JSON Schema

```json
{
  "id": "faction-id",
  "name": "Display Name",
  "type": "fleet/house/guild/military/corporation",
  "parent": "parent-faction-id",
  "tags": ["criminal", "noble", "military"],

  "minimal": {
    "essence": "35 words max. Core identity, purpose, distinguishing trait.",
    "symbol": "Visual identifier or heraldry",
    "motto": "Their guiding phrase or creed",
    "current_status": "Brief current state description"
  },

  "full": {
    "history": "Relevant background - evocative > exhaustive",
    "values": "What they believe, what they protect",
    "operations": "How they work, their methods",
    "structure": "Organizational model (hierarchical, cellular, feudal)",
    "territories": "Areas of control or influence",
    "arc": {
      "trajectory": "Where they're heading",
      "themes": ["loyalty", "decay", "ambition"]
    }
  },

  "hierarchy": {
    "subfactions": [
      {
        "id": "subfaction-id",
        "name": "Subfaction Name",
        "autonomy": true,
        "role": "What this unit does"
      }
    ]
  },

  "members": {
    "named": ["character-id-1", "character-id-2"],
    "units": [
      {
        "name": "Unit Name",
        "count": 50,
        "morale": "high",
        "role": "Function within faction",
        "location": "location-id",
        "linked_members": ["character-id"]
      }
    ],
    "pools": [
      {
        "label": "1,200 crew",
        "state": "stable"
      }
    ]
  },

  "relationships": [
    {
      "type": "ally",
      "target": "other-faction-id",
      "state": {
        "trust": "high",
        "terms": "mutual defense pact"
      },
      "notes": "Freeform context"
    }
  ],

  "economy": {
    "accounts": [
      {
        "category": "liquid",
        "balance": 45000,
        "notes": "Operating funds"
      }
    ],
    "running_costs": [
      {
        "line": "Crew wages",
        "amount": 12000,
        "period": "month"
      }
    ],
    "inventory": [
      {
        "item": "Cargo container",
        "qty": 20,
        "value": 500,
        "location": "main-hold",
        "legality": "legal"
      }
    ],
    "assets": [
      {
        "name": "The Still Here",
        "type": "ship",
        "value": 250000,
        "notes": "Salvage vessel, heavily modified"
      }
    ]
  },

  "resources": {
    "supply": 85,
    "fuel": 60,
    "ammunition": 40
  },

  "sections": {}
}
```

## Field Reference

### Required

- **id**: Unique identifier (lowercase, hyphenated)
- **name**: Display name

### Recommended

- **type**: Organizational type (fleet, house, guild, military, corporation, crew, cult)
- **parent**: Parent faction ID for nested organizations

### Minimal Profile

Always loaded. Keep compact.

- **essence**: 35 words MAX. Core identity + purpose + distinguishing trait
- **symbol**: Visual identifier, heraldry, insignia
- **motto**: Their creed or guiding phrase
- **current_status**: Brief current state

### Full Profile

Loaded with `--depth full`.

- **history**: Relevant background (evocative > exhaustive)
- **values**: What they believe and protect
- **operations**: Methods, how they work
- **structure**: Organizational model
- **territories**: Areas of control or influence
- **arc**: Trajectory and themes for story purposes

## Hierarchy & Subfactions

Factions support nested hierarchy with configurable autonomy.

### Single Parent Rule

Each subfaction has one parent. Use `parent` field:

```json
{
  "id": "engineering-dept",
  "name": "Engineering Department",
  "parent": "ins-leviathan"
}
```

### Subfaction Autonomy

Track whether subfactions can act independently:

```json
"hierarchy": {
  "subfactions": [
    {
      "id": "house-verdania-merchants",
      "name": "Merchant Arm",
      "autonomy": true,
      "role": "Trade operations"
    },
    {
      "id": "house-verdania-guard",
      "name": "House Guard",
      "autonomy": false,
      "role": "Security and enforcement"
    }
  ]
}
```

### Sibling Relationships

Subfactions under the same parent can have relationships with each other:

```json
"relationships": [
  {
    "type": "rival",
    "target": "house-verdania-guard",
    "state": {
      "tension": "high"
    },
    "notes": "Merchants resent Guard's interference in trade deals"
  }
]
```

## Relationship Edge Types

Relationships are first-class edges with type-specific state.

### Core Types

| Type | State Fields | Use Case |
|------|--------------|----------|
| `ally` | trust, terms | Mutual support agreements |
| `enemy` | threat, conflict | Active opposition |
| `rival` | tension, domain | Competition without open hostility |
| `debtor` | principal, rate, accruing | Owed money or favors |
| `creditor` | principal, rate, accruing | Owed money or favors |
| `vassal` | obligations, tribute | Subordinate relationship |
| `patron` | protection, expectations | Protector relationship |
| `reports_to` | via, bypasses | Authority chains |
| `neutral` | last_contact | No active relationship |

### Relationship Examples

```json
"relationships": [
  {
    "type": "debtor",
    "target": "syndicate-bank",
    "state": {
      "principal": 50000,
      "rate": 0.08,
      "accruing": true
    },
    "notes": "Loan for ship repairs, due Y4.D100"
  },
  {
    "type": "reports_to",
    "target": "imperial-navy-command",
    "state": {
      "via": "sector-command",
      "bypasses": ["local-governor"]
    },
    "notes": "Direct line to admiralty in emergencies"
  },
  {
    "type": "ally",
    "target": "tam",
    "state": {
      "trust": "absolute",
      "terms": "family"
    },
    "notes": "Juno's sister, crew member"
  }
]
```

### Freeform Extension

All relationship types allow additional fields:

```json
{
  "type": "enemy",
  "target": "imperial-customs",
  "state": {
    "threat": "moderate",
    "conflict": "evasion",
    "wanted_level": 2,
    "last_encounter": "Y3.D45"
  },
  "notes": "They know the ship but not the crew"
}
```

## Member Tiers

Track members at appropriate granularity.

### Named Members

Links to character JSON files. Full character data available.

```json
"members": {
  "named": ["juno", "tam", "ossian", "rill"]
}
```

### Named Units

Groups with identity but not individual character files.

```json
"units": [
  {
    "name": "Alpha Squad",
    "count": 12,
    "morale": "high",
    "role": "Boarding operations",
    "location": "barracks-deck",
    "linked_members": ["sergeant-voss"]
  },
  {
    "name": "Engineering Team",
    "count": 8,
    "morale": "stable",
    "role": "Ship maintenance",
    "location": "engineering-bay",
    "linked_members": ["chief-engineer-mora"]
  }
]
```

Unit fields:
- **name**: Required. Unit identifier.
- **count**: Number of members.
- **morale**: Current state (high, stable, low, broken).
- **role**: Function within faction.
- **location**: Current location ID.
- **linked_members**: Character IDs of notable individuals in unit.

### Abstracted Pools

Large groups tracked minimally.

```json
"pools": [
  {
    "label": "1,200 crew",
    "state": "stable"
  },
  {
    "label": "~500 household staff",
    "state": "loyal"
  }
]
```

## Economy Submodule

Track faction finances and material resources.

### Accounts

```json
"accounts": [
  {
    "category": "liquid",
    "balance": 45000,
    "notes": "Operating funds"
  },
  {
    "category": "receivables",
    "balance": 12000,
    "notes": "Owed by House Maren"
  },
  {
    "category": "payables",
    "balance": -8000,
    "interest": 0.05,
    "notes": "Owed to dockmaster"
  }
]
```

Account categories:
- **liquid**: Available funds
- **receivables**: Money owed to faction
- **payables**: Money faction owes
- **reserves**: Emergency funds
- **invested**: Tied up in ventures

### Running Costs

```json
"running_costs": [
  {
    "line": "Crew wages",
    "amount": 12000,
    "period": "month"
  },
  {
    "line": "Fuel and supplies",
    "amount": 3000,
    "period": "month"
  },
  {
    "line": "Docking fees",
    "amount": "500 * days_docked",
    "period": "variable",
    "notes": "Formula-driven"
  }
]
```

### Inventory

Default legality is "legal" unless specified.

```json
"inventory": [
  {
    "item": "Medical supplies",
    "qty": 50,
    "value": 100,
    "location": "cargo-bay-2"
  },
  {
    "item": "Restricted weapons",
    "qty": 10,
    "value": 2000,
    "location": "hidden-compartment",
    "legality": "illegal"
  }
]
```

### Assets

Freeform complex items.

```json
"assets": [
  {
    "name": "The Still Here",
    "type": "ship",
    "value": 250000,
    "notes": "Salvage vessel, heavily modified, irreplaceable"
  },
  {
    "name": "Warehouse 7",
    "type": "property",
    "value": 80000,
    "location": "port-district",
    "notes": "Leased to third party"
  }
]
```

## Resources

Faction-defined tracked values. Schema is flexible.

```json
"resources": {
  "supply": 85,
  "fuel": 60,
  "ammunition": 40,
  "jump_charges": 3,
  "political_capital": "moderate"
}
```

Use whatever makes sense for your faction. Values can be numeric or descriptive.

## Scale Examples

### Tight Scale: Crew/Fleet (~40 named)

**Example: Delacroix Fleet**

Small organization with full economic detail and mostly named members.

```json
{
  "id": "delacroix-fleet",
  "name": "Delacroix Fleet",
  "type": "fleet",
  "tags": ["salvage", "independent", "smuggling"],

  "minimal": {
    "essence": "Three-ship salvage operation on the margins. Family by choice, not blood. Survive first, profit second, principles somewhere in between.",
    "symbol": "Crossed wrenches over a star",
    "motto": "We came for salvage.",
    "current_status": "Recovering from the Leviathan encounter, resources strained"
  },

  "members": {
    "named": ["juno", "tam", "ossian", "rill", "marco-pilot", "kessa-engineer"],
    "units": [
      {
        "name": "Bridge Crew",
        "count": 4,
        "morale": "high",
        "role": "Ship operations",
        "linked_members": ["juno", "tam"]
      }
    ],
    "pools": []
  },

  "economy": {
    "accounts": [
      {"category": "liquid", "balance": 12000, "notes": "After last job"}
    ],
    "running_costs": [
      {"line": "Crew shares", "amount": 6000, "period": "month"},
      {"line": "Ship maintenance", "amount": 2000, "period": "month"}
    ],
    "inventory": [
      {"item": "Salvage haul", "qty": 1, "value": 8000, "location": "cargo-hold"}
    ],
    "assets": [
      {"name": "The Still Here", "type": "ship", "value": 180000}
    ]
  },

  "relationships": [
    {
      "type": "ally",
      "target": "fence-marcus",
      "state": {"trust": "moderate", "terms": "70/30 split"},
      "notes": "Regular buyer for salvage"
    }
  ]
}
```

### Ship Scale: Military Vessel (~50 named, ~1,200 abstracted)

**Example: INS Leviathan**

Military vessel with departments as subfactions.

```json
{
  "id": "ins-leviathan",
  "name": "INS Leviathan",
  "type": "military",
  "parent": "imperial-navy",
  "tags": ["warship", "carrier", "imperial"],

  "minimal": {
    "essence": "Venator-class carrier. 1,200 souls. Pride of the 7th Fleet. Captain Vance runs tight but fair. Crew loyal to ship more than Empire.",
    "symbol": "Imperial Navy crest with ship designation",
    "motto": "Through fire, we endure",
    "current_status": "Patrol duty, sector seven"
  },

  "hierarchy": {
    "subfactions": [
      {
        "id": "leviathan-bridge",
        "name": "Bridge Officers",
        "autonomy": false,
        "role": "Command and navigation"
      },
      {
        "id": "leviathan-engineering",
        "name": "Engineering Division",
        "autonomy": true,
        "role": "Propulsion and maintenance"
      },
      {
        "id": "leviathan-marines",
        "name": "Marine Detachment",
        "autonomy": true,
        "role": "Security and boarding operations"
      }
    ]
  },

  "members": {
    "named": ["captain-vance", "commander-reis", "chief-engineer-yuki"],
    "units": [
      {
        "name": "Marine Platoon Alpha",
        "count": 50,
        "morale": "high",
        "role": "Boarding operations",
        "linked_members": ["sergeant-major-cole"]
      },
      {
        "name": "Fighter Squadron",
        "count": 24,
        "morale": "stable",
        "role": "Fighter operations",
        "linked_members": ["squadron-leader-kira"]
      }
    ],
    "pools": [
      {"label": "1,200 crew", "state": "stable"},
      {"label": "~200 support staff", "state": "stable"}
    ]
  },

  "relationships": [
    {
      "type": "reports_to",
      "target": "seventh-fleet-command",
      "state": {"via": "sector-command"},
      "notes": "Standard chain of command"
    }
  ],

  "resources": {
    "ammunition": 85,
    "fuel": 70,
    "supplies": 60,
    "fighter_readiness": 22
  }
}
```

### Vast Scale: Noble House (key figures only)

**Example: House Verdania**

Large organization with minimal tracking, subfactions may oppose each other.

```json
{
  "id": "house-verdania",
  "name": "House Verdania",
  "type": "house",
  "tags": ["noble", "merchant", "political"],

  "minimal": {
    "essence": "Ancient trading house spanning twelve systems. Wealth built on commerce, maintained by marriage and murder. Three heirs, two factions, one throne.",
    "symbol": "Green serpent coiled around golden scales",
    "motto": "Fair dealing, final payment",
    "current_status": "Succession crisis brewing"
  },

  "full": {
    "history": "Founded during the Expansion. Survived three empires. Current generation may tear it apart.",
    "values": "Profit, legacy, family name (in that order)",
    "structure": "Feudal with corporate overlay. Branch families control regions.",
    "territories": "Core holdings in Verdania system, trade posts across sector"
  },

  "hierarchy": {
    "subfactions": [
      {
        "id": "verdania-firstborn",
        "name": "Firstborn Faction",
        "autonomy": true,
        "role": "Traditional heir's supporters"
      },
      {
        "id": "verdania-reformists",
        "name": "Reformist Faction",
        "autonomy": true,
        "role": "Younger heirs seeking change"
      },
      {
        "id": "verdania-merchants",
        "name": "Merchant Arm",
        "autonomy": true,
        "role": "Trade operations"
      }
    ]
  },

  "members": {
    "named": ["lord-verdania", "heir-marcus", "heir-lydia", "spymaster-chen"],
    "units": [],
    "pools": [
      {"label": "~500 household staff", "state": "loyal"},
      {"label": "~2,000 trade employees", "state": "stable"}
    ]
  },

  "relationships": [
    {
      "type": "rival",
      "target": "house-corvain",
      "state": {"tension": "high", "domain": "shipping routes"},
      "notes": "Three generations of competition"
    },
    {
      "type": "patron",
      "target": "guild-of-factors",
      "state": {"protection": "financial backing", "expectations": "favorable rates"},
      "notes": "Long-standing sponsorship"
    }
  ],

  "economy": {
    "accounts": [
      {"category": "liquid", "balance": 2000000, "notes": "House treasury"},
      {"category": "invested", "balance": 15000000, "notes": "Trade ventures"}
    ],
    "assets": [
      {"name": "Verdania Tower", "type": "property", "value": 5000000},
      {"name": "Trade Fleet", "type": "ships", "value": 8000000, "notes": "47 vessels"}
    ]
  }
}
```

## Bidirectional Sync

Faction membership is tracked bidirectionally:

1. **Faction knows members**: `members.named` lists character IDs
2. **Characters point to faction**: `faction` field in character JSON

Keep both in sync:

```json
// In faction file
"members": {
  "named": ["juno", "tam"]
}

// In character file
{
  "id": "juno",
  "faction": "delacroix-fleet",
  "subfaction": null
}
```

## Changelog Integration

All faction updates are logged to the campaign changelog:

- Member additions/removals
- Relationship changes
- Economy updates
- Resource changes
- Status updates

Use the campaign tools for updates to maintain audit trail.

## Anti-Patterns - AVOID These

- **Exhaustive history for minor factions** - evocative > exhaustive
- **All members as named** - use units and pools for scale
- **Missing relationship types** - be specific about edge type
- **Economy tracking for non-economic factions** - only track what matters
- **Tracking individual credits for vast organizations** - use abstraction
- **Forgetting bidirectional sync** - keep character and faction files aligned
- **Subfactions without parent references** - breaks hierarchy
- **Resources without meaning** - only track values you'll use in play

## Workflow

### Step 1: Determine Scale

Before creating a faction, decide its scale:

- **Tight** (< 50 members): Name everyone, full economic detail
- **Ship** (50-2000): Key figures named, departments as subfactions, pools for masses
- **Vast** (2000+): Leadership only, subfactions may be semi-independent

### Step 2: Create Minimal Profile

Start with identity:

```json
{
  "id": "faction-id",
  "name": "Display Name",
  "type": "appropriate-type",
  "minimal": {
    "essence": "35 words capturing core identity",
    "symbol": "Visual identifier",
    "motto": "Their creed",
    "current_status": "Current state"
  }
}
```

### Step 3: Add Structure

Define hierarchy if needed:

- Parent faction reference
- Subfactions with autonomy settings
- Member tiers (named, units, pools)

### Step 4: Define Relationships

Add first-class relationship edges:

- Type each relationship explicitly
- Include relevant state fields
- Allow for freeform extension

### Step 5: Track Economy (If Relevant)

Only for factions where resources matter to play:

- Accounts for money tracking
- Running costs for ongoing expenses
- Inventory for tracked goods
- Assets for major holdings

### Step 6: Create Character Cross-References

For named members:

- Add character ID to faction's `members.named`
- Set `faction` field in character JSON
- Optionally set `subfaction` if applicable

### Step 7: Save File

Save to `factions/{id}.json`
