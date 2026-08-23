from pathlib import Path
import re
from typing import Final

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter()

TRANSCRIPT_THEME_MARKER: Final[str] = 'id="skyline-transcript-theme"'
TRANSCRIPT_LANGUAGE_SWITCHER_MARKER: Final[str] = 'id="skyline-transcript-lang-switcher"'
TRANSCRIPT_THEME_STYLE: Final[str] = """
<style id="skyline-transcript-theme">
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Sora:wght@600;700&display=swap");

:root {
    --skyline-bg-1: #050b17;
    --skyline-bg-2: #111d38;
    --skyline-card: rgba(10, 16, 31, 0.76);
    --skyline-card-strong: rgba(14, 24, 44, 0.92);
    --skyline-border: rgba(131, 164, 255, 0.24);
    --skyline-border-hover: rgba(160, 190, 255, 0.48);
    --skyline-text-main: #ecf3ff;
    --skyline-text-muted: #a8bbdc;
    --skyline-accent: #7f9fff;
    --skyline-accent-2: #5fe2d2;
}

html,
body {
    background:
        radial-gradient(1200px 620px at 15% -10%, rgba(110, 132, 255, 0.2), transparent 55%),
        radial-gradient(1000px 500px at 100% 0%, rgba(95, 226, 210, 0.16), transparent 52%),
        linear-gradient(170deg, var(--skyline-bg-1), var(--skyline-bg-2)) !important;
    color: var(--skyline-text-main) !important;
    font-family: "IBM Plex Sans", "gg sans", "Segoe UI", sans-serif !important;
}

body::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px),
        linear-gradient(rgba(255, 255, 255, 0.018) 1px, transparent 1px);
    background-size: 36px 36px;
    mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.75), transparent 88%);
    z-index: -1;
}

.panel,
.main,
.footer {
    width: min(1140px, calc(100% - 28px));
    margin-left: auto !important;
    margin-right: auto !important;
}

.panel {
    position: sticky;
    top: 10px;
    z-index: 50;
    margin-top: 12px;
    margin-bottom: 12px;
    padding: 13px 18px !important;
    border: 1px solid var(--skyline-border);
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(18, 32, 62, 0.92), rgba(8, 15, 30, 0.9));
    box-shadow: 0 20px 42px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(12px);
}

.panel span:first-of-type {
    font-family: "Sora", "IBM Plex Sans", sans-serif;
    letter-spacing: 0.02em;
}

.panel__hashtag-icon {
    filter: drop-shadow(0 6px 12px rgba(112, 166, 255, 0.35));
}

.panel__channel-topic {
    border-color: rgba(169, 196, 255, 0.3) !important;
    color: var(--skyline-text-muted) !important;
}

.panel__summary-button {
    margin-right: 0 !important;
    padding: 8px 12px;
    border: 1px solid rgba(155, 182, 255, 0.45);
    border-radius: 11px;
    background: linear-gradient(135deg, rgba(126, 163, 255, 0.25), rgba(95, 226, 210, 0.18));
    color: var(--skyline-text-main) !important;
    transition: transform 0.15s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.panel__summary-button:hover {
    transform: translateY(-1px);
    border-color: rgba(192, 213, 255, 0.75);
    box-shadow: 0 10px 20px rgba(90, 126, 245, 0.25);
}

.main {
    height: calc(100dvh - 208px) !important;
    min-height: 420px;
    margin-bottom: 14px;
    border: 1px solid rgba(128, 158, 242, 0.22);
    border-radius: 22px;
    background: linear-gradient(165deg, rgba(10, 18, 35, 0.86), rgba(5, 10, 22, 0.86));
    box-shadow: 0 24px 50px rgba(2, 4, 8, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04);
    scrollbar-color: #5b78b8 rgba(15, 24, 46, 0.4);
    scrollbar-width: thin;
}

.main::-webkit-scrollbar {
    width: 9px;
}

.main::-webkit-scrollbar-thumb {
    border-radius: 10px;
    background: linear-gradient(180deg, rgba(129, 163, 255, 0.85), rgba(95, 226, 210, 0.85));
}

.buffer {
    min-height: clamp(20px, 4vh, 56px);
}

.info {
    margin: 0 20px !important;
    padding-bottom: 14px !important;
}

.info__title {
    font-family: "Sora", "IBM Plex Sans", sans-serif;
    font-size: clamp(1.5rem, 1.1rem + 1.5vw, 2rem) !important;
    letter-spacing: 0.015em;
}

.info__subject,
.info__channel-message-count {
    color: var(--skyline-text-muted) !important;
}

.chatlog {
    margin: 0 14px 10px;
    padding: 0 3px 8px;
    border-top: none !important;
}

.chatlog__message-group {
    margin-bottom: 0.7rem !important;
}

.chatlog__message-container {
    margin-bottom: 8px;
    overflow: hidden;
    border: 1px solid rgba(123, 152, 240, 0.2);
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(18, 30, 56, 0.42), rgba(10, 17, 33, 0.35));
    backdrop-filter: blur(4px);
    transition: transform 0.16s ease, border-color 0.2s ease, background-color 0.2s ease;
}

.chatlog__message-container:hover {
    transform: translateY(-1px);
    border-color: var(--skyline-border-hover);
    background: linear-gradient(180deg, rgba(23, 39, 72, 0.58), rgba(13, 22, 43, 0.52));
}

.chatlog__message {
    padding: 12px !important;
}

.chatlog__message-aside {
    min-width: 54px;
}

.chatlog__avatar {
    width: 40px !important;
    height: 40px !important;
    border-radius: 12px;
    border: 1px solid rgba(159, 187, 255, 0.35);
    box-shadow: 0 10px 18px rgba(0, 0, 0, 0.35);
}

.chatlog__author-name {
    font-weight: 700 !important;
    letter-spacing: 0.01em;
}

.chatlog__timestamp,
.chatlog__short-timestamp,
.chatlog__reference-edited-timestamp {
    color: #abc0e6 !important;
}

.chatlog__content,
.chatlog__markdown,
.markdown {
    color: var(--skyline-text-main) !important;
}

.pre,
.pre--inline {
    background: rgba(3, 8, 19, 0.86) !important;
    border-color: rgba(143, 176, 255, 0.22) !important;
}

.mention {
    background: rgba(127, 159, 255, 0.2) !important;
}

.quote {
    --quote-bar-color: rgba(126, 161, 255, 0.65);
}

.chatlog__attachment-thumbnail,
.chatlog__sticker {
    border-radius: 12px !important;
    border: 1px solid rgba(176, 201, 255, 0.25);
    box-shadow: 0 14px 24px rgba(0, 0, 0, 0.36);
}

.chatlog__reaction {
    background-color: rgba(66, 87, 136, 0.2) !important;
    border-color: rgba(146, 176, 252, 0.25) !important;
}

.chatlog__reaction-count {
    color: #d6e3ff !important;
}

.footer {
    height: auto !important;
    margin-bottom: 16px !important;
    padding: 14px 16px !important;
    border-radius: 16px;
    border: 1px solid rgba(127, 157, 240, 0.26);
    background: linear-gradient(160deg, rgba(15, 26, 48, 0.92), rgba(8, 15, 30, 0.92));
    box-shadow: 0 14px 32px rgba(0, 0, 0, 0.34);
}

.footer__text {
    color: var(--skyline-text-muted) !important;
}

#context-menu,
.summary-popout,
.meta-popout {
    border: 1px solid rgba(147, 177, 255, 0.28);
    border-radius: 14px !important;
    background: var(--skyline-card-strong) !important;
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(14px);
}

.summary-popout,
.meta-popout {
    width: min(320px, calc(100vw - 18px)) !important;
}

.meta__divider,
.meta__divider-2 {
    background-color: rgba(155, 181, 236, 0.38) !important;
}

.meta__title {
    color: var(--skyline-text-muted) !important;
}

@media (max-width: 900px) {
    .panel,
    .main,
    .footer {
        width: calc(100% - 16px);
    }

    .panel {
        top: 8px;
        padding: 10px 13px !important;
        border-radius: 14px;
        font-size: 17px;
    }

    .panel__channel-topic {
        display: none;
    }

    .panel__summary-button {
        padding: 6px 10px;
        font-size: 13px;
    }

    .main {
        height: calc(100dvh - 190px) !important;
        min-height: 360px;
        border-radius: 16px;
    }

    .chatlog {
        margin: 0 8px 8px;
    }

    .chatlog__message {
        padding: 10px !important;
    }

    .chatlog__attachment-thumbnail {
        max-width: 100%;
        height: auto;
    }
}

@media (max-width: 560px) {
    html,
    body {
        font-size: 15px !important;
    }

    .panel {
        flex-wrap: wrap;
        gap: 6px;
    }

    .panel__summary-button {
        margin-left: auto;
    }

    .main {
        height: calc(100dvh - 205px) !important;
    }

    .chatlog__message-container {
        border-radius: 12px;
    }
}
</style>
"""
TRANSCRIPT_LANGUAGE_SWITCHER_BLOCK: Final[str] = r"""
<div id="skyline-transcript-lang-switcher" data-no-auto-i18n="1">
  <button type="button" id="skyline-transcript-lang-switcher-btn" aria-label="Switch language" title="Switch language">
    <span aria-hidden="true">&#127760;</span>
    <span id="skyline-transcript-lang-switcher-label">EN</span>
  </button>
</div>
<style id="skyline-transcript-lang-switcher-style">
  #skyline-transcript-lang-switcher {
    position: fixed;
    right: 12px;
    bottom: 12px;
    z-index: 9999;
  }
  #skyline-transcript-lang-switcher-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 36px;
    border-radius: 999px;
    border: 1px solid rgba(141, 178, 255, 0.54);
    padding: 7px 12px;
    background: linear-gradient(135deg, rgba(35, 68, 138, 0.95), rgba(44, 114, 214, 0.93));
    color: #f3f8ff;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    line-height: 1;
    cursor: pointer;
    box-shadow: 0 16px 30px rgba(6, 15, 34, 0.45);
  }
  #skyline-transcript-lang-switcher-btn:hover {
    filter: brightness(1.06);
    transform: translateY(-1px);
  }
</style>
<script id="skyline-transcript-lang-switcher-script">
  (() => {
    const button = document.getElementById("skyline-transcript-lang-switcher-btn");
    const label = document.getElementById("skyline-transcript-lang-switcher-label");
    if (!(button instanceof HTMLButtonElement) || !(label instanceof HTMLElement)) return;

    const readCookieLang = () => {
      const cookies = String(document.cookie || "").split(";").map((part) => part.trim());
      for (const item of cookies) {
        if (!item.toLowerCase().startsWith("skyline_lang=")) continue;
        const value = item.slice("skyline_lang=".length).trim().toLowerCase();
        return value === "en" ? "en" : "th";
      }
      return "";
    };
    const htmlLang = String((document.documentElement && document.documentElement.lang) || "").toLowerCase();
    let currentLang = readCookieLang() || (htmlLang.startsWith("en") ? "en" : "th");
    if (currentLang !== "en") currentLang = "th";

    const syncLabel = () => {
      const nextLang = currentLang === "en" ? "th" : "en";
      label.textContent = nextLang.toUpperCase();
      const title = nextLang === "en" ? "Switch to English" : "Switch to Thai";
      button.setAttribute("aria-label", title);
      button.setAttribute("title", title);
    };

    button.addEventListener("click", () => {
      const targetLang = currentLang === "en" ? "th" : "en";
      const currentPath = window.location && window.location.pathname ? window.location.pathname : "/";
      const suffixPath = String(currentPath || "/").replace(/^\/(?:th|en)(?=\/|$)/i, "") || "/";
      const normalizedSuffix = suffixPath.startsWith("/") ? suffixPath : "/" + suffixPath;
      const search = window.location && window.location.search ? window.location.search : "";
      const hash = window.location && window.location.hash ? window.location.hash : "";
      window.location.assign("/" + targetLang + normalizedSuffix + search + hash);
    });

    syncLabel();
  })();
</script>
"""


def _enhance_transcript_html(html_content: str) -> str:
    enhanced = str(html_content or "")

    if TRANSCRIPT_THEME_MARKER not in enhanced:
        if "</head>" in enhanced:
            enhanced = enhanced.replace("</head>", f"{TRANSCRIPT_THEME_STYLE}\n</head>", 1)
        elif "<body>" in enhanced:
            enhanced = enhanced.replace("<body>", f"{TRANSCRIPT_THEME_STYLE}\n<body>", 1)
        else:
            enhanced = f"{TRANSCRIPT_THEME_STYLE}\n{enhanced}"

    if TRANSCRIPT_LANGUAGE_SWITCHER_MARKER not in enhanced:
        if "</body>" in enhanced:
            enhanced = enhanced.replace("</body>", f"{TRANSCRIPT_LANGUAGE_SWITCHER_BLOCK}\n</body>", 1)
        elif "</html>" in enhanced:
            enhanced = enhanced.replace("</html>", f"{TRANSCRIPT_LANGUAGE_SWITCHER_BLOCK}\n</html>", 1)
        else:
            enhanced = f"{enhanced}\n{TRANSCRIPT_LANGUAGE_SWITCHER_BLOCK}"

    return enhanced


@router.get("/transcripts/{transcript_unique_id}")
async def get_transcript(transcript_unique_id: str):
    transcripts_dir = Path(__file__).resolve().parents[3] / "transcripts"
    safe_name = transcript_unique_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", safe_name):
        raise HTTPException(status_code=400, detail="Invalid transcript id")

    candidates = [safe_name]
    if not safe_name.endswith(".html"):
        candidates.append(f"{safe_name}.html")

    file_path = None
    for candidate in candidates:
        current = (transcripts_dir / candidate).resolve()
        if transcripts_dir.resolve() in current.parents and current.exists():
            file_path = current
            break

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as file_handle:
                html_content = file_handle.read()
                return HTMLResponse(content=_enhance_transcript_html(html_content), status_code=200)
        except Exception as error:
            raise HTTPException(status_code=500, detail="Internal Server Error") from error

    raise HTTPException(status_code=404, detail="Transcript not found")
