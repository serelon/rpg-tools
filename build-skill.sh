#!/bin/bash
# Build rpg-tools.skill from repo sources
#
# Usage: ./build-skill.sh [output-path]
# Default output: ./rpg-tools.skill

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
OUTPUT="${1:-$SCRIPT_DIR/rpg-tools.skill}"

# Create temp directory for skill structure
TEMP_DIR=$(mktemp -d)
SKILL_DIR="$TEMP_DIR/rpg-tools"
mkdir -p "$SKILL_DIR/scripts"
mkdir -p "$SKILL_DIR/guides"
mkdir -p "$SKILL_DIR/modifiers"

# Copy SKILL.md
cp "$REPO_ROOT/SKILL.md" "$SKILL_DIR/"

# Copy tool scripts
cp "$REPO_ROOT/scripts/dice.py" "$SKILL_DIR/scripts/"
cp "$REPO_ROOT/scripts/tarot.py" "$SKILL_DIR/scripts/"
cp "$REPO_ROOT/scripts/namegen.py" "$SKILL_DIR/scripts/"
cp "$REPO_ROOT/scripts/stories.py" "$SKILL_DIR/scripts/"
cp "$REPO_ROOT/scripts/characters.py" "$SKILL_DIR/scripts/"
cp "$REPO_ROOT/scripts/locations.py" "$SKILL_DIR/scripts/"
cp "$REPO_ROOT/scripts/memories.py" "$SKILL_DIR/scripts/"
cp "$REPO_ROOT/scripts/oracle.py" "$SKILL_DIR/scripts/"

# Copy guides
cp "$REPO_ROOT/guides/"*.md "$SKILL_DIR/guides/"

# Copy modifiers
cp "$REPO_ROOT/modifiers/"*.md "$SKILL_DIR/modifiers/"

# Build the skill archive
cd "$TEMP_DIR"
rm -f "$OUTPUT"
zip -r "$OUTPUT" rpg-tools

# Cleanup
rm -rf "$TEMP_DIR"

echo "Built: $OUTPUT"
echo "Contents:"
unzip -l "$OUTPUT"
