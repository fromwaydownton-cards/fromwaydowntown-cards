# Hourly posting run

GitHub Actions (`nightly.yml`) builds the posts and adds them to `queue.json`.
This run only POSTS what is in the queue. It never builds or edits graphics,
and never needs sports data.

What gets queued (since Nov 2026):
- `guess:` / `legend:` entries: Guess the Player #N, every night at 8 PM Central
  (a current player on Tue/Thu/Sat, a legend on the other nights).
- `weekly:` entries: weekly per-game leaders, Monday 12 PM Central. Since Nov 2026
  these are SPLIT entries (see "Split entries" below): a video for TikTok/YouTube and
  a 6-image swipeable carousel for Facebook/Instagram.
- `mvp:` entries: MVP ladder, Monday 5 PM Central.
The nightly recap (`night:`) and nightly shot charts (`shots:`) are retired;
older entries with those keys are still posted normally if pending.
All entry kinds are posted the same way below.

## Steps

1. **Get the latest repo.** It is usually already checked out at
   `/home/claude/fromwaydowntown-cards`: run `git -C /home/claude/fromwaydowntown-cards fetch -q origin main && git -C /home/claude/fromwaydowntown-cards reset -q --hard origin/main`.
   If the folder is missing: `git clone --depth 1 https://github.com/fromwaydownton-cards/fromwaydowntown-cards /home/claude/fromwaydowntown-cards`.
2. **Read** `queue.json` → `queue` and `posted.json` → `posted`.
   Pending = queue entries whose `key` is not a key in `posted`.
   None pending → stop: "Nothing to post."
3. **Duplicate check (always).** Call Metricool `getScheduledPosts` for brandId
   `7591436`, timezone `America/Los_Angeles`, from 3 days ago to 1 day ahead.
   For an entry with `post_at`, search through post_at + 1 day too.
   If any returned post's `text` equals the entry's `caption`, it was already
   posted: do not post again; just record it in step 5. For a split entry, check
   each of its two posts separately by network: the video post (tiktok) and the
   carousel post (facebook/instagram) share the caption, so only skip the half
   whose networks already have it.
4. **Post** with Metricool `createScheduledPost`, blogId `7591436`.
   Publish time: if the entry has `post_at` and it is later than now + 3 minutes,
   use `post_at` exactly (a Central time: Guess the Player 8 PM, weekly leaders Monday 12 PM,
   MVP ladder Monday 5 PM. Send it as
   date `post_at` and publicationDate {dateTime: post_at's local time, timezone
   "America/Chicago"}). Otherwise use now + 3 minutes in `America/Los_Angeles`.
   Metricool holds future posts and publishes them on time, so schedule it in this run.
   - Normal entry (`"test": false`): providers tiktok, facebook, instagram
     (+ youtube if getBrandSettings shows a YouTube channel connected).
   - Test entry (`"test": true`): provider tiktok ONLY, privacyOption `SELF_ONLY`.
   - **Video entries.** If the entry has `videos`, post the VIDEO, not the image:
     `media` = entry.videos; instagramData type `"REEL"` (showReelOnFeed true);
     facebookData type `"REEL"`; tiktokData without photoCoverIndex;
     youtubeData {"title": entry.title (max 100 chars), "type": "short",
     "privacy": "public", "madeForKids": false, "category": "SPORTS"}.
     If Metricool rejects the video, retry once with the image version
     (media = entry.images, types back to POST) and report it.
   ```json
   {"autoPublish": true, "draft": false, "descendants": [],
    "firstCommentText": <entry.first_comment or "">, "hasNotReadNotes": false, "shortener": false,
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
   - **Split entries.** If the entry has `carousel_on` AND `videos`, make TWO posts
     with the same caption, first comment and publish time:
     1. Video post: providers tiktok (+ youtube if connected), media = entry.videos,
        set up exactly like a video entry above (tiktokData without photoCoverIndex,
        youtubeData as above).
     2. Carousel post: providers = entry.carousel_on (facebook, instagram),
        media = entry.images (all of them, in order: Metricool posts several
        images as a carousel), facebookData {"type": "POST"}, instagramData
        {"type": "POST", "showReelOnFeed": true, "isAiGenerated": false}.
     Record both ids in step 5, e.g. "tiktok+youtube video id A; facebook+instagram
     carousel id B". If one half fails, still record the half that posted and say
     which failed. If the entry has `carousel_on` but no `videos` (the video build
     failed), post it as a normal entry with all images (a carousel everywhere).
   If Metricool rejects one network, retry once without that network and
   report which one failed. If it rejects the first comment, retry once with
   firstCommentText "" and say so.
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
