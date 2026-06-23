# Medical Pronunciation Lookup — Configuration

**api_key** (required): Your Merriam-Webster **Medical Dictionary** API key.

1. Register for free at <https://dictionaryapi.com/register/index>
2. When asked which reference(s) you want, choose **Medical Dictionary**.
3. After signing up, your key appears under "Your Keys" on your account page.
4. Paste it here as the value of `api_key` and click OK.

The key takes effect immediately — no restart needed. The free tier allows
1,000 queries per day, and this add-on caches every successful lookup on
disk, so each unique term only ever costs one query.

**shortcut**: Keyboard shortcut that jumps your cursor into the lookup box
from anywhere in Anki (default `Ctrl+Shift+M`). Press `Esc` in the box to
hand focus back to the reviewer. Changing the shortcut requires an Anki
restart.

**toggle_shortcut**: Keyboard shortcut that shows/hides the whole panel
without stealing focus (default `Ctrl+Shift+P`) — handy when it's in the
way while reviewing. Mirrors the Tools → Medical Pronunciation Lookup menu
toggle. Change it if it conflicts with another shortcut; changes require an
Anki restart.

**show_on_startup**: Whether the dock is visible when Anki opens (default
`true`). You can always toggle it via Tools → Medical Pronunciation Lookup.

## Cache

Cached audio and lookups live in this add-on's `user_files` folder
(`user_files/audio/*.mp3` and `user_files/lookup_cache.json`), which Anki
preserves across add-on updates. To clear the cache, delete those files
while Anki is closed.
