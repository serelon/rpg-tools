#!/usr/bin/env python3
"""Bundle rpg-tools into a skill package for Claude Desktop."""

import zipfile
from pathlib import Path

# Files to include in the skill package
INCLUDE_FILES = [
    'SKILL.md',
    'scripts/dice.py',
    'scripts/tarot.py',
    'scripts/namegen.py',
    'scripts/stories.py',
    'scripts/characters.py',
    'scripts/locations.py',
    'scripts/memories.py',
    'scripts/oracle.py',
]

# Directories to include
INCLUDE_DIRS = [
    ('guides', '*.md'),
    ('modifiers', '*.md'),
    ('scripts/lib', '*.py'),
]


def bundle(repo_path: Path, output_path: Path):
    """Create skill zip package."""
    file_count = 0

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add specific files
        for rel_path in INCLUDE_FILES:
            src = repo_path / rel_path
            if src.exists():
                arcname = f'rpg-tools/{rel_path}'
                zf.write(src, arcname)
                file_count += 1
            else:
                print(f"Warning: {rel_path} not found")

        # Add directory contents
        for dir_name, pattern in INCLUDE_DIRS:
            dir_path = repo_path / dir_name
            if dir_path.exists():
                for path in dir_path.glob(pattern):
                    if path.is_file():
                        arcname = f'rpg-tools/{dir_name}/{path.name}'
                        zf.write(path, arcname)
                        file_count += 1

    size_kb = output_path.stat().st_size / 1024
    print(f"Bundled {file_count} files -> {output_path.name} ({size_kb:.1f} KB)")

    # List contents
    print("\nContents:")
    with zipfile.ZipFile(output_path, 'r') as zf:
        for name in sorted(zf.namelist()):
            info = zf.getinfo(name)
            print(f"  {name} ({info.file_size} bytes)")


def main():
    repo_path = Path(__file__).parent
    output_path = repo_path / "rpg-tools.skill"
    bundle(repo_path, output_path)


if __name__ == "__main__":
    main()
