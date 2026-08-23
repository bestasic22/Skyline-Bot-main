from __future__ import annotations

import html
import logging
import os
import re
import threading
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from skylinebot.utils import i18n

logger = logging.getLogger(__name__)


_TRANSLATABLE_HTML_ATTRS = {
    "title",
    "placeholder",
    "aria-label",
    "aria-description",
    "alt",
}
_TRANSLATION_SKIP_TAGS = {"script", "style", "code", "pre"}
_TRANSLATION_SKIP_ATTR_NAMES = {
    "data-guild-name",
    "data-user-name",
    "data-server-name",
    "data-no-translate-name",
}
_TRANSLATION_SKIP_ATTR_VALUES = {"1", "true", "yes", "on"}
_HAS_TRANSLATABLE_CHARS_RE = re.compile(r"[A-Za-z\u0E00-\u0E7F]")
_HAS_THAI_CHARS_RE = re.compile(r"[\u0E00-\u0E7F]")
_HAS_EN_CHARS_RE = re.compile(r"[A-Za-z]")
_DASHBOARD_I18N_LINE_RE = re.compile(r'^\s*([A-Za-z0-9_]+):\s*"((?:\\.|[^"\\])*)",?\s*$')
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _safe_int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, str(default))).strip()
    try:
        return int(raw)
    except Exception:
        return int(default)


_LAYOUT_MARKUP_LOCALIZE_EN_ENABLED = str(
    os.getenv("DASHBOARD_LAYOUT_LOCALIZE_EN_ENABLED", "0")
).strip().lower() in {"1", "true", "yes", "on"}
_LAYOUT_MARKUP_LOCALIZE_TH_ENABLED = str(
    os.getenv("DASHBOARD_LAYOUT_LOCALIZE_TH_ENABLED", "0")
).strip().lower() in {"1", "true", "yes", "on"}
_LAYOUT_GOOGLE_FALLBACK_ENABLED = str(
    os.getenv("DASHBOARD_LAYOUT_GOOGLE_FALLBACK_ENABLED", "0")
).strip().lower() in {"1", "true", "yes", "on"}
_LAYOUT_GOOGLE_FALLBACK_MAX_CHARS = max(
    24,
    _safe_int_env("DASHBOARD_LAYOUT_GOOGLE_FALLBACK_MAX_CHARS", 260),
)
_LAYOUT_GOOGLE_FALLBACK_CACHE_LIMIT = max(
    128,
    _safe_int_env("DASHBOARD_LAYOUT_GOOGLE_FALLBACK_CACHE_LIMIT", 6000),
)
_LAYOUT_LITERAL_TRANSLATE_MAX_CHARS = max(
    48,
    _safe_int_env("DASHBOARD_LAYOUT_LITERAL_TRANSLATE_MAX_CHARS", 480),
)
_LAYOUT_LITERAL_CACHE_LIMIT = max(
    256,
    _safe_int_env("DASHBOARD_LAYOUT_LITERAL_CACHE_LIMIT", 12000),
)
_LAYOUT_LITERAL_CACHE_MAX_CHARS = max(
    24,
    _safe_int_env("DASHBOARD_LAYOUT_LITERAL_CACHE_MAX_CHARS", 360),
)
_DASHBOARD_I18N_JS_VERSION = str(
    os.getenv("DASHBOARD_I18N_JS_VERSION", "20260520-4") or "20260520-4"
).strip()
_TRANSLATION_TOKEN_RE = re.compile(
    r"(\{\{[^{}]{0,240}\}\}|\{[^{}]{0,240}\}|`[^`]{0,320}`|https?://\S+|%\([^)]+\)[a-zA-Z]|%[a-zA-Z])"
)
_google_fallback_cache: dict[tuple[str, str], str] = {}
_google_fallback_cache_order: list[tuple[str, str]] = []
_google_fallback_lock = threading.Lock()
_google_translator_cache: dict[str, Any] = {}
_literal_translation_cache: dict[tuple[str, str], str] = {}
_literal_translation_cache_order: list[tuple[str, str]] = []
_literal_translation_lock = threading.Lock()


def _dashboard_i18n_script_src(language: str) -> str:
    lang = "en" if str(language or "").strip().lower() == "en" else "th"
    suffix = f"?v={_DASHBOARD_I18N_JS_VERSION}" if _DASHBOARD_I18N_JS_VERSION else ""
    return f"/dashboard/static/dashboard/i18n/{lang}.js{suffix}"


def _dashboard_i18n_script_tags(language: str) -> str:
    src = _dashboard_i18n_script_src(language)
    return f'<script src="{src}" defer></script>'


def _decode_js_string_literal(raw: str) -> str:
    # Keep decoding conservative to avoid mojibake on existing UTF-8 Thai text.
    text = str(raw or "")
    return (
        text.replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\/", "/")
    )


def _strip_inline_markup(text: str) -> str:
    return _HTML_TAG_RE.sub("", str(text or ""))


def _normalize_dashboard_literal(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _load_dashboard_i18n_dictionary(locale: str) -> dict[str, str]:
    i18n_file = (
        Path(__file__).resolve().parents[2]
        / "static"
        / "dashboard"
        / "i18n"
        / f"{locale}.js"
    )
    try:
        lines = i18n_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return {}

    entries: dict[str, str] = {}
    for line in lines:
        match = _DASHBOARD_I18N_LINE_RE.match(line)
        if not match:
            continue
        key = str(match.group(1) or "").strip()
        if not key:
            continue
        entries[key] = _decode_js_string_literal(match.group(2) or "")
    return entries


def _build_dashboard_literal_maps() -> tuple[dict[str, str], dict[str, str]]:
    en_dict = _load_dashboard_i18n_dictionary("en")
    th_dict = _load_dashboard_i18n_dictionary("th")
    if not en_dict or not th_dict:
        return {}, {}

    en_to_th: dict[str, str] = {}
    th_to_en: dict[str, str] = {}
    for key, en_value in en_dict.items():
        th_value = th_dict.get(key)
        if not isinstance(th_value, str):
            continue

        en_text = _normalize_dashboard_literal(_strip_inline_markup(en_value))
        th_text = _normalize_dashboard_literal(_strip_inline_markup(th_value))
        if not en_text or not th_text or en_text == th_text:
            continue

        en_to_th.setdefault(en_text, th_text)
        th_to_en.setdefault(th_text, en_text)

    return en_to_th, th_to_en


_DASHBOARD_LITERAL_EN_TO_TH, _DASHBOARD_LITERAL_TH_TO_EN = _build_dashboard_literal_maps()


def _map_dashboard_literal_text(text: str, target_lang: str) -> str | None:
    normalized = _normalize_dashboard_literal(_strip_inline_markup(text))
    if not normalized:
        return None
    if target_lang == "th":
        return _DASHBOARD_LITERAL_EN_TO_TH.get(normalized)
    if target_lang == "en":
        return _DASHBOARD_LITERAL_TH_TO_EN.get(normalized)
    return None


def _mask_translation_tokens(payload: str) -> tuple[str, dict[str, str]]:
    text = str(payload or "")
    if not text:
        return text, {}
    token_map: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        token_key = f"__SKY_I18N_TOKEN_{len(token_map)}__"
        token_map[token_key] = str(match.group(0) or "")
        return token_key

    masked = _TRANSLATION_TOKEN_RE.sub(_replace, text)
    return masked, token_map


def _restore_translation_tokens(payload: str, token_map: Mapping[str, str]) -> str:
    text = str(payload or "")
    if not text or not token_map:
        return text
    restored = text
    for token_key, token_value in token_map.items():
        restored = restored.replace(token_key, token_value)
    return restored


def _read_google_cache(target_lang: str, text: str) -> str | None:
    key = (target_lang, text)
    with _google_fallback_lock:
        return _google_fallback_cache.get(key)


def _write_google_cache(target_lang: str, text: str, translated: str) -> None:
    key = (target_lang, text)
    with _google_fallback_lock:
        _google_fallback_cache[key] = translated
        _google_fallback_cache_order.append(key)
        while len(_google_fallback_cache_order) > _LAYOUT_GOOGLE_FALLBACK_CACHE_LIMIT:
            oldest = _google_fallback_cache_order.pop(0)
            _google_fallback_cache.pop(oldest, None)


def _read_literal_cache(target_lang: str, text: str) -> str | None:
    payload = str(text or "")
    if not payload or len(payload) > _LAYOUT_LITERAL_CACHE_MAX_CHARS:
        return None
    key = (target_lang, payload)
    with _literal_translation_lock:
        return _literal_translation_cache.get(key)


def _write_literal_cache(target_lang: str, text: str, translated: str) -> None:
    payload = str(text or "")
    if not payload or len(payload) > _LAYOUT_LITERAL_CACHE_MAX_CHARS:
        return
    key = (target_lang, payload)
    with _literal_translation_lock:
        if key in _literal_translation_cache:
            _literal_translation_cache_order[:] = [
                item for item in _literal_translation_cache_order if item != key
            ]
        _literal_translation_cache[key] = str(translated or "")
        _literal_translation_cache_order.append(key)
        while len(_literal_translation_cache_order) > _LAYOUT_LITERAL_CACHE_LIMIT:
            oldest = _literal_translation_cache_order.pop(0)
            _literal_translation_cache.pop(oldest, None)


def _get_google_translator(target_lang: str) -> Any | None:
    if target_lang not in {"th", "en"}:
        return None
    with _google_fallback_lock:
        cached = _google_translator_cache.get(target_lang)
    if cached is not None:
        return cached
    try:
        from deep_translator import GoogleTranslator  # type: ignore
    except Exception:
        return None
    try:
        translator = GoogleTranslator(source="auto", target=target_lang)
    except Exception:
        return None
    with _google_fallback_lock:
        _google_translator_cache[target_lang] = translator
    return translator


def _translate_literal_text_google_fallback(text: str, target_lang: str) -> str:
    payload = str(text or "")
    if not payload or target_lang not in {"th", "en"}:
        return payload
    if not _LAYOUT_GOOGLE_FALLBACK_ENABLED:
        return payload
    if len(payload) > _LAYOUT_GOOGLE_FALLBACK_MAX_CHARS:
        return payload
    compact = " ".join(payload.split())
    if len(compact) < 4:
        return payload
    # Short single-token literals should stay on rule-based dictionaries to keep runtime latency low.
    if len(compact) < 12 and " " not in compact:
        return payload
    if target_lang == "en" and not _HAS_THAI_CHARS_RE.search(payload):
        return payload
    if target_lang == "th" and not _HAS_EN_CHARS_RE.search(payload):
        return payload

    cached = _read_google_cache(target_lang, payload)
    if isinstance(cached, str):
        return cached

    translator = _get_google_translator(target_lang)
    if translator is None:
        return payload

    masked_text, token_map = _mask_translation_tokens(payload)
    if not masked_text.strip():
        return payload

    try:
        translated = translator.translate(masked_text)
    except Exception:
        return payload
    if not isinstance(translated, str) or not translated.strip():
        return payload

    restored = _restore_translation_tokens(translated, token_map)
    if not restored:
        return payload
    _write_google_cache(target_lang, payload, restored)
    return restored


def _translate_literal_text(text: str, target_lang: str) -> str:
    payload = str(text or "")
    if not payload or not payload.strip():
        return payload
    if target_lang not in {"th", "en"}:
        return payload
    if len(payload) > _LAYOUT_LITERAL_TRANSLATE_MAX_CHARS:
        return payload
    if not _HAS_TRANSLATABLE_CHARS_RE.search(payload):
        return payload
    if target_lang == "th" and not _HAS_EN_CHARS_RE.search(payload):
        return payload
    if target_lang == "en" and not _HAS_THAI_CHARS_RE.search(payload):
        return payload

    cached = _read_literal_cache(target_lang, payload)
    if isinstance(cached, str):
        return cached

    mapped_dashboard_literal = _map_dashboard_literal_text(payload, target_lang)
    if isinstance(mapped_dashboard_literal, str) and mapped_dashboard_literal:
        _write_literal_cache(target_lang, payload, mapped_dashboard_literal)
        return mapped_dashboard_literal

    translated = payload
    normalize_mixed = getattr(i18n, "_normalize_mixed_language_text", None)

    if callable(normalize_mixed):
        try:
            normalized_seed = normalize_mixed(translated, target_lang)
            if isinstance(normalized_seed, str) and normalized_seed:
                translated = normalized_seed
        except Exception:
            pass

    map_literal = getattr(i18n, "_map_literal_from_locales", None)
    if callable(map_literal):
        try:
            mapped = map_literal(translated, target_lang)
            if isinstance(mapped, str) and mapped and mapped != translated:
                translated = mapped
        except Exception:
            pass

    rule_based = getattr(i18n, "_translate_text_runtime_rule_based", None)
    if callable(rule_based):
        try:
            normalized = rule_based(translated, target_lang)
            if isinstance(normalized, str) and normalized:
                translated = normalized
        except Exception:
            pass

    if target_lang == "th":
        heuristic_to_th = getattr(i18n, "_translate_command_text_to_th", None)
        generic_fallback = str(getattr(i18n, "_TH_COMMAND_GENERIC_FALLBACK", "") or "")
        if callable(heuristic_to_th):
            try:
                heuristic = heuristic_to_th(translated)
                if (
                    isinstance(heuristic, str)
                    and heuristic
                    and heuristic != translated
                    and heuristic != generic_fallback
                ):
                    translated = heuristic
            except Exception:
                pass

    contains_en = getattr(i18n, "_contains_english", None)
    contains_th = getattr(i18n, "_contains_thai", None)
    ai_translate = getattr(i18n, "_translate_text_with_aiforthai", None)
    ai_runtime_enabled = bool(getattr(i18n, "_I18N_AI_RUNTIME_FALLBACK_ENABLED", False))
    if ai_runtime_enabled and callable(ai_translate):
        try:
            if target_lang == "th" and callable(contains_en) and contains_en(translated):
                ai_result = ai_translate(translated, "en2th")
                if isinstance(ai_result, str) and ai_result:
                    translated = ai_result
            elif target_lang == "en" and callable(contains_th) and contains_th(translated):
                ai_result = ai_translate(translated, "th2en")
                if isinstance(ai_result, str) and ai_result:
                    translated = ai_result
        except Exception:
            pass

    # Final fallback for unresolved mixed-language literals in dashboard pages.
    # This is opt-in via env and cached aggressively to avoid repeated external calls.
    try:
        if target_lang == "en" and _HAS_THAI_CHARS_RE.search(translated or ""):
            translated = _translate_literal_text_google_fallback(translated, "en")
        elif target_lang == "th" and _HAS_EN_CHARS_RE.search(translated or ""):
            translated = _translate_literal_text_google_fallback(translated, "th")
    except Exception:
        pass

    if callable(normalize_mixed):
        try:
            normalized_final = normalize_mixed(translated, target_lang)
            if isinstance(normalized_final, str) and normalized_final:
                translated = normalized_final
        except Exception:
            pass

    result = translated if isinstance(translated, str) and translated else payload
    _write_literal_cache(target_lang, payload, result)
    return result


class _DashboardHtmlLocalizer(HTMLParser):
    def __init__(self, target_lang: str):
        super().__init__(convert_charrefs=False)
        self.target_lang = target_lang
        self.parts: list[str] = []
        self._skip_translate_stack: list[bool] = []

    def _should_skip_text_translation(self) -> bool:
        return any(self._skip_translate_stack)

    @staticmethod
    def _has_skip_translation_attr(attrs: list[tuple[str, str | None]]) -> bool:
        for key, value in attrs:
            attr_name = str(key or "").strip().lower()
            attr_value = str(value or "").strip().lower()
            if attr_name == "data-no-auto-i18n" and attr_value in _TRANSLATION_SKIP_ATTR_VALUES:
                return True
            if attr_name in _TRANSLATION_SKIP_ATTR_NAMES:
                return True
        return False

    @staticmethod
    def _serialize_attrs(attrs: list[tuple[str, str | None]]) -> str:
        serialized: list[str] = []
        for key, value in attrs:
            if value is None:
                serialized.append(str(key))
                continue
            escaped = html.escape(str(value), quote=True)
            serialized.append(f'{key}="{escaped}"')
        return (" " + " ".join(serialized)) if serialized else ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = str(tag or "").lower()
        parent_skip = bool(self._skip_translate_stack[-1]) if self._skip_translate_stack else False
        current_skip = parent_skip or tag_name in _TRANSLATION_SKIP_TAGS or self._has_skip_translation_attr(attrs)
        translated_attrs: list[tuple[str, str | None]] = []
        for key, value in attrs:
            attr_name = str(key or "")
            attr_value = value
            if (
                isinstance(attr_value, str)
                and attr_name.lower() in _TRANSLATABLE_HTML_ATTRS
                and not attr_name.lower().startswith("data-")
                and not current_skip
            ):
                attr_value = _translate_literal_text(attr_value, self.target_lang)
            translated_attrs.append((attr_name, attr_value))
        self.parts.append(f"<{tag}{self._serialize_attrs(translated_attrs)}>")
        self._skip_translate_stack.append(current_skip)

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if self._skip_translate_stack:
            self._skip_translate_stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = str(tag or "").lower()
        parent_skip = bool(self._skip_translate_stack[-1]) if self._skip_translate_stack else False
        current_skip = parent_skip or tag_name in _TRANSLATION_SKIP_TAGS or self._has_skip_translation_attr(attrs)
        translated_attrs: list[tuple[str, str | None]] = []
        for key, value in attrs:
            attr_name = str(key or "")
            attr_value = value
            if (
                isinstance(attr_value, str)
                and attr_name.lower() in _TRANSLATABLE_HTML_ATTRS
                and not attr_name.lower().startswith("data-")
                and not current_skip
            ):
                attr_value = _translate_literal_text(attr_value, self.target_lang)
            translated_attrs.append((attr_name, attr_value))
        self.parts.append(f"<{tag}{self._serialize_attrs(translated_attrs)}/>")

    def handle_data(self, data: str) -> None:
        if self._should_skip_text_translation():
            self.parts.append(data)
            return
        self.parts.append(_translate_literal_text(data, self.target_lang))

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")


def _localize_html_markup(markup: str, target_lang: str) -> str:
    raw = str(markup or "")
    if not raw or target_lang not in {"th", "en"}:
        return raw
    parser = _DashboardHtmlLocalizer(target_lang)
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return raw
    rendered = "".join(parser.parts)
    return rendered or raw


def _should_localize_layout_markup(target_lang: str) -> bool:
    lang = str(target_lang or "").strip().lower()
    if lang == "en":
        return _LAYOUT_MARKUP_LOCALIZE_EN_ENABLED
    if lang == "th":
        return _LAYOUT_MARKUP_LOCALIZE_TH_ENABLED
    return False


_IMAGE_CRITICAL_CLASS_HINTS = {
    "sidebar-server-head",
    "topbar-account-trigger-avatar",
    "topbar-account-card-avatar",
    "profile-user-avatar",
    "server-rail-item",
    "guild-card-head",
}

_STRAY_LAYOUT_TEXT_RE = re.compile(
    r"(?<=\>)\s*dashboard-content\s+flex-1\s+min-h-0\s+p-0\"?\s*(?=\<)",
    flags=re.IGNORECASE,
)


class _DashboardImagePerfHintInjector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []

    @staticmethod
    def _serialize_attrs(attrs: list[tuple[str, str | None]]) -> str:
        serialized: list[str] = []
        for key, value in attrs:
            if value is None:
                serialized.append(str(key))
                continue
            escaped = html.escape(str(value), quote=True)
            serialized.append(f'{key}="{escaped}"')
        return (" " + " ".join(serialized)) if serialized else ""

    @staticmethod
    def _is_critical_image(attrs: list[tuple[str, str | None]]) -> bool:
        attr_map: dict[str, str] = {}
        for key, value in attrs:
            attr_map[str(key or "").strip().lower()] = str(value or "").strip().lower()

        if attr_map.get("loading") == "eager":
            return True
        if attr_map.get("fetchpriority") == "high":
            return True
        if attr_map.get("data-critical-img") in {"1", "true", "yes", "on"}:
            return True

        class_tokens = {
            token.strip().lower()
            for token in str(attr_map.get("class") or "").split()
            if token and token.strip()
        }
        if class_tokens.intersection(_IMAGE_CRITICAL_CLASS_HINTS):
            return True
        return False

    def _inject_img_attrs(self, attrs: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
        attr_map = {str(key or "").strip().lower(): key for key, _value in attrs}
        out_attrs = list(attrs)
        is_critical = self._is_critical_image(attrs)

        if "decoding" not in attr_map:
            out_attrs.append(("decoding", "async"))
        if "loading" not in attr_map:
            out_attrs.append(("loading", "eager" if is_critical else "lazy"))
        if "fetchpriority" not in attr_map:
            out_attrs.append(("fetchpriority", "high" if is_critical else "low"))
        return out_attrs

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = str(tag or "").lower()
        final_attrs = self._inject_img_attrs(attrs) if tag_name == "img" else attrs
        self.parts.append(f"<{tag}{self._serialize_attrs(final_attrs)}>")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = str(tag or "").lower()
        final_attrs = self._inject_img_attrs(attrs) if tag_name == "img" else attrs
        self.parts.append(f"<{tag}{self._serialize_attrs(final_attrs)}/>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")


def _apply_image_perf_hints(markup: str) -> str:
    raw = str(markup or "")
    if not raw or "<img" not in raw.lower():
        return raw
    parser = _DashboardImagePerfHintInjector()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return raw
    rendered = "".join(parser.parts)
    return rendered or raw


def _strip_known_stray_layout_text(markup: str) -> str:
    raw = str(markup or "")
    if not raw:
        return raw
    if "dashboard-content flex-1 min-h-0 p-0" not in raw:
        return raw
    cleaned = _STRAY_LAYOUT_TEXT_RE.sub("", raw)
    return cleaned or raw


class DashboardRenderHelpers:
    def __init__(self, *, layout_template_path: Path, page_template_dir: Path):
        self._layout_template_path = layout_template_path
        self._page_template_dir = page_template_dir
        self._layout_template_cache: str | None = None
        self._layout_template_mtime_ns: int = -1
        self._page_template_cache: dict[str, str] = {}
        self._page_template_mtime_ns: dict[str, int] = {}

    def escape(self, value: Any) -> str:
        return html.escape(str(value or ""))

    def load_layout_template(self) -> str:
        try:
            stat = self._layout_template_path.stat()
            current_mtime_ns = int(stat.st_mtime_ns)
        except Exception:
            current_mtime_ns = -1
        if self._layout_template_cache is not None and current_mtime_ns == self._layout_template_mtime_ns:
            return self._layout_template_cache
        try:
            self._layout_template_cache = self._layout_template_path.read_text(encoding="utf-8")
            self._layout_template_mtime_ns = current_mtime_ns
        except Exception:
            self._layout_template_cache = ""
            self._layout_template_mtime_ns = current_mtime_ns
        return self._layout_template_cache

    def load_page_template(self, template_name: str) -> str:
        cache_key = str(template_name or "").strip()
        if not cache_key:
            return ""
        template_path = self._page_template_dir / cache_key
        try:
            stat = template_path.stat()
            current_mtime_ns = int(stat.st_mtime_ns)
        except Exception:
            current_mtime_ns = -1

        cached = self._page_template_cache.get(cache_key)
        cached_mtime_ns = int(self._page_template_mtime_ns.get(cache_key, -2))
        if cached is not None and cached_mtime_ns == current_mtime_ns:
            return cached
        try:
            content = template_path.read_text(encoding="utf-8")
        except Exception:
            content = ""
        self._page_template_cache[cache_key] = content
        self._page_template_mtime_ns[cache_key] = current_mtime_ns
        return content

    def render_f_template(
        self,
        template_name: str,
        context: dict[str, Any],
        *,
        globals_scope: Mapping[str, Any] | None = None,
    ) -> str:
        normalized_name = str(template_name or "").strip()
        is_script_template = normalized_name.lower().endswith(".js")

        template = self.load_page_template(normalized_name)
        if not template:
            if is_script_template:
                return ""
            return self._render_template_issue_markup(
                normalized_name,
                "ไม่พบไฟล์เทมเพลตของหน้านี้",
            )

        safe_context = dict(context or {})
        safe_context["__ctx"] = safe_context
        source = 'fr"""' + template.replace('"""', '\\"\\"\\"') + '"""'
        try:
            return eval(source, dict(globals_scope or {}), safe_context)
        except Exception:
            logger.exception("Failed to render dashboard template: %s", normalized_name or "<unknown>")
            if is_script_template:
                # Keep script slots valid when nested JS-template rendering fails.
                return ""
            return self._render_template_issue_markup(
                normalized_name,
                "เกิดปัญหาระหว่างเรนเดอร์หน้า กรุณารีเฟรชอีกครั้ง",
            )

    def _render_template_issue_markup(self, template_name: str, message: str) -> str:
        safe_name = self.escape(template_name or "unknown")
        safe_message = self.escape(message or "เกิดข้อผิดพลาด")
        return (
            '<section class="section-stack dashboard-detail-shell">'
            '<section class="panel">'
            '<div class="panel-header detail-page-hero detail-page-hero-auto">'
            '<div class="panel-title detail-page-hero-copy">'
            '<h2 data-icon-key="warning">โหลดหน้าไม่สำเร็จ</h2>'
            f"<p>{safe_message}</p>"
            "</div></div>"
            '<section class="panel-sub detail-page-section-auto">'
            f"<strong>Template:</strong> <code>{safe_name}</code>"
            "</section></section></section>"
        )

    def render_layout_template(
        self,
        *,
        callback_url: str,
        title_html: str,
        page_mode_html: str,
        topbar_html: str,
        content_markup: str,
        main_content_html: str,
        server_switcher_profile_html: str,
        server_switcher_items_html: str,
        sidebar_server_name_html: str,
        sidebar_server_icon_url: str,
        sidebar_server_access_html: str = "",
        topbar_center_html: str,
        topbar_actions_html: str,
        sidebar_menu_html: str,
        dashboard_bootstrap_json: str,
        global_copyright_html: str,
        seo_path: str = "/dashboard",
        seo_image_path: str = "/dashboard/static/image_web_bot/giveaways_dashboard.webp",
        language: str = "th",
    ) -> str:
        resolved_lang = str(language or "th").strip().lower()
        if resolved_lang not in {"th", "en"}:
            resolved_lang = "th"
        i18n_script_tags = _dashboard_i18n_script_tags(resolved_lang)
        should_localize_markup = _should_localize_layout_markup(resolved_lang)
        resolved_title_html = str(title_html or "")
        if should_localize_markup:
            try:
                resolved_title_html = html.escape(
                    _translate_literal_text(html.unescape(resolved_title_html), resolved_lang)
                )
            except Exception:
                resolved_title_html = str(title_html or "")

        # Runtime localization can be expensive on large pages.
        # Keep this behind explicit language toggles so operators can tune behavior per locale.
        if should_localize_markup:
            topbar_html = _localize_html_markup(topbar_html, resolved_lang)
            content_markup = _localize_html_markup(content_markup, resolved_lang)
            main_content_html = _localize_html_markup(main_content_html, resolved_lang)
            sidebar_server_access_html = _localize_html_markup(sidebar_server_access_html, resolved_lang)
            topbar_center_html = _localize_html_markup(topbar_center_html, resolved_lang)
            topbar_actions_html = _localize_html_markup(topbar_actions_html, resolved_lang)
            sidebar_menu_html = _localize_html_markup(sidebar_menu_html, resolved_lang)
            global_copyright_html = _localize_html_markup(global_copyright_html, resolved_lang)

        topbar_html = _apply_image_perf_hints(topbar_html)
        content_markup = _apply_image_perf_hints(content_markup)
        main_content_html = _apply_image_perf_hints(main_content_html)
        server_switcher_profile_html = _apply_image_perf_hints(server_switcher_profile_html)
        server_switcher_items_html = _apply_image_perf_hints(server_switcher_items_html)
        sidebar_server_access_html = _apply_image_perf_hints(sidebar_server_access_html)
        topbar_center_html = _apply_image_perf_hints(topbar_center_html)
        topbar_actions_html = _apply_image_perf_hints(topbar_actions_html)
        sidebar_menu_html = _apply_image_perf_hints(sidebar_menu_html)

        if page_mode_html not in {"dashboard", "music-user"}:
            return _strip_known_stray_layout_text(
                (
                f"<!DOCTYPE html><html lang=\"{resolved_lang}\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                f"<title>{resolved_title_html}</title>"
                "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">"
                "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>"
                "<link href=\"https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap\" rel=\"stylesheet\">"
                "<link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.7.2/css/all.min.css\">"
                "<link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css\">"
                "<link rel=\"stylesheet\" href=\"/dashboard/static/dashboard/layout.css?v=20260520-1\">"
                "<link rel=\"stylesheet\" href=\"/dashboard/static/dashboard/layout-unified.css?v=20260519-7\">"
                "</head>"
                f"<body class=\"page-{page_mode_html} ui-pro\">"
                "<div class=\"ui-backdrop\"><span class=\"ui-orb orb-a\"></span><span class=\"ui-orb orb-b\"></span><span class=\"ui-orb orb-c\"></span></div>"
                "<div id=\"toast-container\"></div><div class=\"frame app-shell\">"
                f"{topbar_html}<main class=\"content\">{content_markup}</main>"
                f"<footer class=\"layout-global-footer\" style=\"margin:8px 16px calc(14px + env(safe-area-inset-bottom, 0px));padding:10px 8px 8px;text-align:center;line-height:1.45;font-size:.9rem;color:var(--text,#dce8ff);font-weight:600;letter-spacing:.01em;text-shadow:0 1px 0 rgba(0,0,0,.28);border-top:1px solid rgba(130,155,216,.24);position:relative;z-index:2;\">{global_copyright_html}</footer>"
                "</div>"
                f"<script type=\"application/json\" id=\"dashboard-bootstrap\">{dashboard_bootstrap_json}</script>"
                "<script src=\"/dashboard/static/dashboard/layout.js?v=20260520-13\" defer></script>"
                f"{i18n_script_tags}"
                "<script src=\"/dashboard/static/dashboard/layout-runtime.js?v=20260520-9\" defer></script>"
                "<script src=\"/dashboard/static/dashboard/layout-unified.js?v=20260520-3\" defer></script>"
                "</body></html>"
                )
            )

        base_url = str(callback_url or "").strip()
        callback_suffix = "/dashboard/auth/callback"
        if base_url.endswith(callback_suffix):
            base_url = base_url[: -len(callback_suffix)]

        def _resolve_absolute_url(value: str, default_path: str) -> str:
            raw = str(value or "").strip() or default_path
            if "://" in raw:
                return self.escape(raw)
            path = raw if raw.startswith("/") else f"/{raw.lstrip('/')}"
            if path == "/":
                absolute = f"{base_url.rstrip('/')}/" if base_url else "/"
            else:
                absolute = f"{base_url.rstrip('/')}{path}" if base_url else path
            return self.escape(absolute)

        seo_page_url = _resolve_absolute_url(seo_path, "/dashboard")
        seo_image_url = _resolve_absolute_url(
            seo_image_path,
            "/dashboard/static/image_web_bot/giveaways_dashboard.webp",
        )

        template = self.load_layout_template()
        if not template:
            return _strip_known_stray_layout_text(
                (
                f"<!DOCTYPE html><html lang=\"{resolved_lang}\"><head><meta charset=\"utf-8\">"
                f"<title>{resolved_title_html}</title></head><body class=\"page-{page_mode_html} ui-pro\">"
                "<div id=\"toast-container\"></div><div class=\"frame\">"
                f"{topbar_html}<main class=\"content\">{content_markup}</main></div>"
                f"<script type=\"application/json\" id=\"dashboard-bootstrap\">{dashboard_bootstrap_json}</script>"
                "<script src=\"/dashboard/static/dashboard/layout.js?v=20260520-13\" defer></script>"
                f"{i18n_script_tags}"
                "<script src=\"/dashboard/static/dashboard/layout-runtime.js?v=20260520-9\" defer></script>"
                "</body></html>"
                )
            )
        return _strip_known_stray_layout_text(
            template.replace("{{HTML_LANG}}", resolved_lang)
            .replace("{{TITLE}}", resolved_title_html)
            .replace("{{PAGE_MODE}}", page_mode_html)
            .replace("{{TOPBAR_HTML}}", topbar_html)
            .replace("{{CONTENT_MARKUP}}", content_markup)
            .replace("{{MAIN_CONTENT_HTML}}", main_content_html)
            .replace("{{SERVER_SWITCHER_PROFILE_HTML}}", server_switcher_profile_html)
            .replace("{{SERVER_SWITCHER_ITEMS_HTML}}", server_switcher_items_html)
            .replace("{{SIDEBAR_SERVER_NAME_HTML}}", sidebar_server_name_html)
            .replace("{{SIDEBAR_SERVER_ICON_URL}}", sidebar_server_icon_url)
            .replace("{{SIDEBAR_SERVER_ACCESS_HTML}}", sidebar_server_access_html)
            .replace("{{TOPBAR_CENTER_HTML}}", topbar_center_html)
            .replace("{{TOPBAR_ACTIONS_HTML}}", topbar_actions_html)
            .replace("{{SIDEBAR_MENU_HTML}}", sidebar_menu_html)
            .replace("{{DASHBOARD_BOOTSTRAP_JSON}}", dashboard_bootstrap_json)
            .replace("{{I18N_SCRIPT_TAGS}}", i18n_script_tags)
            .replace("{{SEO_PAGE_URL}}", seo_page_url)
            .replace("{{SEO_IMAGE_URL}}", seo_image_url)
            .replace("{{GLOBAL_COPYRIGHT_HTML}}", global_copyright_html)
        )
