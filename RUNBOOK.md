# Nightly post-game run

Goal: every NBA game that has gone final gets ONE 4-card carousel (top 2 scorers
per team, winners first) posted to TikTok and Facebook through Metricool, once.

## Steps

1. **Repo.** Attach `fromwaydownton-cards/fromwaydowntown-cards` with push access
   (add_repo), clone it to `/home/claude/fromwaydowntown-cards` (or `git pull` if
   already there), and work from that folder.
2. **Find finished games.** Fetch NBA `scores`. Take every game with status
   `closed` whose `start_time` is within the last 36 hours and whose `id` is NOT a
   key in `posted.json` → `posted`. Nothing new → stop, post nothing.
3. **For each new game:**
   1. Fetch its `game_stats`. Write `game.json` in the scratchpad with:
      `id`, `start_time` (from scores), `home`, `away`, `score`, and
      `player_stats` → for each team, every player as `{"name", "stats"}` keeping
      these stat keys: points, rebounds, assists, field_goals_made,
      field_goals_att, three_points_made, three_points_att, blocks, steals,
      turnovers, personal_fouls, efficiency_game_score. Copy numbers exactly.
   2. Run `python3 run_game.py <path to game.json>`. It writes the 4 PNGs and
      caption into `cards/YYYY-MM-DD/AWAY_at_HOME/` and prints the image URLs,
      caption and title.
   3. Open one or two of the PNGs to check they rendered (name, big points number,
      two stat rows, final score). Check the top scorers' points against the box
      score.
   4. Commit the new card folder and **push before posting** (Metricool pulls the
      images from the raw GitHub URLs, so they must be live first).
   5. Schedule the post with Metricool `createScheduledPost`:
      - blogId `7591436`
      - date/publicationDate = now + 3 minutes, timezone `America/Los_Angeles`
      - info:
        ```json
        {"autoPublish": true, "draft": false, "descendants": [],
         "firstCommentText": "", "hasNotReadNotes": false, "shortener": false,
         "smartLinkData": {"ids": []}, "mediaAltText": [],
         "media": [<the 4 image URLs in order>],
         "text": <caption>,
         "providers": [{"network": "tiktok"}, {"network": "facebook"}],
         "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": <title>,
                        "photoCoverIndex": 0, "autoAddMusic": false,
                        "disableComment": false, "disableDuet": false,
                        "disableStitch": false, "isAigc": false,
                        "commercialContentThirdParty": false,
                        "commercialContentOwnBrand": false},
         "facebookData": {"type": "POST"},
         "publicationDate": {"dateTime": "<YYYY-MM-DDTHH:MM:SS>",
                             "timezone": "America/Los_Angeles"}}
        ```
   6. Only after Metricool accepts it: add `"<game id>": "<AWAY>_at_<HOME> <date>"`
      to `posted.json` → `posted`, commit and push.
4. **Report** one line per game posted (matchup + the 4 players), and anything
   skipped or failed. If Metricool or GitHub errors, do not retry more than once
   and do not add the game to `posted.json`, so the next run picks it up.

## Never
- Post a game twice (always check `posted.json`).
- Post anything other than these stat cards: no logos, photos or video.
- Change the card design, colors or handle (@FROMWAYDOWNTOWN).
