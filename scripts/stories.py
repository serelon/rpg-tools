#!/usr/bin/env python3
"""Story collection tool for solo RPG games. Manages character story collections."""

import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any


# Story collections storage
story_collections: Dict[str, Dict] = {}


def parse_era(era_str: str) -> int:
    """Parse era string to sortable integer (negative for BCE)."""
    # Strip approximate markers
    era = era_str.strip().lstrip('~').strip()

    # Match patterns like "15000 BCE", "500 CE", "3000 BC"
    match = re.match(r'(\d+)\s*(BCE|BC|CE|AD)?', era, re.IGNORECASE)
    if not match:
        return 0  # Unknown era sorts to middle

    year = int(match.group(1))
    suffix = (match.group(2) or 'CE').upper()

    if suffix in ('BCE', 'BC'):
        return -year
    return year


def discover_stories(repo_root: Path) -> None:
    """Discover story collections from campaign folders and user uploads."""
    global story_collections

    story_paths = []

    # Look in campaigns/*/stories/
    campaigns_dir = repo_root / "campaigns"
    if campaigns_dir.exists():
        for campaign_dir in campaigns_dir.iterdir():
            if campaign_dir.is_dir():
                stories_dir = campaign_dir / "stories"
                if stories_dir.exists():
                    story_paths.extend(stories_dir.glob("*.json"))

    # Look in root stories/ (for bundled usage)
    root_stories = repo_root / "stories"
    if root_stories.exists():
        story_paths.extend(root_stories.glob("*.json"))

    # Look in user uploads (Claude.ai environment)
    uploads_stories = Path("/mnt/user-data/uploads/stories")
    if uploads_stories.exists():
        story_paths.extend(uploads_stories.glob("*.json"))

    # Also check for loose JSON files in uploads root matching story patterns
    uploads_root = Path("/mnt/user-data/uploads")
    if uploads_root.exists():
        story_paths.extend(uploads_root.glob("*-stories.json"))

    # Look in /home/claude/*/stories/ (extracted bundles)
    home_claude = Path("/home/claude")
    if home_claude.exists():
        for subdir in home_claude.iterdir():
            if subdir.is_dir():
                stories_dir = subdir / "stories"
                if stories_dir.exists():
                    story_paths.extend(stories_dir.glob("*.json"))

    # Load all discovered collections
    for path in story_paths:
        try:
            with open(path, encoding='utf-8') as f:
                collection = json.load(f)
                collection_id = collection.get("id", path.stem)
                story_collections[collection_id] = collection
        except Exception as e:
            print(f"Warning: Could not load story collection {path}: {e}", file=sys.stderr)

    if not story_collections:
        print("Warning: No story collections found", file=sys.stderr)


def get_collection(campaign: str) -> Optional[Dict]:
    """Get aggregated story collection for a campaign (merges all matching files)."""
    matching_files = []
    campaign_lower = campaign.lower()

    for coll_id, coll in story_collections.items():
        coll_campaign = coll.get("campaign", "").lower()
        # Match by campaign field or collection id
        if (coll_campaign == campaign_lower or
            campaign_lower in coll_campaign or
            campaign_lower in coll_id.lower()):
            matching_files.append(coll)

    if not matching_files:
        return None

    # Aggregate: merge all stories from matching files
    aggregated = {
        "id": f"{campaign}-stories",
        "character": matching_files[0].get("character"),
        "campaign": campaign,
        "collections": {},
        "stories": []
    }

    for coll in matching_files:
        # Merge collection definitions
        aggregated["collections"].update(coll.get("collections", {}))
        # Merge stories
        aggregated["stories"].extend(coll.get("stories", []))

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


def cmd_get(campaign: str, story_id: str) -> None:
    """Get a specific story by ID or title."""
    coll = get_collection(campaign)
    if not coll:
        print(f"Error: No story collection found for campaign '{campaign}'", file=sys.stderr)
        sys.exit(1)

    story_id_lower = story_id.lower()
    for story in coll.get("stories", []):
        if (story.get("id", "").lower() == story_id_lower or
            story.get("title", "").lower() == story_id_lower):
            print(f"# {story.get('title', 'Untitled')}\n")
            print(story.get("text", ""))
            return

    print(f"Error: Story '{story_id}' not found", file=sys.stderr)
    sys.exit(1)


def cmd_show(campaign: str, story_id: str) -> None:
    """Show full story details with metadata."""
    coll = get_collection(campaign)
    if not coll:
        print(f"Error: No story collection found for campaign '{campaign}'", file=sys.stderr)
        sys.exit(1)

    story_id_lower = story_id.lower()
    for story in coll.get("stories", []):
        if (story.get("id", "").lower() == story_id_lower or
            story.get("title", "").lower() == story_id_lower):
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
            return

    print(f"Error: Story '{story_id}' not found", file=sys.stderr)
    sys.exit(1)


def main():
    # Find repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Load story collections
    discover_stories(repo_root)

    # Parse command line
    if len(sys.argv) < 2:
        print("Usage: python stories.py <command> [options]")
        print("\nCommands:")
        print("  meta --campaign NAME                     Show available tags/metadata with counts")
        print("  list --campaign NAME [filters...]        List stories")
        print("  random --campaign NAME [filters...]      Get random story")
        print("  get --campaign NAME --story ID           Get specific story text")
        print("  show --campaign NAME --story ID          Show story with metadata")
        print("\nFilters (for list/random):")
        print("  --collection COLL    Filter by collection (told/private)")
        print("  --theme TAG          Filter by theme")
        print("  --mood MOOD          Filter by mood")
        print("  --era ERA            Filter by era (partial match)")
        sys.exit(1)

    command = sys.argv[1]

    # Parse options
    campaign = None
    collection = None
    theme = None
    mood = None
    era = None
    story_id = None

    i = 2
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
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
