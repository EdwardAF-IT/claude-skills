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
MANIFEST="${DEST}/.claude-skills-manifest"

say() { printf '  %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# Put $1 on PATH for this run and persist it for future shells, without repeating it.
add_user_path() {
  case ":$PATH:" in
    *":$1:"*) ;;
    *) export PATH="$1:$PATH" ;;
  esac
  local rc
  for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [ -f "$rc" ] || continue
    grep -qF "$1" "$rc" 2>/dev/null || printf '\nexport PATH="%s:$PATH"\n' "$1" >> "$rc"
  done
}

apt_updated=0
apt_install() {
  if [ "$apt_updated" -eq 0 ]; then sudo apt-get update -qq; apt_updated=1; fi
  sudo apt-get install -y "$@" >/dev/null
}

no_pkg_manager() {  # no_pkg_manager <label> — no brew, no apt-get
  echo "cannot install $1: no brew or apt-get" >&2
  echo "  install Homebrew first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"" >&2
  exit 1
}

pkg() {  # pkg <command> <brew-name> <apt-name> <label>
  if have "$1"; then say "$4 present"; return; fi
  say "installing $4 ..."
  if have brew; then brew install "$2" >/dev/null
  elif have apt-get; then apt_install "$3"
  else no_pkg_manager "$4"
  fi
}

ensure_node() {  # Debian/Ubuntu only suggests npm alongside nodejs; ask for both explicitly.
  if have node && have npm; then say "Node.js present"; return; fi
  say "installing Node.js ..."
  if have brew; then brew install node >/dev/null
  elif have apt-get; then apt_install nodejs npm
  else no_pkg_manager "Node.js"
  fi
}

ensure_python_alias() {  # the skills run `python`; neither macOS nor Ubuntu ships that name
  have python && return
  say "linking python -> python3 ..."
  if have apt-get; then apt_install python-is-python3
  else
    mkdir -p "$HOME/.local/bin"
    ln -sf "$(command -v python3)" "$HOME/.local/bin/python"
    add_user_path "$HOME/.local/bin"
    say "python -> $(command -v python3), via ~/.local/bin on PATH"
  fi
}

ensure_npm_user_prefix() {  # avoid a root-owned global prefix so `npm install -g` needs no sudo
  local want="${HOME}/.npm-global"
  if [ "$(npm config get prefix 2>/dev/null || true)" != "$want" ]; then
    mkdir -p "$want"
    npm config set prefix "$want"
  fi
  add_user_path "$want/bin"
}

echo; echo "Claude Code + skills installer"; echo
pkg git git git git
ensure_node
pkg python3 python python3 Python
ensure_python_alias
pkg dot graphviz graphviz Graphviz
ensure_npm_user_prefix
have claude || { say "installing Claude Code ..."; npm install -g @anthropic-ai/claude-code >/dev/null; }
have mmdc   || { say "installing mermaid-cli ..."; npm install -g @mermaid-js/mermaid-cli >/dev/null; }
[ -d "$(npm root -g)/highlight.js" ] || { say "installing highlight.js ..."; npm install -g highlight.js >/dev/null; }

if [ -d "$STAGE/.git" ]; then say "updating skills ..."; git -C "$STAGE" pull --quiet --ff-only
else say "fetching skills ..."; git clone --quiet --depth 1 "https://github.com/${REPO}.git" "$STAGE"
fi

mkdir -p "$DEST"

# A manifest of the skill names this installer put in $DEST, so an update can tell "retired
# upstream" apart from "the person made this themselves" — mirroring one folder at a time
# cannot, on its own.
old_manifest=()
if [ -f "$MANIFEST" ]; then
  while IFS= read -r line; do [ -n "$line" ] && old_manifest+=("$line"); done < "$MANIFEST"
fi

n=0
new_manifest=()
for d in "$STAGE"/skills/*/; do
  name="$(basename "$d")"
  rm -rf "${DEST:?}/${name}"          # mirror one skill at a time; others in ~/.claude/skills stay
  cp -R "$d" "$DEST/$name"
  new_manifest+=("$name")
  n=$((n + 1))
done

for old in "${old_manifest[@]:-}"; do
  [ -z "$old" ] && continue
  keep=0
  for cur in "${new_manifest[@]:-}"; do [ "$old" = "$cur" ] && keep=1 && break; done
  if [ "$keep" -eq 0 ] && [ -d "$DEST/$old" ]; then
    rm -rf "${DEST:?}/${old}"
    say "removed $old (retired upstream)"
  fi
done
printf '%s\n' "${new_manifest[@]:-}" | grep -v '^$' > "$MANIFEST" || true

# One-time cleanup: `resume` was renamed to `pickup` before this manifest existed, so the loop
# above has no record of it. Remove only our own copy, identified by its exact description —
# never a skill the person wrote themselves that happens to share the name.
if [ -d "$DEST/resume" ] && [ ! -d "$STAGE/skills/resume" ] \
  && grep -q '^name: resume$' "$DEST/resume/SKILL.md" 2>/dev/null \
  && grep -q 'Pick up a repo where a previous session left it' "$DEST/resume/SKILL.md" 2>/dev/null
then
  rm -rf "$DEST/resume"
  say "removed resume (renamed to pickup)"
fi

echo; say "$n skills in $DEST"
[ -f "$HOME/.claude/.credentials.json" ] || say 'next: run "claude" and sign in when it asks'
echo
