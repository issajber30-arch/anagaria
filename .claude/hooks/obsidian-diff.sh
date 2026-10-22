#!/bin/bash
# PostToolUse (Write|Edit): append each file change in this project, as a diff, to the Obsidian project log.
NOTE="/Users/3isa./Desktop/mywebsite/fort nox/פרויקט - תכנון ארון/יומן שינויים.md"
in=$(cat)
tool=$(jq -r '.tool_name' <<<"$in")
f=$(jq -r '.tool_input.file_path // empty' <<<"$in")
proj=$(jq -r '.cwd // empty' <<<"$in")
case "$f" in "$proj"/*) ;; *) exit 0 ;; esac  # only files inside the project
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
if [ "$tool" = Edit ]; then
  jq -r '.tool_input.old_string' <<<"$in" >"$tmp/a"
  jq -r '.tool_input.new_string' <<<"$in" >"$tmp/b"
  body=$(diff -u --label before --label after "$tmp/a" "$tmp/b" | tail -n +3)
else
  jq -r '.tool_input.content' <<<"$in" >"$tmp/b"
  body="(קובץ נכתב במלואו: $(wc -l <"$tmp/b" | tr -d ' ') שורות)"$'\n'$(head -n 40 "$tmp/b" | sed 's/^/+/')
fi
mkdir -p "$(dirname "$NOTE")"
{
  printf '\n### %s · %s · `%s`\n' "$(date '+%Y-%m-%d %H:%M')" "$tool" "${f#$proj/}"
  printf '~~~~diff\n%s\n~~~~\n' "$(printf '%s' "$body" | head -c 6000)"
} >>"$NOTE"
