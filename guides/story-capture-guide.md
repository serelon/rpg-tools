# Capturing Stories

After sessions, extract stories told or learned into the story collection.

## File Structure

**Location:** `stories/session-NN-stories.json`

```json
{
  "id": "session-01-stories",
  "character": "CharacterName",
  "campaign": "campaign-id",
  "collections": {
    "told": {
      "name": "Stories Told",
      "description": "Tales shared with others"
    },
    "learned": {
      "name": "Stories Learned",
      "description": "Tales heard from others"
    },
    "private": {
      "name": "Private Memories",
      "description": "Kept close, rarely spoken"
    }
  },
  "stories": []
}
```

## Story Entry Format

```json
{
  "id": "short-kebab-case-id",
  "title": "The Story Title",
  "collection": "told",
  "era": "~15000 BCE",
  "source": "How learned/created",
  "themes": ["theme1", "theme2"],
  "characters": [],
  "mood": "bittersweet",
  "related": [],
  "text": "Full story text.\n\nUse \\n for paragraph breaks."
}
```

## Field Guide

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique identifier, kebab-case |
| title | Yes | Display title |
| collection | Yes | "told", "learned", or "private" |
| era | Yes | When learned (e.g., "~15000 BCE") |
| source | Yes | "Learned from [person]", "Witnessed firsthand", "Created for [person]" |
| themes | Yes | 2-4 tags: love, loss, courage, wisdom, mortality, hope, warning |
| characters | No | Named people in the story ([] if none) |
| mood | Yes | Single word: tender, bittersweet, tense, hopeful, somber |
| related | No | IDs of connected stories ([] if none) |
| text | Yes | Full story text |

## Workflow

When asked to capture stories from a session:
1. Identify stories told/heard (not just narrative, but actual in-character stories)
2. Extract the story text verbatim
3. Add metadata (who told it, themes, mood)
4. Save to `stories/session-NN-stories.json`
