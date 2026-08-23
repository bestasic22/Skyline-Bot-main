from __future__ import annotations

import ipaddress
import re
from typing import Any, Callable
from urllib.parse import urlparse

PROMOTE_DEFAULT_ALLOWED_DOMAINS: tuple[str, ...] = ("skylinebot.xyz",)


def is_safe_public_host(host: str) -> bool:
    host = str(host or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except Exception:
        pass
    return True


def _collect_unique(values: list[str], *, limit: int = 50) -> list[str]:
    unique: list[str] = []
    for item in values:
        token = str(item or "").strip()
        if not token or token in unique:
            continue
        unique.append(token)
        if len(unique) >= max(1, int(limit)):
            break
    return unique


def _split_tokens(raw: Any, *, clean_text_fn: Callable[[Any], str]) -> list[str]:
    if isinstance(raw, (list, tuple, set)):
        return [clean_text_fn(item) for item in raw]
    text = clean_text_fn(raw or "")
    return re.split(r"[\n\r,|]+", text)


def _normalize_domain_token(value: Any, *, clean_text_fn: Callable[[Any], str]) -> str:
    token = clean_text_fn(value).strip().lower()
    if not token:
        return ""
    if "://" in token:
        parsed = urlparse(token)
        token = (parsed.hostname or "").strip().lower()
    else:
        token = token.split("/", 1)[0].strip().lower()
    if token.startswith("www."):
        token = token[4:]
    if ":" in token:
        token = token.split(":", 1)[0].strip()
    if not token or token.endswith("."):
        return ""
    if not is_safe_public_host(token):
        return ""
    if not re.fullmatch(r"[a-z0-9.-]+", token):
        return ""
    return token


def normalize_promote_allowed_domains(
    raw: Any,
    *,
    clean_text_fn: Callable[[Any], str],
    limit: int = 30,
) -> list[str]:
    domains: list[str] = []
    for token in _split_tokens(raw, clean_text_fn=clean_text_fn):
        normalized = _normalize_domain_token(token, clean_text_fn=clean_text_fn)
        if normalized:
            domains.append(normalized)
    return _collect_unique(domains, limit=limit)


def normalize_promote_blocked_words(
    raw: Any,
    *,
    clean_text_fn: Callable[[Any], str],
    limit: int = 200,
) -> list[str]:
    words: list[str] = []
    for token in _split_tokens(raw, clean_text_fn=clean_text_fn):
        normalized = clean_text_fn(token).strip().lower()
        if not normalized:
            continue
        if len(normalized) > 64:
            normalized = normalized[:64]
        words.append(normalized)
    return _collect_unique(words, limit=limit)


def _normalize_url_prefix_token(value: Any, *, clean_text_fn: Callable[[Any], str]) -> str:
    token = clean_text_fn(value).strip()
    if not token:
        return ""
    normalized = token if "://" in token else f"https://{token}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").strip().lower()
    if not host or not is_safe_public_host(host):
        return ""
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    # Use canonical path-prefix form (no query/fragment) for consistent matching.
    path = path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def normalize_promote_allowed_urls(
    raw: Any,
    *,
    clean_text_fn: Callable[[Any], str],
    limit: int = 30,
) -> list[str]:
    prefixes: list[str] = []
    for token in _split_tokens(raw, clean_text_fn=clean_text_fn):
        normalized = _normalize_url_prefix_token(token, clean_text_fn=clean_text_fn)
        if normalized:
            prefixes.append(normalized)
    return _collect_unique(prefixes, limit=limit)


def normalize_promote_candidate_url(url: str, *, clean_text_fn: Callable[[Any], str]) -> str:
    raw = clean_text_fn(url).strip()
    if not raw:
        return ""
    normalized = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").strip().lower()
    if not host or not is_safe_public_host(host):
        return ""
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    out = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    if parsed.query:
        out = f"{out}?{parsed.query}"
    return out


def promote_default_allowed_domains() -> list[str]:
    return list(PROMOTE_DEFAULT_ALLOWED_DOMAINS)


def promote_allowed_url_targets(
    allowed_domains: Any,
    allowed_urls: Any,
    *,
    clean_text_fn: Callable[[Any], str],
    default_domains: tuple[str, ...] = PROMOTE_DEFAULT_ALLOWED_DOMAINS,
) -> tuple[list[str], list[str]]:
    custom_domains = normalize_promote_allowed_domains(allowed_domains, clean_text_fn=clean_text_fn)
    merged_domains = _collect_unique(
        [
            *[_normalize_domain_token(item, clean_text_fn=clean_text_fn) for item in list(default_domains or ())],
            *custom_domains,
        ],
        limit=60,
    )
    custom_urls = normalize_promote_allowed_urls(allowed_urls, clean_text_fn=clean_text_fn)
    return merged_domains, custom_urls


def promote_blocked_url_targets(
    blocked_domains: Any,
    blocked_urls: Any,
    *,
    clean_text_fn: Callable[[Any], str],
) -> tuple[list[str], list[str]]:
    domains = normalize_promote_allowed_domains(blocked_domains, clean_text_fn=clean_text_fn)
    urls = normalize_promote_allowed_urls(blocked_urls, clean_text_fn=clean_text_fn)
    return domains, urls


def is_allowed_promote_custom_url(
    url: str,
    *,
    allowed_domains: Any,
    allowed_urls: Any,
    clean_text_fn: Callable[[Any], str],
    default_domains: tuple[str, ...] = PROMOTE_DEFAULT_ALLOWED_DOMAINS,
) -> bool:
    normalized = normalize_promote_candidate_url(url, clean_text_fn=clean_text_fn)
    if not normalized:
        return False
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    domain_targets, url_targets = promote_allowed_url_targets(
        allowed_domains,
        allowed_urls,
        clean_text_fn=clean_text_fn,
        default_domains=default_domains,
    )
    for domain in domain_targets:
        if host == domain or host.endswith(f".{domain}"):
            return True
    normalized_base = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{(parsed.path or '/').rstrip('/') or '/'}"
    for prefix in url_targets:
        trimmed = prefix.rstrip("/")
        if normalized_base == prefix or normalized_base == trimmed:
            return True
        if normalized_base.startswith(f"{trimmed}/"):
            return True
    return False


def is_blocked_promote_custom_url(
    url: str,
    *,
    blocked_domains: Any,
    blocked_urls: Any,
    clean_text_fn: Callable[[Any], str],
) -> bool:
    normalized = normalize_promote_candidate_url(url, clean_text_fn=clean_text_fn)
    if not normalized:
        return False
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    domain_targets, url_targets = promote_blocked_url_targets(
        blocked_domains,
        blocked_urls,
        clean_text_fn=clean_text_fn,
    )
    for domain in domain_targets:
        if host == domain or host.endswith(f".{domain}"):
            return True
    normalized_base = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{(parsed.path or '/').rstrip('/') or '/'}"
    for prefix in url_targets:
        trimmed = prefix.rstrip("/")
        if normalized_base == prefix or normalized_base == trimmed:
            return True
        if normalized_base.startswith(f"{trimmed}/"):
            return True
    return False


def normalize_promote_attachment_url(
    url: str,
    *,
    clean_text_fn: Callable[[Any], str],
    allowed_extensions: tuple[str, ...],
    allowed_domains: tuple[str, ...],
) -> str:
    raw = clean_text_fn(url).strip()
    if not raw:
        return ""
    normalized = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if not is_safe_public_host(host):
        return ""
    path_lower = (parsed.path or "").lower()
    has_allowed_ext = any(path_lower.endswith(ext) for ext in allowed_extensions)
    is_allowed_domain = any(host == d or host.endswith(f".{d}") for d in allowed_domains)
    if not (has_allowed_ext or is_allowed_domain):
        return ""
    canonical_base = f"{parsed.scheme.lower()}://{(parsed.netloc or host).lower()}{parsed.path or ''}"
    if host in {"cdn.discordapp.com", "media.discordapp.net"} and path_lower.startswith("/attachments/"):
        # Discord signed params (`ex/is/hm`) expire; stable path keeps embeds renderable.
        return canonical_base
    if parsed.query:
        return f"{canonical_base}?{parsed.query}"
    return canonical_base


def validate_promote_content(
    content: str,
    blocked_words: list[str],
    *,
    hard_block_words: tuple[str, ...],
    clean_text_fn: Callable[[Any], str],
) -> tuple[bool, str]:
    text = clean_text_fn(content).strip().lower()
    if not text:
        return True, ""
    for word in blocked_words:
        if word and word in text:
            return False, f"พบคำที่ถูกบล็อก: `{word}`"
    for hard in hard_block_words:
        if hard in text:
            return False, f"ข้อความสุ่ม/อันตราย: `{hard}`"
    return True, ""


def promote_preview_script() -> str:
    return """
    <script>
      (function() {
        const imageExts = [".png", ".jpg", ".jpeg", ".jfif", ".pjp", ".pjpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".avif"];
        const isImageUrl = (url) => {
          const value = String(url || "").trim().toLowerCase();
          if (!value) return false;
          const clean = value.split("?")[0].split("#")[0];
          if (clean.includes("/dashboard/assets/db/")) return true;
          return imageExts.some((ext) => clean.endsWith(ext));
        };

        const forms = document.querySelectorAll('form[data-promote-preview="true"]');
        forms.forEach((form) => {
          const autoInviteEnabled = String(form.getAttribute('data-preview-auto-invite') || '0') === '1';
          const autoInviteText = String(form.getAttribute('data-preview-auto-invite-text') || '').trim() || 'Auto invite will be generated when sent';
          const contentInput = form.querySelector('[data-preview-content]');
          const attachmentsInput = form.querySelector('[data-preview-attachments]');
          const inviteInput = form.querySelector('[data-preview-invite]');
          const imageFileInput = form.querySelector('[data-preview-image-file]');
          const contentView = form.querySelector('[data-preview-content-view]');
          const inviteView = form.querySelector('[data-preview-invite-view]');
          const attachmentsWrap = form.querySelector('[data-preview-attachments-wrap]');
          const attachmentsView = form.querySelector('[data-preview-attachments-view]');
          const imageView = form.querySelector('[data-preview-image-view]');
          const imageCaption = form.querySelector('[data-preview-image-caption]');
          const openServerBtn = form.querySelector('[data-preview-open-server-btn]');
          const copyInviteBtn = form.querySelector('[data-preview-copy-invite-btn]');

          if (!contentInput || !attachmentsInput || !inviteInput || !contentView || !inviteView || !attachmentsView) {
            return;
          }

          let objectImageUrl = "";
          const clearObjectImageUrl = () => {
            if (objectImageUrl) {
              try {
                URL.revokeObjectURL(objectImageUrl);
              } catch (error) {
                // ignore URL revoke errors
              }
              objectImageUrl = "";
            }
          };

          const parseAttachments = () => (
            String(attachmentsInput.value || "")
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
              .slice(0, 5)
          );

          const setInviteButtons = (inviteUrl) => {
            const normalizedInvite = String(inviteUrl || '').trim();
            const hasInvite = Boolean(normalizedInvite) || autoInviteEnabled;
            const hasRealInvite = Boolean(normalizedInvite);
            if (openServerBtn) {
              openServerBtn.style.display = hasInvite ? "" : "none";
              openServerBtn.href = hasRealInvite ? normalizedInvite : "#";
              openServerBtn.style.pointerEvents = hasRealInvite ? "" : "none";
              openServerBtn.style.opacity = hasRealInvite ? "" : "0.7";
              openServerBtn.setAttribute("aria-disabled", hasRealInvite ? "false" : "true");
            }
            if (copyInviteBtn) {
              copyInviteBtn.style.display = hasInvite ? "" : "none";
              copyInviteBtn.disabled = !hasInvite;
            }
            if (copyInviteBtn && !copyInviteBtn.dataset.bound) {
              copyInviteBtn.dataset.bound = "1";
              copyInviteBtn.addEventListener("click", async () => {
                const value = String(copyInviteBtn.dataset.invite || "").trim();
                const autoMode = String(copyInviteBtn.dataset.auto || "0") === "1";
                const original = copyInviteBtn.dataset.label || copyInviteBtn.textContent || "";
                if (!value && autoMode) {
                  copyInviteBtn.textContent = "Auto on send";
                  window.setTimeout(() => {
                    copyInviteBtn.textContent = original;
                  }, 1200);
                  return;
                }
                if (!value) return;
                try {
                  await navigator.clipboard.writeText(value);
                  const oldText = copyInviteBtn.textContent || original;
                  copyInviteBtn.textContent = "Copied";
                  window.setTimeout(() => {
                    copyInviteBtn.textContent = oldText;
                  }, 1200);
                } catch (error) {
                  // clipboard may be blocked
                }
              });
            }
            if (copyInviteBtn) {
              if (!copyInviteBtn.dataset.label) {
                copyInviteBtn.dataset.label = copyInviteBtn.textContent || "";
              }
              copyInviteBtn.dataset.invite = normalizedInvite || "";
              copyInviteBtn.dataset.auto = (!normalizedInvite && autoInviteEnabled) ? "1" : "0";
            }
          };

          const setImagePreview = (attachments) => {
            let imageUrl = "";
            let imageLabel = "";
            const pickedFile = imageFileInput && imageFileInput.files && imageFileInput.files[0] ? imageFileInput.files[0] : null;
            if (pickedFile) {
              clearObjectImageUrl();
              objectImageUrl = URL.createObjectURL(pickedFile);
              imageUrl = objectImageUrl;
              imageLabel = `รูปที่เลือก: ${pickedFile.name}`;
            } else {
              clearObjectImageUrl();
              imageUrl = attachments.find((url) => isImageUrl(url)) || "";
              imageLabel = imageUrl ? "รูปจากลิงก์ไฟล์แนบ" : "";
            }
            if (imageView) {
              if (imageUrl) {
                imageView.src = imageUrl;
                imageView.style.display = "";
              } else {
                imageView.removeAttribute("src");
                imageView.style.display = "none";
              }
            }
            if (imageCaption) {
              if (imageLabel) {
                imageCaption.textContent = imageLabel;
                imageCaption.style.display = "";
              } else {
                imageCaption.textContent = "";
                imageCaption.style.display = "none";
              }
            }
            return imageUrl;
          };

          const render = () => {
            const esc = (value) => String(value || '')
              .replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#39;');
            const content = (contentInput.value || '').trim();
            const invite = (inviteInput.value || '').trim();
            const attachments = parseAttachments();
            const imageAttachment = setImagePreview(attachments);
            const nonImageAttachments = imageAttachment
              ? attachments.filter((url) => url !== imageAttachment)
              : attachments;

            contentView.textContent = content || '-';
            if (invite) {
              inviteView.textContent = `Invite: ${invite}`;
            } else if (autoInviteEnabled) {
              inviteView.textContent = `Invite: ${autoInviteText}`;
            } else {
              inviteView.textContent = 'Invite: -';
            }
            setInviteButtons(invite);

            if (attachmentsWrap) {
              attachmentsWrap.style.display = nonImageAttachments.length ? "" : "none";
            }
            attachmentsView.innerHTML = nonImageAttachments.length
              ? nonImageAttachments.map((url) => `<div style="margin:2px 0;">${esc(url)}</div>`).join('')
              : '';
          };

          contentInput.addEventListener('input', render);
          attachmentsInput.addEventListener('input', render);
          inviteInput.addEventListener('input', render);
          if (imageFileInput) {
            imageFileInput.addEventListener('change', render);
          }
          window.addEventListener('beforeunload', clearObjectImageUrl);
          render();
        });
      })();
    </script>
    """
