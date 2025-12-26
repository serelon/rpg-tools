#!/usr/bin/env python3
"""Story collection tool for solo RPG games. Manages character story collections."""

import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

from lib import parse_era, discover_data, find_item, save_item


# Story collections storage
story_collections: Dict[str, Dict] = {}


def discover_stories(repo_root: Path) -> None:
    """Discover story collections from campaign folders and user uploads."""
    global story_collections
    story_collections = discover_data(
        "stories",
        repo_root,
        loose_pattern="*-stories.json"
    )


def get_collection(campaign: str) -> Optional[Dict]:
    """Get aggregated story collection for a campaign (merges all matching files)."""
    matching_collections = []
    matching_stories = []
    campaign_lower = campaign.lower()

    for coll_id, coll in story_collections.items():
        coll_campaign = coll.get("campaign", "").lower()
        # Match by campaign field or collection id
        if (coll_campaign == campaign_lower or
            campaign_lower in coll_campaign or
            campaign_lower in coll_id.lower()):
            # Check if this is a story (has title) vs collection (has stories array)
            if "title" in coll and "stories" not in coll:
                # This is a flat-array story, add directly
                matching_stories.append(coll)
            else:
                # This is a collection wrapper
                matching_collections.append(coll)

    if not matching_collections and not matching_stories:
        return None

    # Aggregate: merge all stories from matching files
    aggregated = {
        "id": f"{campaign}-stories",
        "character": matching_collections[0].get("character") if matching_collections else None,
        "campaign": campaign,
        "collections": {},
        "stories": []
    }

    # Add stories from collection wrappers
    for coll in matching_collections:
        aggregated["collections"].update(coll.get("collections", {}))
        aggregated["stories"].extend(coll.get("stories", []))

    # Add flat-array stories directly
    aggregated["stories"].extend(matching_stories)

    return aggregated


def filter_stories(
    stories: List[Dict],
    collection: Optional[str] = None,
    theme: Optional[str] = None,
    mood: Optional[str] = None,
    era: Optional[str] = None,
    before_era: Optional[str] = None
) -> List[Dict]:
    """Filter stories by criteria."""
    result = stories

    if collection:
        result = [s for s in result if s.get("collection") == collection]

    if theme:
        theme_lower = theme.lower()
        result = [s for s in result if any(theme_lower in t.lower() for t in s.get("themes", []))]

    if mood:
        mood_lower = mood.lower()
        result = [s for s in result if mood_lower in s.get("mood", "").lower()]

    if era:
        era_lower = era.lower()
        result = [s for s in result if era_lower in s.get("era", "").lower()]

    if before_era:
        target = parse_era(before_era)
        result = [s for s in result if parse_era(s.get("era", "")) <= target]

    return result


def cmd_meta(campaign: str) -> None:
    """Show available metadata with counts."""
    coll = get_collection(campaign)
    if not coll:
        print(f"Error: No story collection found for campaign '{campaign}'", file=sys.stderr)
        sys.exit(1)

    stories = coll.get("stories", [])
    if not stories:
        print("No stories found")
        return

    # Count themes
    themes: Dict[str, int] = {}
    for s in stories:
        for t in s.get("themes", []):
            themes[t] = themes.get(t, 0) + 1

    # Count moods
    moods: Dict[str, int] = {}
    for s in stories:
        m = s.get("mood", "unknown")
        moods[m] = moods.get(m, 0) + 1

    # Count collections
    collections: Dict[str, int] = {}
    for s in stories:
        c = s.get("collection", "unknown")
        collections[c] = collections.get(c, 0) + 1

    # Count eras
    eras: Dict[str, int] = {}
    for s in stories:
        e = s.get("era", "unknown")
        eras[e] = eras.get(e, 0) + 1

    # Count source files
    sources: Dict[str, int] = {}
    for s in stories:
        src = s.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1

    # Print results
    print(f"\n## Collections")
    for k, v in sorted(collections.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n## Eras")
    for k, v in sorted(eras.items(), key=lambda x: parse_era(x[0])):
        print(f"  {k}: {v}")

    print(f"\n## Moods")
    for k, v in sorted(moods.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n## Themes")
    for k, v in sorted(themes.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n## Sources")
    for k, v in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n**Total: {len(stories)} stories**")


def cmd_list(
    campaign: str,
    collection: Optional[str] = None,
    theme: Optional[str] = None,
    mood: Optional[str] = None,
    era: Optional[str] = None
) -> None:
    """List all stories in a collection."""
    coll = get_collection(campaign)
    if not coll:
        print(f"Error: No story collection found for campaign '{campaign}'", file=sys.stderr)
        print(f"Available: {', '.join(story_collections.keys())}", file=sys.stderr)
        sys.exit(1)

    stories = filter_stories(
        coll.get("stories", []),
        collection=collection,
        theme=theme,
        mood=mood,
        era=era
    )

    if not stories:
        print("No stories found matching criteria")
        return

    # Print header
    print(f"\n{'Title':<40} {'Era':<15} {'Collection':<15}")
    print("-" * 70)

    # Sort by era
    stories_sorted = sorted(stories, key=lambda s: parse_era(s.get("era", "")))

    for story in stories_sorted:
        title = story.get("title", "Untitled")[:38]
        era = story.get("era", "Unknown")[:13]
        coll_name = story.get("collection", "")[:13]
        print(f"{title:<40} {era:<15} {coll_name:<15}")

    print(f"\nTotal: {len(stories)} stories")


def cmd_random(
    campaign: str,
    collection: Optional[str] = None,
    theme: Optional[str] = None,
    mood: Optional[str] = None,
    era: Optional[str] = None
) -> None:
    """Get a random story."""
    coll = get_collection(campaign)
    if not coll:
        print(f"Error: No story collection found for campaign '{campaign}'", file=sys.stderr)
        sys.exit(1)

    stories = filter_stories(
        coll.get("stories", []),
        collection=collection,
        theme=theme,
        mood=mood,
        era=era
    )

    if not stories:
        print("No stories found matching criteria", file=sys.stderr)
        sys.exit(1)

    story = random.choice(stories)
    print(f"# {story.get('title', 'Untitled')}\n")
    print(story.get("text", ""))


def find_story(stories: List, story_id: str) -> Optional[Dict]:
    """Find a story by ID or title in a list of stories."""
    story_id_lower = story_id.lower()
    for story in stories:
        if (story.get("id", "").lower() == story_id_lower or
            story.get("title", "").lower() == story_id_lower):
            return story
    return None


def cmd_get(campaign: str, story_id: str) -> None:
    """Get a specific story by ID or title."""
    coll = get_collection(campaign)
    if not coll:
        print(f"Error: No story collection found for campaign '{campaign}'", file=sys.stderr)
        sys.exit(1)

    story = find_story(coll.get("stories", []), story_id)
    if not story:
        print(f"Error: Story '{story_id}' not found", file=sys.stderr)
        sys.exit(1)

    print(f"# {story.get('title', 'Untitled')}\n")
    print(story.get("text", ""))


def cmd_show(campaign: str, story_id: str) -> None:
    """Show full story details with metadata."""
    coll = get_collection(campaign)
    if not coll:
        print(f"Error: No story collection found for campaign '{campaign}'", file=sys.stderr)
        sys.exit(1)

    story = find_story(coll.get("stories", []), story_id)
    if not story:
        print(f"Error: Story '{story_id}' not found", file=sys.stderr)
        sys.exit(1)

    print(f"# {story.get('title', 'Untitled')}")
    print(f"\n**ID:** {story.get('id', 'N/A')}")
    print(f"**Era:** {story.get('era', 'Unknown')}")
    print(f"**Collection:** {story.get('collection', 'N/A')}")
    print(f"**Source:** {story.get('source', 'Unknown')}")
    print(f"**Themes:** {', '.join(story.get('themes', []))}")
    print(f"**Mood:** {story.get('mood', 'N/A')}")
    if story.get("characters"):
        print(f"**Characters:** {', '.join(story.get('characters', []))}")
    if story.get("related"):
        print(f"**Related:** {', '.join(story.get('related', []))}")
    print(f"\n---\n")
    print(story.get("text", ""))


def generate_story_id() -> str:
    """Generate next story ID."""
    max_num = 0
    for coll in story_collections.values():
        for story in coll.get("stories", []):
            story_id = story.get("id", "")
            if story_id.startswith("story-"):
                try:
                    num = int(story_id[6:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
    return f"story-{max_num + 1:05d}"


def cmd_create(
    story_id: Optional[str],
    title: str,
    text: str,
    campaign: str,
    collection_type: Optional[str] = None,
    teller: Optional[str] = None,
    themes: Optional[str] = None,
    characters: Optional[str] = None,
    locations: Optional[str] = None,
    era: Optional[str] = None,
    mood: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Create a new story."""
    search_root = Path.cwd()

    # Generate ID if not provided
    if not story_id:
        story_id = generate_story_id()

    # Check if ID already exists
    all_story_ids = {s.get("id") for c in story_collections.values() for s in c.get("stories", [])}
    if story_id in all_story_ids:
        print(f"Error: Story '{story_id}' already exists", file=sys.stderr)
        sys.exit(1)

    # Build story dict
    story = {
        "id": story_id,
        "title": title,
        "text": text,
        "campaign": campaign,
    }

    if collection_type:
        story["collection"] = collection_type
    if teller:
        story["teller"] = teller
    if era:
        story["era"] = era
    if mood:
        story["mood"] = mood
    if themes:
        story["themes"] = [t.strip() for t in themes.split(',')]
    if characters:
        story["characters"] = [c.strip() for c in characters.split(',')]
    if locations:
        story["locations"] = [l.strip() for l in locations.split(',')]

    # Save as individual story file
    path = save_item("stories", story, search_root)

    if output_json:
        print(json.dumps(story, indent=2))
    else:
        print(f"Created story: {story_id}")
        print(f"  Title: {title}")
        print(f"  Campaign: {campaign}")
        if collection_type:
            print(f"  Collection: {collection_type}")
        print(f"  Saved to: {path}")


def main():
    # Find repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Load story collections
    discover_stories(repo_root)

    # Parse command line
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print("Usage: python stories.py <command> [options]")
        print("\nCommands:")
        print("  create [id] --title T --text T --campaign C ...")
        print("                                           Create a new story")
        print("  meta --campaign NAME                     Show available tags/metadata with counts")
        print("  list --campaign NAME [filters...]        List stories")
        print("  random --campaign NAME [filters...]      Get random story")
        print("  get --campaign NAME --story ID           Get specific story text")
        print("  show --campaign NAME --story ID          Show story with metadata")
        print("\nCreate options:")
        print("  --title TITLE        Story title (required)")
        print("  --text TEXT          Story text (required)")
        print("  --campaign NAME      Campaign identifier (required)")
        print("  --collection COLL    Collection type (told, untold, historical, etc.)")
        print("  --teller ID          Character ID of storyteller")
        print("  --themes THEMES      Comma-separated themes")
        print("  --characters CHARS   Comma-separated character IDs")
        print("  --locations LOCS     Comma-separated location IDs")
        print("  --era ERA            Time period")
        print("  --mood MOOD          Story mood")
        print("  --json               Output as JSON")
        print("\nFilters (for list/random):")
        print("  --collection COLL    Filter by collection (told/private)")
        print("  --theme TAG          Filter by theme")
        print("  --mood MOOD          Filter by mood")
        print("  --era ERA            Filter by era (partial match)")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h') else 1)

    command = sys.argv[1]

    # Parse options
    campaign = None
    collection = None
    theme = None
    mood = None
    era = None
    story_id = None
    title = None
    text = None
    teller = None
    themes_list = None
    characters_list = None
    locations_list = None
    output_json = False

    i = 2
    # Handle positional id for create command
    if command == "create" and i < len(sys.argv) and not sys.argv[i].startswith("--"):
        story_id = sys.argv[i]
        i += 1
    while i < len(sys.argv):
        if sys.argv[i] == "--campaign" and i + 1 < len(sys.argv):
            campaign = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--collection" and i + 1 < len(sys.argv):
            collection = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--theme" and i + 1 < len(sys.argv):
            theme = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--mood" and i + 1 < len(sys.argv):
            mood = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--era" and i + 1 < len(sys.argv):
            era = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--story" and i + 1 < len(sys.argv):
            story_id = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--title" and i + 1 < len(sys.argv):
            title = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--text" and i + 1 < len(sys.argv):
            text = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--teller" and i + 1 < len(sys.argv):
            teller = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--themes" and i + 1 < len(sys.argv):
            themes_list = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--characters" and i + 1 < len(sys.argv):
            characters_list = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--locations" and i + 1 < len(sys.argv):
            locations_list = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--json":
            output_json = True
            i += 1
        else:
            print(f"Unknown option: {sys.argv[i]}", file=sys.stderr)
            sys.exit(1)

    # Validate campaign
    if not campaign:
        print("Error: --campaign is required", file=sys.stderr)
        sys.exit(1)

    # Execute command
    if command == "meta":
        cmd_meta(campaign)
    elif command == "list":
        cmd_list(campaign, collection, theme, mood, era)
    elif command == "random":
        cmd_random(campaign, collection, theme, mood, era)
    elif command == "get":
        if not story_id:
            print("Error: --story is required for 'get' command", file=sys.stderr)
            sys.exit(1)
        cmd_get(campaign, story_id)
    elif command == "show":
        if not story_id:
            print("Error: --story is required for 'show' command", file=sys.stderr)
            sys.exit(1)
        cmd_show(campaign, story_id)
    elif command == "create":
        if not title:
            print("Error: --title is required for 'create' command", file=sys.stderr)
            sys.exit(1)
        if not text:
            print("Error: --text is required for 'create' command", file=sys.stderr)
            sys.exit(1)
        cmd_create(
            story_id, title, text, campaign,
            collection_type=collection,
            teller=teller,
            themes=themes_list,
            characters=characters_list,
            locations=locations_list,
            era=era,
            mood=mood,
            output_json=output_json
        )
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
