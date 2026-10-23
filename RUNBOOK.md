# Hourly posting run

GitHub Actions (`nightly.yml`) builds the nightly leaders graphic once every
game of an NBA night is final and adds it to `queue.json`. This run only
POSTS what is in the queue. It never builds or edits graphics, and never needs
sports data.

## Steps

1. **Get the latest repo.** It is usually already checked out at
   `/home/claude/fromwaydowntown-cards`: run `git -C /home/claude/fromwaydowntown-cards fetch -q origin main && git -C /home/claude/fromwaydowntown-cards reset -q --hard origin/main`.
   If the folder is missing: `git clone --depth 1 https://github.com/fromwaydownton-cards/fromwaydowntown-cards /home/claude/fromwaydowntown-cards`.
2. **Read** `queue.json` → `queue` and `posted.json` → `posted`.
   Pending = queue entries whose `key` is not a key in `posted`.
   None pending → stop: "Nothing to post."
3. **Duplicate check (always).** Call Metricool `getScheduledPosts` for brandId
   `7591436`, timezone `America/Los_Angeles`, from 3 days ago to 1 day ahead.
   If any returned post's `text` equals the entry's `caption`, it was already
   posted: do not post again; just record it in step 5.
4. **Post** with Metricool `createScheduledPost`, blogId `7591436`,
   date/publicationDate = now + 3 minutes in `America/Los_Angeles`.
   - Normal entry (`"test": false`): providers tiktok, facebook, instagram.
   - Test entry (`"test": true`): provider tiktok ONLY, privacyOption `SELF_ONLY`.
   ```json
   {"autoPublish": true, "draft": false, "descendants": [],
    "firstCommentText": "", "hasNotReadNotes": false, "shortener": false,
    "smartLinkData": {"ids": []}, "mediaAltText": [],
    "media": <entry.images>,
    "text": <entry.caption>,
    "providers": [{"network": "tiktok"}, {"network": "facebook"}, {"network": "instagram"}],
    "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": <entry.title>,
                   "photoCoverIndex": 0, "autoAddMusic": false, "disableComment": false,
                   "disableDuet": false, "disableStitch": false, "isAigc": false,
                   "commercialContentThirdParty": false, "commercialContentOwnBrand": false},
    "facebookData": {"type": "POST"},
    "instagramData": {"type": "POST", "showReelOnFeed": true, "isAiGenerated": false},
    "publicationDate": {"dateTime": "<YYYY-MM-DDTHH:MM:SS>", "timezone": "America/Los_Angeles"}}
   ```
   (For a test entry, drop facebook/instagram from providers and their data blocks.)
   If Metricool rejects one network, retry once without that network and
   report which one failed.
5. **Record it.** Add `"<entry.key>": "<what was posted, e.g. tiktok+facebook+instagram, Metricool id>"`
   to `posted.json` → `posted` and save it to GitHub on branch `main`. Use the
   GitHub tools (`create_or_update_file` / `push_files` on repo
   `fromwaydownton-cards/fromwaydowntown-cards`) or `git push` if available.
   If saving fails, say so: step 3 still prevents a double post next hour.
6. **Report** one line per entry: posted / skipped as duplicate / failed + why.

## Never
- Post anything that is not in `queue.json`.
- Post the same entry twice.
- Change graphics, captions or the queue.
