#!/usr/bin/env bash
# Publish media/*.mp4 to the 'media' branch, keeping only the last 8 days.
# The branch is rewritten each time (one commit), so videos never pile up in history.
set -euo pipefail
shopt -s nullglob
new=(media/*.mp4)
[ ${#new[@]} -eq 0 ] && { echo "no new videos"; exit 0; }
pub=$(mktemp -d)
if git ls-remote --exit-code origin media >/dev/null 2>&1; then
  git fetch -q --depth 1 origin media
  git archive FETCH_HEAD | tar -x -C "$pub"
fi
cp media/*.mp4 "$pub/"
cutoff=$(date -u -d '8 days ago' +%Y%m%d)
for f in "$pub"/*.mp4; do
  d=$(basename "$f" | cut -c1-8)
  if [[ "$d" < "$cutoff" ]]; then rm -f "$f"; fi
done
remote="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
cd "$pub"
git init -q
git checkout -q -b media
git add -A
git -c user.name="fromwaydowntown-bot" -c user.email="actions@users.noreply.github.com" commit -q -m "Videos (last 8 days)"
git push -q -f "$remote" media
echo "published: $(ls *.mp4 | tr '\n' ' ')"
