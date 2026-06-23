"""
Medical Pronunciation Lookup (Merriam-Webster Medical Dictionary)

A small dock that stays visible while you review — front or back of the
card. Type a medical term, press Enter, and hear its pronunciation.

Successful lookups (audio + phonetics) are cached on disk in this
add-on's user_files folder, so repeat lookups never touch the API and
don't count against the 1000-queries/day free quota.

Setup: Tools > Add-ons > select this add-on > Config, and paste your
free Medical Dictionary API key from https://dictionaryapi.com/
"""

import html
import json
import os
import string
import urllib.parse

import requests

from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.sound import av_player

ADDON_DIR = os.path.dirname(__file__)
USER_FILES = os.path.join(ADDON_DIR, "user_files")
AUDIO_DIR = os.path.join(USER_FILES, "audio")
INDEX_PATH = os.path.join(USER_FILES, "lookup_cache.json")

API_URL = "https://www.dictionaryapi.com/api/v3/references/medical/json/{term}?key={key}"
AUDIO_URL = "https://media.merriam-webster.com/audio/prons/en/us/mp3/{subdir}/{name}.mp3"
TIMEOUT = 10  # seconds


# --------------------------------------------------------------- errors


class TermNotFound(Exception):
    """The dictionary has no entry; .suggestions may hold alternatives."""

    def __init__(self, suggestions):
        super().__init__("term not found")
        self.suggestions = suggestions


class APIKeyError(Exception):
    """Missing, malformed, or rejected API key."""


class NetworkError(Exception):
    """Connection problems, timeouts, or unexpected HTTP responses."""


# ---------------------------------------------------------------- cache


def _load_index():
    """term -> {headword, phonetic, audio_file} mapping, best-effort."""
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_index(index):
    try:
        os.makedirs(USER_FILES, exist_ok=True)
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=1)
    except OSError:
        pass  # the cache is best-effort; never break a lookup over it


# ------------------------------------------------------------------ API


def _audio_subdir(name):
    """Merriam-Webster's rule for which folder an audio file lives in."""
    if name.startswith("bix"):
        return "bix"
    if name.startswith("gg"):
        return "gg"
    if name[0].isdigit() or name[0] in string.punctuation:
        return "number"
    return name[0]


def _extract_pronunciation(entries):
    """Return (headword, phonetic, audio_name); audio_name may be None."""
    first_hw = None
    first_ph = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hwi = entry.get("hwi") or {}
        hw = (hwi.get("hw") or "").replace("*", "") or None
        first_hw = first_hw or hw
        prs = list(hwi.get("prs") or [])
        for variant in entry.get("vrs") or []:
            prs.extend(variant.get("prs") or [])
        for pr in prs:
            if not isinstance(pr, dict):
                continue
            ph = pr.get("mw")
            first_ph = first_ph or ph
            audio = (pr.get("sound") or {}).get("audio")
            if audio:
                return hw or first_hw, ph or first_ph, audio
    return first_hw, first_ph, None


def _api_lookup(term, key):
    url = API_URL.format(
        term=urllib.parse.quote(term), key=urllib.parse.quote(key)
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise NetworkError(str(e))
    if resp.status_code in (401, 403):
        raise APIKeyError()
    if resp.status_code != 200:
        raise NetworkError(f"HTTP {resp.status_code} from dictionaryapi.com")
    try:
        data = resp.json()
    except ValueError:
        # An invalid key comes back as plain text rather than JSON.
        if "key" in resp.text.lower():
            raise APIKeyError()
        raise NetworkError("Unexpected response from dictionaryapi.com")
    if not isinstance(data, list) or not data:
        raise TermNotFound([])
    if all(isinstance(item, str) for item in data):
        # No entry found: the API returns spelling suggestions instead.
        return_suggestions = data[:3]
        raise TermNotFound(return_suggestions)
    return data


def _download_audio(audio_name):
    """Fetch the MP3 into the cache (skips if already present)."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    path = os.path.join(AUDIO_DIR, audio_name + ".mp3")
    if os.path.exists(path):
        return path
    url = AUDIO_URL.format(subdir=_audio_subdir(audio_name), name=audio_name)
    try:
        resp = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise NetworkError(str(e))
    if resp.status_code != 200 or not resp.content:
        raise NetworkError(f"audio file unavailable (HTTP {resp.status_code})")
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(resp.content)
    os.replace(tmp, path)
    return path


def lookup_term(term, key):
    """Blocking: query the API and cache the audio. Runs off the UI thread.

    Returns {"headword": ..., "phonetic": ..., "audio_file": ... or None}.
    """
    data = _api_lookup(term, key)
    headword, phonetic, audio_name = _extract_pronunciation(data)
    if audio_name:
        _download_audio(audio_name)
    return {
        "headword": headword,
        "phonetic": phonetic,
        "audio_file": (audio_name + ".mp3") if audio_name else None,
    }


# ------------------------------------------------------------------- UI


# Gruvbox Dark palette (https://github.com/morhetz/gruvbox).
GRUVBOX = {
    "card": "#3c3836",    # bg1 — the panel surface
    "input": "#282828",   # bg0 — recessed input well
    "border": "#504945",  # bg2
    "text": "#ebdbb2",    # fg1
    "muted": "#928374",   # gray
    "accent": "#8ec07c",  # bright aqua — focus ring + phonetics
    "header": "#fabd2f",  # bright yellow — section heading
    "btn": "#8ec07c",     # bright aqua — button
    "btn_hi": "#b8bb26",  # bright green — button hover
    "btn_fg": "#1d2021",  # bg0_hard — dark text on the bright button
}


def _stylesheet(p):
    # `border: none` on the button forces Qt's styled box model so the accent
    # background actually paints over macOS's native button style.
    return f"""
    #medpronCard {{
        background: {p['card']};
        border: 1px solid {p['border']};
        border-radius: 12px;
    }}
    #medpronHeader {{
        color: {p['header']};
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    #medpronInput {{
        font-size: 16px;
        padding: 8px 10px;
        border: 1px solid {p['border']};
        border-radius: 8px;
        background: {p['input']};
        color: {p['text']};
        selection-background-color: {p['accent']};
        selection-color: {p['btn_fg']};
    }}
    #medpronInput:focus {{
        border: 1px solid {p['accent']};
    }}
    #medpronButton {{
        font-size: 18px;
        border: none;
        border-radius: 8px;
        background: {p['btn']};
        color: {p['btn_fg']};
    }}
    #medpronButton:hover {{ background: {p['btn_hi']}; }}
    #medpronButton:disabled {{ background: {p['border']}; color: {p['muted']}; }}
    #medpronStatus {{
        font-size: 14px;
        color: {p['muted']};
    }}
    """


class _LookupLine(QLineEdit):
    """Lookup box that keeps out of the reviewer's way.

    Esc hands keyboard focus back to the reviewer. While the box has focus
    we also swallow Anki's window-level review shortcuts (Enter to answer,
    Space, 1–4, e to edit, …) so typing a term — and pressing Enter to look
    it up — never advances the card underneath.
    """

    def event(self, evt):
        # Qt offers a key to the focused widget via a ShortcutOverride event
        # before firing any matching window shortcut. Accepting it routes the
        # key here instead of to the shortcut. We claim every un-modified key
        # so reviewer hotkeys stay dormant, but leave Ctrl/⌘ combos alone so
        # clipboard and app shortcuts (copy, paste, quit) keep working.
        if evt.type() == QEvent.Type.ShortcutOverride:
            blocking_mods = (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.MetaModifier
            )
            if not (evt.modifiers() & blocking_mods):
                evt.accept()
                return True
        return super().event(evt)

    def keyPressEvent(self, evt):
        if evt.key() == Qt.Key.Key_Escape:
            mw.web.setFocus()
            return
        super().keyPressEvent(evt)


class PronunciationDock(QDockWidget):
    def __init__(self):
        super().__init__("Pronunciation", mw)
        self.setObjectName("MedicalPronunciationDock")
        self._busy = False
        self.index = _load_index()

        body = QWidget()
        body.setObjectName("medpronBody")
        outer = QVBoxLayout(body)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        card = QFrame()
        card.setObjectName("medpronCard")
        col = QVBoxLayout(card)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(10)

        header = QLabel("🩺  MEDICAL PRONUNCIATION")
        header.setObjectName("medpronHeader")
        col.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.input = _LookupLine()
        self.input.setObjectName("medpronInput")
        self.input.setPlaceholderText("Type a medical term…")
        self.input.setMinimumWidth(150)
        self.input.setClearButtonEnabled(True)
        self.button = QPushButton("🔊")
        self.button.setObjectName("medpronButton")
        self.button.setFixedSize(42, 40)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setToolTip("Look up / play (or press Enter)")
        row.addWidget(self.input)
        row.addWidget(self.button)
        col.addLayout(row)

        self.status = QLabel("Ready — type a term and press Enter.")
        self.status.setObjectName("medpronStatus")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        col.addWidget(self.status)

        outer.addWidget(card)
        outer.addStretch(1)

        body.setStyleSheet(_stylesheet(GRUVBOX))
        self.setWidget(body)
        self.input.returnPressed.connect(self.lookup)
        self.button.clicked.connect(self.lookup)

    # ---------------------------------------------------------- helpers

    def set_status(self, text):
        self.status.setText(text)

    def focus_input(self):
        self.show()
        self.raise_()
        self.input.setFocus()
        self.input.selectAll()

    # ----------------------------------------------------------- lookup

    def lookup(self):
        if self._busy:
            return
        term = self.input.text().strip()
        if not term:
            return
        key = term.lower()

        # Cache hit: play from disk, no API call.
        cached = self.index.get(key)
        if cached:
            audio_file = cached.get("audio_file")
            if audio_file is None or os.path.exists(
                os.path.join(AUDIO_DIR, audio_file)
            ):
                self._show_result(cached, from_cache=True)
                return
            # The MP3 was deleted from disk — forget the entry and refetch.
            self.index.pop(key, None)
            _save_index(self.index)

        config = mw.addonManager.getConfig(__name__) or {}
        api_key = (config.get("api_key") or "").strip()
        if not api_key:
            self.set_status(
                "No API key set. Get a free Medical Dictionary key at "
                "dictionaryapi.com, then paste it under Tools → Add-ons → "
                "Medical Pronunciation Lookup → Config."
            )
            return

        self._busy = True
        self.button.setEnabled(False)
        self.set_status(f"Looking up “{html.escape(term)}”…")
        mw.taskman.run_in_background(
            lambda: lookup_term(term, api_key),
            lambda fut: self._on_done(key, term, fut),
        )

    def _on_done(self, key, term, fut):
        self._busy = False
        self.button.setEnabled(True)
        try:
            result = fut.result()
        except TermNotFound as e:
            shown = html.escape(term)
            if e.suggestions:
                sugg = ", ".join(html.escape(s) for s in e.suggestions)
                self.set_status(
                    f"“{shown}” not found. Did you mean: {sugg}?"
                )
            else:
                self.set_status(
                    f"“{shown}” not found in the medical dictionary."
                )
        except APIKeyError:
            self.set_status(
                "API key rejected by Merriam-Webster. Double-check it under "
                "Tools → Add-ons → Medical Pronunciation Lookup → Config."
            )
        except NetworkError as e:
            self.set_status(
                "Network problem — couldn’t reach Merriam-Webster. "
                f"({html.escape(str(e))})"
            )
        except Exception as e:  # noqa: BLE001 — surface anything unexpected
            self.set_status(f"Unexpected error: {html.escape(str(e))}")
        else:
            self.index[key] = result
            _save_index(self.index)
            self._show_result(result, from_cache=False)

    def _show_result(self, result, from_cache):
        headword = result.get("headword") or self.input.text().strip()
        phonetic = result.get("phonetic")
        audio_file = result.get("audio_file")
        p = GRUVBOX

        parts = [
            f"<span style='font-size:20px;font-weight:700;color:{p['text']};'>"
            f"{html.escape(headword)}</span>"
        ]
        if phonetic:
            parts.append(
                f"<span style='font-size:15px;color:{p['accent']};'>"
                f"\\{html.escape(phonetic)}\\</span>"
            )

        if audio_file:
            path = os.path.join(AUDIO_DIR, audio_file)
            if os.path.exists(path):
                av_player.play_file(path)
                note = "🔊 playing" + (" · cached" if from_cache else "")
            else:
                note = "audio file missing from cache"
        else:
            note = "no audio available for this entry"
        parts.append(
            f"<span style='font-size:12px;color:{p['muted']};'>"
            f"{html.escape(note)}</span>"
        )

        # One compact line so a bottom-docked panel stays short; the plain
        # spaces let it wrap gracefully if the dock is ever narrow instead.
        self.set_status(" &nbsp; ".join(parts))
        self.input.selectAll()


# ---------------------------------------------------------------- setup

_dock = None


def _setup():
    global _dock
    _dock = PronunciationDock()
    mw.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, _dock)

    config = mw.addonManager.getConfig(__name__) or {}

    # Tools-menu toggle, stays in sync with the dock's close button.
    action = _dock.toggleViewAction()
    action.setText("Medical Pronunciation Lookup")
    mw.form.menuTools.addAction(action)

    # Global shortcut to jump the cursor into the lookup box.
    shortcut = (config.get("shortcut") or "Ctrl+Shift+M").strip()
    if shortcut:
        sc = QShortcut(QKeySequence(shortcut), mw)
        sc.activated.connect(_dock.focus_input)

    if not config.get("show_on_startup", True):
        _dock.hide()


gui_hooks.main_window_did_init.append(_setup)
