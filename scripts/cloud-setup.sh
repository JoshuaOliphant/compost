#!/usr/bin/env bash
# ABOUTME: Setup script for Claude Code cloud environments: installs compost from its own marketplace, plus the
# ABOUTME: typesafe plugin its skills lean on. Every step is idempotent and only warns on failure.
#
# Usage, as the environment's setup script (works in any project, since it needs no clone):
#   curl -fsSL https://raw.githubusercontent.com/JoshuaOliphant/compost/main/scripts/cloud-setup.sh | bash
# Not `bash scripts/cloud-setup.sh`: sessions start in /home/user, above any clone, so that exits 127.
set -uo pipefail

warn() { echo "cloud-setup: warn: $*" >&2; }

has_marketplace() {
  claude plugin marketplace list 2>/dev/null | grep -qE "^[[:space:]]*>?[[:space:]]*$1\$"
}

has_plugin() {
  claude plugin list 2>/dev/null | grep -qE "^[[:space:]]*>?[[:space:]]*$1\$"
}

# Register a marketplace if missing, refresh it, then update the plugin, installing it if update fails.
ensure_plugin() {
  local marketplace="$1" source="$2" plugin="$3"
  if ! has_marketplace "$marketplace"; then
    claude plugin marketplace add "$source" || { warn "could not add marketplace $source"; return 0; }
  fi
  claude plugin marketplace update "$marketplace" || warn "marketplace update $marketplace failed"
  claude plugin update "$plugin@$marketplace" 2>/dev/null \
    || claude plugin install "$plugin@$marketplace" \
    || warn "could not install $plugin@$marketplace"
}

# compost is also listed in the oliphant-plugins marketplace. An environment that installed it there
# would show every skill twice next to compost@compost, so drop the old id first.
drop_old_compost_id() {
  has_plugin compost@oliphant-plugins || return 0
  claude plugin uninstall compost@oliphant-plugins || warn "could not uninstall compost@oliphant-plugins"
}

if ! command -v claude >/dev/null 2>&1; then
  warn "claude CLI not found; skipping plugin installs"
  exit 0
fi

drop_old_compost_id
ensure_plugin compost JoshuaOliphant/compost compost
# Source per https://docs.typesafe.ai/agent-skill
ensure_plugin typesafe-ai typesafe-ai/skills typesafe
