(() => {
  const TOKEN_RE = /<(a?):([A-Za-z0-9_]{2,32}):([0-9]{5,22})>/g;
  const TOKEN_SINGLE_RE = /^<(a?):([A-Za-z0-9_]{2,32}):([0-9]{5,22})>$/;
  const SKIP_TAGS = new Set([
    "SCRIPT",
    "STYLE",
    "TEXTAREA",
    "INPUT",
    "SELECT",
    "OPTION",
    "NOSCRIPT",
    "CODE",
    "PRE",
    "KBD",
    "SAMP",
  ]);
  const SKIP_CLASS_SELECTORS = [
    ".sb-emoji-picker",
    ".econ-emoji-picker",
    ".sb-emoji-btn",
  ];
  const STYLE_ID = "sb-discord-emoji-style";
  const EMOJI_CLASS = "sb-discord-emoji";

  let flushQueued = false;
  const pendingRoots = new Set();

  const parseToken = (raw) => {
    const value = String(raw || "").trim();
    const match = value.match(TOKEN_SINGLE_RE);
    if (!match) return null;
    return {
      animated: match[1] === "a",
      name: match[2],
      id: match[3],
      token: value,
    };
  };

  const buildEmojiUrl = (parsed, size = 48) => {
    if (!parsed) return "";
    const ext = parsed.animated ? "gif" : "png";
    return `https://cdn.discordapp.com/emojis/${parsed.id}.${ext}?size=${size}&quality=lossless`;
  };

  const ensureStyles = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .${EMOJI_CLASS}{
        display:inline-block;
        width:1.18em;
        height:1.18em;
        vertical-align:-0.2em;
        object-fit:contain;
        margin:0 .02em;
        pointer-events:none;
      }
    `;
    document.head.appendChild(style);
  };

  const createEmojiNode = (parsed) => {
    const img = document.createElement("img");
    img.className = EMOJI_CLASS;
    img.src = buildEmojiUrl(parsed, 48);
    img.alt = `:${parsed.name}:`;
    img.loading = "lazy";
    img.decoding = "async";
    img.draggable = false;
    img.setAttribute("data-discord-emoji-id", parsed.id);
    img.setAttribute("data-discord-emoji-name", parsed.name);
    if (parsed.animated) {
      img.setAttribute("data-discord-emoji-animated", "1");
    }
    return img;
  };

  const shouldSkipTextNode = (textNode) => {
    if (!(textNode instanceof Text)) return true;
    const parent = textNode.parentElement;
    if (!parent) return true;
    if (SKIP_TAGS.has(parent.tagName)) return true;
    if (parent.classList.contains(EMOJI_CLASS)) return true;
    if (parent.getAttribute("data-discord-emoji-skip") === "1") return true;
    for (const selector of SKIP_CLASS_SELECTORS) {
      if (parent.closest(selector)) return true;
    }
    return false;
  };

  const replaceTextNodeTokens = (textNode) => {
    if (shouldSkipTextNode(textNode)) return false;
    const source = String(textNode.nodeValue || "");
    if (!source || source.indexOf("<") === -1 || source.indexOf(":") === -1) return false;

    TOKEN_RE.lastIndex = 0;
    let match = TOKEN_RE.exec(source);
    if (!match) return false;

    const fragment = document.createDocumentFragment();
    let cursor = 0;

    while (match) {
      const start = match.index;
      const end = TOKEN_RE.lastIndex;

      if (start > cursor) {
        fragment.appendChild(document.createTextNode(source.slice(cursor, start)));
      }

      const parsed = {
        animated: match[1] === "a",
        name: match[2],
        id: match[3],
        token: match[0],
      };
      fragment.appendChild(createEmojiNode(parsed));

      cursor = end;
      match = TOKEN_RE.exec(source);
    }

    if (cursor < source.length) {
      fragment.appendChild(document.createTextNode(source.slice(cursor)));
    }

    if (!textNode.parentNode) return false;
    textNode.parentNode.replaceChild(fragment, textNode);
    return true;
  };

  const renderInRoot = (root) => {
    const scope =
      root instanceof Element || root instanceof DocumentFragment || root instanceof Document
        ? root
        : document.body;
    if (!scope) return;

    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    const candidates = [];
    while (walker.nextNode()) {
      const current = walker.currentNode;
      if (!(current instanceof Text)) continue;
      if (!current.nodeValue || current.nodeValue.indexOf("<") === -1) continue;
      candidates.push(current);
    }

    candidates.forEach((node) => {
      replaceTextNodeTokens(node);
    });
  };

  const flush = () => {
    flushQueued = false;
    const roots = Array.from(pendingRoots);
    pendingRoots.clear();

    if (!roots.length) {
      renderInRoot(document.body);
      return;
    }

    roots.forEach((root) => renderInRoot(root));
  };

  const queueRender = (root) => {
    if (root instanceof Text) {
      pendingRoots.add(root.parentElement || document.body);
    } else if (root instanceof Element || root instanceof DocumentFragment || root instanceof Document) {
      pendingRoots.add(root);
    } else {
      pendingRoots.add(document.body);
    }

    if (flushQueued) return;
    flushQueued = true;
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(flush);
    } else {
      window.setTimeout(flush, 16);
    }
  };

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === "characterData") {
        queueRender(mutation.target);
        return;
      }
      if (mutation.type !== "childList") return;
      if (mutation.addedNodes && mutation.addedNodes.length) {
        mutation.addedNodes.forEach((node) => {
          queueRender(node);
        });
      }
    });
  });

  const api = {
    parseCustomEmoji: parseToken,
    toUrl: (rawToken, size = 48) => {
      const parsed = typeof rawToken === "string" ? parseToken(rawToken) : rawToken;
      return buildEmojiUrl(parsed, size);
    },
    render: (root) => {
      renderInRoot(root || document.body);
    },
    queue: (root) => {
      queueRender(root || document.body);
    },
  };
  window.SBDiscordEmoji = api;

  ensureStyles();
  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      queueRender(document.body);
    });
  } else {
    queueRender(document.body);
  }
})();
