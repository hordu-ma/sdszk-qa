#!/usr/bin/env sh
set -eu

# Read full hook payload from stdin for pattern-based checks.
payload=""
if [ ! -t 0 ]; then
  payload="$(cat)"
fi

# Gate known dangerous shell patterns with explicit user approval.
if printf '%s' "$payload" | grep -Eiq 'rm[[:space:]]+-rf|git[[:space:]]+reset[[:space:]]+--hard|git[[:space:]]+checkout[[:space:]]+--|sudo[[:space:]]'; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Detected potentially destructive command pattern; require explicit user confirmation."}}'
  exit 0
fi

printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"No high-risk command pattern detected."}}'
