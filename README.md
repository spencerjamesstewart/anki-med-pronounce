# Medical Pronunciation Lookup (Anki add-on)

A small persistent dock for Anki that looks up medical terms in the
Merriam-Webster Medical Dictionary and plays their audio pronunciation.
Stays visible on both the front and back of cards while reviewing.
Successful lookups are cached on disk so each unique term only ever
costs one API query (free tier: 1,000/day).

Requires Anki 2.1.50+ and a free Medical Dictionary API key from
<https://dictionaryapi.com/> — see `config.md` for setup.

## Layout

- `__init__.py` — the entire add-on (UI, API client, cache)
- `config.json` — default config (API key, shortcuts, startup visibility)
- `config.md` — config docs shown in Anki's add-on config dialog
- `manifest.json` — package metadata for `.ankiaddon` installs

## Developing

The repo root *is* the add-on folder. The simplest loop is to copy (or
symlink) it into Anki's add-ons directory and restart Anki to pick up
changes:

- Windows: `%APPDATA%\Anki2\addons21\medical_pronunciation_lookup`
- macOS: `~/Library/Application Support/Anki2/addons21/medical_pronunciation_lookup`
- Linux: `~/.local/share/Anki2/addons21/medical_pronunciation_lookup`

Anki will create `meta.json` (your saved config, including your API key)
and `user_files/` (the audio cache) inside the live folder. Both are
gitignored — don't commit them.

## Building a release

From the repo root:

```
zip medical_pronunciation_lookup.ankiaddon __init__.py config.json config.md manifest.json
```

The files must sit at the zip root (no containing folder), and the zip
must not include `meta.json`. Install via Tools → Add-ons → Install
from file.
