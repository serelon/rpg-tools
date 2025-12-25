"""Changelog utilities for tracking state changes with audit trail."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class ChangeEntry:
    """A single state change with audit information."""
    id: str
    session: str
    branch: Optional[str]
    timeline: Optional[str]
    character: str
    tier: str  # "development" or "state"
    field: str
    from_value: Any
    to_value: Any
    reason: str
    linked_log: Optional[str] = None
    created: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Rename from_value/to_value to from/to for cleaner JSON
        d["from"] = d.pop("from_value")
        d["to"] = d.pop("to_value")
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChangeEntry':
        """Create from dictionary."""
        # Handle from/to naming
        if "from" in data:
            data["from_value"] = data.pop("from")
        if "to" in data:
            data["to_value"] = data.pop("to")
        return cls(**data)


class Changelog:
    """Manages changelog entries with persistence."""

    def __init__(self, changelog_path: Path):
        self.path = changelog_path
        self.entries: List[ChangeEntry] = []
        self._load()

    def _load(self) -> None:
        """Load changelog from disk."""
        if self.path.exists():
            try:
                with open(self.path, encoding='utf-8') as f:
                    data = json.load(f)
                    self.entries = [ChangeEntry.from_dict(e) for e in data]
            except Exception:
                self.entries = []

    def _save(self) -> None:
        """Save changelog to disk."""
        self.path.parent.mkdir(exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump([e.to_dict() for e in self.entries], f, indent=2)

    def _generate_id(self) -> str:
        """Generate next change ID."""
        max_num = 0
        for entry in self.entries:
            if entry.id.startswith("change-"):
                try:
                    num = int(entry.id[7:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        return f"change-{max_num + 1:05d}"

    def add(
        self,
        session: str,
        character: str,
        tier: str,
        field: str,
        from_value: Any,
        to_value: Any,
        reason: str,
        branch: Optional[str] = None,
        timeline: Optional[str] = None,
        linked_log: Optional[str] = None
    ) -> ChangeEntry:
        """Add a new changelog entry."""
        entry = ChangeEntry(
            id=self._generate_id(),
            session=session,
            branch=branch,
            timeline=timeline,
            character=character,
            tier=tier,
            field=field,
            from_value=from_value,
            to_value=to_value,
            reason=reason,
            linked_log=linked_log
        )
        self.entries.append(entry)
        self._save()
        return entry

    def get_for_character(self, character_id: str) -> List[ChangeEntry]:
        """Get all changes for a character."""
        char_lower = character_id.lower()
        return [e for e in self.entries if e.character.lower() == char_lower]

    def get_for_session(self, session: str) -> List[ChangeEntry]:
        """Get all changes from a session."""
        session_lower = session.lower()
        return [e for e in self.entries if e.session.lower() == session_lower]

    def get_for_field(self, field_pattern: str) -> List[ChangeEntry]:
        """Get all changes matching a field pattern."""
        pattern_lower = field_pattern.lower()
        return [e for e in self.entries if pattern_lower in e.field.lower()]

    def get_by_tier(self, tier: str) -> List[ChangeEntry]:
        """Get all changes of a specific tier."""
        tier_lower = tier.lower()
        return [e for e in self.entries if e.tier.lower() == tier_lower]


def load_changelog(search_root: Path) -> Changelog:
    """Load changelog from standard location."""
    changelog_path = search_root / "campaign" / "changelog.json"
    return Changelog(changelog_path)
