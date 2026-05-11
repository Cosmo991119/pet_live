#!/usr/bin/env bash
set -u

roots=()

if [[ -n "${CODEX_HOME:-}" ]]; then
  roots+=("$CODEX_HOME/skills")
fi

roots+=("$HOME/.agents/skills")
roots+=("$HOME/.codex/skills")

if [[ -d ".agents/skills" ]]; then
  roots+=("$(pwd)/.agents/skills")
fi

find_skill() {
  local name="$1"
  local root
  for root in "${roots[@]}"; do
    if [[ -f "$root/$name/SKILL.md" ]]; then
      printf '%s\n' "$root/$name/SKILL.md"
      return 0
    fi
  done
  return 1
}

check() {
  local name="$1"
  local found
  if found="$(find_skill "$name")"; then
    printf 'OK      %s -> %s\n' "$name" "$found"
  else
    printf 'MISSING %s\n' "$name"
  fi
}

echo "Checking companion skills..."
check "tdd"
check "diagnose"
check "code-reviewer"

cat <<'EOF'

Install guidance:
- code-reviewer:
  npx skills add https://github.com/google-gemini/gemini-cli --skill code-reviewer -g -y
- tdd / diagnose:
  Install equivalent trusted skills if available, or use the fallback workflows
  built into disciplined-dev-workflow.

Restart the agent after installing new skills.
EOF
