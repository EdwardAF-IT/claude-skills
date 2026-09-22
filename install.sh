#!/usr/bin/env bash
# Install or update Claude Code plus Edward's custom skills on a Mac or Linux box.
#
#   curl -fsSL https://raw.githubusercontent.com/EdwardAF-IT/claude-skills/main/install.sh | bash
#
# Installs what is missing (git, Node, Python, Graphviz via Homebrew or apt; Claude Code,
# mermaid-cli, highlight.js via npm), then copies the skills into ~/.claude/skills. Safe to
# run again: it updates the skills and leaves everything else under ~/.claude alone.
set -euo pipefail

REPO="${REPO:-EdwardAF-IT/claude-skills}"
STAGE="${HOME}/.local/share/claude-skills"
DEST="${HOME}/.claude/skills"

say() { printf '  %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

pkg() {  # pkg <command> <brew-name> <apt-name> <label>
  if have "$1"; then say "$4 present"; return; fi
  say "installing $4 ..."
  if have brew; then brew install "$2" >/dev/null
  elif have apt-get; then sudo apt-get install -y "$3" >/dev/null
  else echo "cannot install $4: no brew or apt-get"; exit 1
  fi
}

echo; echo "Claude Code + skills installer"; echo
pkg git    git      git      git
pkg node   node     nodejs   Node.js
pkg python3 python  python3  Python
pkg dot    graphviz graphviz Graphviz
have claude || { say "installing Claude Code ..."; npm install -g @anthropic-ai/claude-code >/dev/null; }
have mmdc   || { say "installing mermaid-cli ..."; npm install -g @mermaid-js/mermaid-cli >/dev/null; }
[ -d "$(npm root -g)/highlight.js" ] || { say "installing highlight.js ..."; npm install -g highlight.js >/dev/null; }

if [ -d "$STAGE/.git" ]; then say "updating skills ..."; git -C "$STAGE" pull --quiet --ff-only
else say "fetching skills ..."; git clone --quiet --depth 1 "https://github.com/${REPO}.git" "$STAGE"
fi

mkdir -p "$DEST"
n=0
for d in "$STAGE"/skills/*/; do
  name="$(basename "$d")"
  rm -rf "${DEST:?}/${name}"          # mirror one skill at a time; others in ~/.claude/skills stay
  cp -R "$d" "$DEST/$name"
  n=$((n + 1))
done
echo; say "$n skills in $DEST"
[ -f "$HOME/.claude/.credentials.json" ] || say 'next: run "claude" and sign in when it asks'
echo
