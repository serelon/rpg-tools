# Creating Namesets

When a new culture, era, or group needs names, create a nameset JSON file.

## Default Structure

- 200 male first names
- 200 female first names
- 100 unisex first names
- 200 last names

**However**, think critically about whether this fits the setting:
- Prehistoric cultures may not have "last names" - use epithets or clan markers instead
- Some cultures use patronymics rather than family names
- Fantasy races might have completely different naming conventions

## Output Format

Save to `namesets/[theme-id].json`:

```json
{
  "id": "theme-id",
  "name": "Theme Display Name",
  "description": "Explain the theme and any structural decisions",
  "setting": "Campaign or setting name",
  "tags": ["relevant", "tags"],
  "nameCategories": {
    "firstName": [
      {"name": "Example", "gender": "male"},
      {"name": "Example", "gender": "female"},
      {"name": "Example", "gender": "unisex"}
    ],
    "lastName": [
      {"name": "Example"}
    ]
  },
  "format": "{firstName} {lastName}"
}
```

Adjust `nameCategories` based on what makes sense (e.g., `epithet`, `clanName`, `parentage` instead of `lastName`).

## Guidelines

1. **Authenticity over fantasy**: Names should feel plausible for their cultural/historical context
2. **Variety**: Diverse sounds, lengths, and styles within each category
3. **Usability**: Pronounceable and memorable for RPG use
4. **Think first**: Consider what naming conventions would actually exist in this culture
