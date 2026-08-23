(() => {
  const boot = typeof __BOOT === "object" && __BOOT ? __BOOT : {};
  const payload =
    boot && typeof boot.emojiPicker === "object" && boot.emojiPicker
      ? boot.emojiPicker
      : {};

  let customGuilds = Array.isArray(payload.customGuilds)
    ? payload.customGuilds
    : [];
  let unicodeEmojis = Array.isArray(payload.unicodeEmojis)
    ? payload.unicodeEmojis
    : [];
  const emojiDataEndpoint = String(payload.endpoint || "").trim();
  const canLazyLoadEmojiData = Boolean(emojiDataEndpoint);
  const hasEmojiRows = (guildRows, unicodeRows) =>
    guildRows.some((item) => {
      if (!item || typeof item !== "object") return false;
      return (
        Array.isArray(item.emojis) &&
        item.emojis.some((emoji) => emoji && typeof emoji === "object")
      );
    }) ||
    unicodeRows.length > 0;
  let hasAnyEmojiData = hasEmojiRows(customGuilds, unicodeEmojis);
  let lazyEmojiPayloadPromise = null;

  if (!hasAnyEmojiData && !canLazyLoadEmojiData) {
    return;
  }

  const WRAP_CLASS = "sb-emoji-input-wrap";
  const TOGGLE_CLASS = "sb-emoji-toggle";
  const TOGGLE_ICON_HTML =
    '<i class="fa-regular fa-face-smile" aria-hidden="true"></i>';

  let picker = null;
  let pickerSearchInput = null;
  let pickerList = null;
  let activeInput = null;
  let activeToggle = null;
  let searchableButtons = [];
  let serverGroups = [];
  const resolveUiLang = () =>
    String(document.documentElement.lang || "").toLowerCase().startsWith("en")
      ? "en"
      : "th";
  const uiText = (key) => {
    const lang = resolveUiLang();
    const dict = {
      searchPlaceholder: {
        en: "Search emojis...",
        th: "ค้นหาอีโมจิ...",
      },
      pickEmoji: {
        en: "Pick emoji",
        th: "เลือกอีโมจิ",
      },
    };
    const value = dict[key];
    if (!value || typeof value !== "object") return "";
    return String(value[lang] || value.th || "");
  };

  const isEmojiCandidateInput = (node) => {
    const isTextInput =
      node instanceof HTMLInputElement &&
      ["text", "search"].includes(String(node.type || "").toLowerCase());
    const isTextArea = node instanceof HTMLTextAreaElement;
    if (!isTextInput && !isTextArea) return false;
    if (node.disabled || node.readOnly) return false;
    if (node.dataset.emojiPickerDisabled === "1") return false;
    if (node.closest(".econ-emoji-input-wrap")) return false;
    if (node.closest(".econ-emoji-picker")) return false;
    if (node.closest(".sb-emoji-picker")) return false;

    const token = [
      node.name,
      node.id,
      node.className,
      node.getAttribute("placeholder"),
      node.getAttribute("data-opt-field"),
      node.getAttribute("aria-label"),
    ]
      .map((item) => String(item || "").toLowerCase())
      .join(" ");

    if (node.dataset.emojiPicker === "1") return true;
    if (token.includes("emoji")) return true;
    if (token.includes("emote")) return true;
    if (token.includes("reaction")) return true;
    if (token.includes("symbol")) return true;
    if (token.includes("badge")) return true;
    if (token.includes("<:") || token.includes("unicode")) return true;
    return false;
  };

  const parseCustomEmoji = (raw) => {
    const token = String(raw || "").trim();
    if (!token.startsWith("<") || !token.endsWith(">")) return null;
    const body = token.slice(1, -1);
    const parts = body.split(":");
    if (parts.length !== 3) return null;
    let animated = false;
    let name = "";
    let id = "";
    if (parts[0] === "a") {
      animated = true;
      name = String(parts[1] || "").trim();
      id = String(parts[2] || "").trim();
    } else if (parts[0] === "") {
      name = String(parts[1] || "").trim();
      id = String(parts[2] || "").trim();
    } else {
      return null;
    }
    if (!/^[0-9]{5,}$/.test(id)) return null;
    if (!name) return null;
    return { animated, name, id };
  };

  const escapeHtml = (raw) => {
    return String(raw || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  const normalizeInputValueForTarget = (targetInput, rawValue) => {
    let value = String(rawValue || "").trim();
    const maxLengthRaw = Number(
      targetInput.getAttribute("maxlength") || targetInput.maxLength || 0
    );
    const maxLength = Number.isFinite(maxLengthRaw) ? maxLengthRaw : 0;
    const parsed = parseCustomEmoji(value);
    if (parsed && maxLength > 0 && maxLength < value.length) {
      return String(targetInput.value || "").trim();
    }
    if (maxLength > 0) {
      value = value.slice(0, maxLength);
    }
    return value;
  };

  const createButton = (value, searchText, htmlContent, title) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sb-emoji-btn";
    button.setAttribute("data-value", String(value || ""));
    button.setAttribute("data-search", String(searchText || "").toLowerCase());
    button.title = String(title || "");
    button.innerHTML = htmlContent;
    button.addEventListener("click", () => {
      if (
        !(activeInput instanceof HTMLInputElement) &&
        !(activeInput instanceof HTMLTextAreaElement)
      ) {
        return;
      }
      const nextValue = normalizeInputValueForTarget(
        activeInput,
        button.getAttribute("data-value") || ""
      );
      activeInput.value = nextValue;
      activeInput.dispatchEvent(new Event("input", { bubbles: true }));
      activeInput.dispatchEvent(new Event("change", { bubbles: true }));
      closePicker();
    });
    searchableButtons.push(button);
    return button;
  };

  const showPickerMessage = (message) => {
    if (!pickerList) return;
    pickerList.innerHTML = "";
    const node = document.createElement("div");
    node.className = "sb-emoji-muted";
    node.textContent = String(message || "");
    pickerList.appendChild(node);
  };

  const fetchEmojiPayload = async () => {
    if (!canLazyLoadEmojiData || !emojiDataEndpoint) {
      return false;
    }
    try {
      const response = await fetch(emojiDataEndpoint, {
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!response.ok) {
        return false;
      }
      const responsePayload = await response.json();
      const nextCustomGuilds = Array.isArray(responsePayload?.custom_guilds)
        ? responsePayload.custom_guilds
        : [];
      const nextUnicodeEmojis = Array.isArray(responsePayload?.unicode_emojis)
        ? responsePayload.unicode_emojis
        : [];
      customGuilds = nextCustomGuilds;
      unicodeEmojis = nextUnicodeEmojis;
      hasAnyEmojiData = hasEmojiRows(customGuilds, unicodeEmojis);
      return hasAnyEmojiData;
    } catch (_error) {
      return false;
    }
  };

  const ensureEmojiPayload = async () => {
    if (hasAnyEmojiData) return true;
    if (!canLazyLoadEmojiData) return false;
    if (!lazyEmojiPayloadPromise) {
      lazyEmojiPayloadPromise = fetchEmojiPayload();
    }
    const ok = await lazyEmojiPayloadPromise;
    lazyEmojiPayloadPromise = null;
    return Boolean(ok);
  };

  const createPickerShell = () => {
    if (picker) return;
    picker = document.createElement("div");
    picker.className = "sb-emoji-picker";
    picker.setAttribute("aria-hidden", "true");

    const searchInput = document.createElement("input");
    searchInput.type = "search";
    searchInput.className = "sb-emoji-search";
    searchInput.placeholder = uiText("searchPlaceholder");
    searchInput.setAttribute("data-no-auto-i18n", "1");
    searchInput.autocomplete = "off";
    searchInput.addEventListener("input", () => {
      applySearch(searchInput.value || "");
    });
    pickerSearchInput = searchInput;

    const list = document.createElement("div");
    list.className = "sb-emoji-list";
    pickerList = list;

    picker.appendChild(searchInput);
    picker.appendChild(list);
    picker.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    document.body.appendChild(picker);

    if (hasAnyEmojiData) {
      buildPickerSections();
    } else {
      showPickerMessage("Loading emojis...");
    }
  };

  const buildPickerSections = () => {
    if (!pickerList) return;
    pickerList.innerHTML = "";
    searchableButtons = [];
    serverGroups = [];

    const guildTitle = document.createElement("div");
    guildTitle.className = "sb-emoji-title";
    const customCount = customGuilds.reduce((sum, group) => {
      if (!group || typeof group !== "object") return sum;
      const emojis = Array.isArray(group.emojis) ? group.emojis : [];
      return sum + emojis.length;
    }, 0);
    guildTitle.textContent = `SERVER EMOJIS (${customCount})`;
    pickerList.appendChild(guildTitle);

    if (!customGuilds.length) {
      const emptyGuildNotice = document.createElement("div");
      emptyGuildNotice.className = "sb-emoji-muted";
      emptyGuildNotice.textContent = "No guilds were found.";
      pickerList.appendChild(emptyGuildNotice);
    } else {
      customGuilds.forEach((group) => {
        if (!group || typeof group !== "object") return;
        const guildName =
          String(group.name || group.id || "Unknown Guild").trim() ||
          "Unknown Guild";
        const guildId = String(group.id || "").trim();
        const emojis = Array.isArray(group.emojis) ? group.emojis : [];

        const section = document.createElement("section");
        section.className = "sb-emoji-server-group";
        section.setAttribute("data-server", guildName.toLowerCase());

        const head = document.createElement("div");
        head.className = "sb-emoji-server-head";

        const nameNode = document.createElement("span");
        nameNode.className = "sb-emoji-server-name";
        nameNode.textContent = guildName;

        const countNode = document.createElement("span");
        countNode.className = "sb-emoji-count";
        countNode.textContent = `${emojis.length} emojis`;

        head.appendChild(nameNode);
        head.appendChild(countNode);
        section.appendChild(head);

        if (!emojis.length) {
          const emptyNode = document.createElement("div");
          emptyNode.className = "sb-emoji-muted";
          emptyNode.textContent = "No custom emojis available in this guild.";
          section.appendChild(emptyNode);
        } else {
          const grid = document.createElement("div");
          grid.className = "sb-emoji-grid";
          emojis.forEach((emoji) => {
            if (!emoji || typeof emoji !== "object") return;
            const emojiId = String(emoji.id || "").trim();
            const emojiName = String(emoji.name || "emoji").trim() || "emoji";
            if (!emojiId) return;
            const animated = Boolean(emoji.animated);
            const value = `<${animated ? "a" : ""}:${emojiName}:${emojiId}>`;
            let emojiUrl = String(emoji.url || "").trim();
            if (!emojiUrl) {
              const ext = animated ? "gif" : "png";
              emojiUrl = `https://cdn.discordapp.com/emojis/${emojiId}.${ext}?size=64&quality=lossless`;
            }
            const button = createButton(
              value,
              `${emojiName} ${guildName} ${guildId} ${emojiId}`,
              `<img src="${escapeHtml(emojiUrl)}" alt="${escapeHtml(emojiName)}">`,
              emojiName
            );
            grid.appendChild(button);
          });
          section.appendChild(grid);
        }

        pickerList.appendChild(section);
        serverGroups.push(section);
      });
    }

    const unicodeTitle = document.createElement("div");
    unicodeTitle.className = "sb-emoji-title";
    unicodeTitle.textContent = "DISCORD EMOJIS";
    pickerList.appendChild(unicodeTitle);

    const unicodeGrid = document.createElement("div");
    unicodeGrid.className = "sb-emoji-grid";
    unicodeEmojis.forEach((item) => {
      if (!item || typeof item !== "object") return;
      const value = String(item.value || "").trim();
      if (!value) return;
      const aliases = String(item.aliases || "").trim();
      const button = createButton(
        value,
        `${value} ${aliases}`,
        value,
        value
      );
      unicodeGrid.appendChild(button);
    });
    pickerList.appendChild(unicodeGrid);
  };

  const isOpen = () =>
    picker instanceof HTMLElement && picker.classList.contains("show");

  const positionPicker = () => {
    if (!picker || !activeToggle || !isOpen()) return;
    const rect = activeToggle.getBoundingClientRect();
    const pickerWidth = Math.min(430, window.innerWidth - 24);
    const maxHeight = 420;
    let left = Math.round(rect.right - pickerWidth);
    if (left < 12) left = 12;
    const rightBound = window.innerWidth - 12 - pickerWidth;
    if (left > rightBound) left = Math.max(12, rightBound);

    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const shouldFlip = spaceBelow < 260 && spaceAbove > spaceBelow;
    let top = rect.bottom + 8;
    if (shouldFlip) {
      top = Math.max(12, rect.top - Math.min(maxHeight, spaceAbove) - 8);
    }
    picker.style.left = `${left}px`;
    picker.style.top = `${Math.round(top)}px`;
    picker.style.maxHeight = `${Math.max(120, Math.min(maxHeight, shouldFlip ? spaceAbove : spaceBelow))}px`;
  };

  const closePicker = () => {
    if (!picker) return;
    picker.classList.remove("show");
    picker.setAttribute("aria-hidden", "true");
    if (activeToggle) {
      activeToggle.setAttribute("aria-expanded", "false");
    }
    activeInput = null;
    activeToggle = null;
  };

  const openPicker = async (input, toggle) => {
    createPickerShell();
    if (!picker) return;
    activeInput = input;
    activeToggle = toggle;
    picker.classList.add("show");
    picker.setAttribute("aria-hidden", "false");
    toggle.setAttribute("aria-expanded", "true");
    if (pickerSearchInput) {
      pickerSearchInput.value = "";
      applySearch("");
    }
    positionPicker();
    if (!hasAnyEmojiData) {
      showPickerMessage("Loading emojis...");
      const loaded = await ensureEmojiPayload();
      if (!isOpen() || activeInput !== input) {
        return;
      }
      if (loaded) {
        buildPickerSections();
        if (pickerSearchInput) {
          applySearch(pickerSearchInput.value || "");
        }
      } else {
        showPickerMessage("Cannot load emojis now.");
      }
      positionPicker();
    }
    if (pickerSearchInput) {
      try {
        pickerSearchInput.focus({ preventScroll: true });
      } catch (_error) {
        pickerSearchInput.focus();
      }
    }
  };

  const applySearch = (query) => {
    const q = String(query || "").toLowerCase().trim();
    searchableButtons.forEach((button) => {
      const src = String(button.getAttribute("data-search") || "");
      const visible = !q || src.includes(q);
      button.classList.toggle("is-hidden", !visible);
    });
    serverGroups.forEach((group) => {
      const hasVisible = Array.from(
        group.querySelectorAll(".sb-emoji-btn")
      ).some((button) => !button.classList.contains("is-hidden"));
      if (q && !hasVisible) {
        group.style.display = "none";
      } else {
        group.style.display = "";
      }
    });
  };

  const enhanceInput = (input) => {
    if (!isEmojiCandidateInput(input)) return;
    if (input.dataset.emojiPickerBound === "1") return;
    input.dataset.emojiPickerBound = "1";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = `ghost-btn ${TOGGLE_CLASS} toggleEmojiPicker`;
    const pickEmojiText = uiText("pickEmoji");
    toggle.title = pickEmojiText;
    toggle.setAttribute("aria-label", pickEmojiText);
    toggle.setAttribute("data-no-auto-i18n", "1");
    toggle.setAttribute("aria-expanded", "false");
    toggle.innerHTML = TOGGLE_ICON_HTML;
    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (isOpen() && activeInput === input) {
        closePicker();
      } else {
        openPicker(input, toggle);
      }
    });

    const parent = input.parentElement;
    if (parent && parent.classList.contains(WRAP_CLASS)) {
      parent.appendChild(toggle);
      return;
    }
    if (!parent) return;

    const wrap = document.createElement("div");
    wrap.className = WRAP_CLASS;
    parent.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(toggle);
  };

  const scanAndEnhance = (root) => {
    const scope = root instanceof Element || root instanceof Document ? root : document;
    scope
      .querySelectorAll('input[type="text"], input[type="search"], textarea')
      .forEach((node) => enhanceInput(node));
  };
  const refreshLocalizedCopy = () => {
    const searchPlaceholder = uiText("searchPlaceholder");
    if (pickerSearchInput instanceof HTMLInputElement) {
      pickerSearchInput.placeholder = searchPlaceholder;
    }
    const pickEmojiText = uiText("pickEmoji");
    document.querySelectorAll(`button.${TOGGLE_CLASS}`).forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) return;
      button.title = pickEmojiText;
      button.setAttribute("aria-label", pickEmojiText);
      button.setAttribute("data-no-auto-i18n", "1");
    });
  };

  document.addEventListener("click", (event) => {
    if (!isOpen()) return;
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (picker && picker.contains(target)) return;
    if (activeToggle && activeToggle.contains(target)) return;
    closePicker();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePicker();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) closePicker();
  });
  window.addEventListener("resize", () => {
    positionPicker();
  });
  window.addEventListener(
    "scroll",
    () => {
      positionPicker();
    },
    true
  );

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (!mutation.addedNodes || !mutation.addedNodes.length) return;
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof Element)) return;
        if (node.matches('input[type="text"], input[type="search"], textarea')) {
          enhanceInput(node);
        }
        scanAndEnhance(node);
      });
    });
  });
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      scanAndEnhance(document);
      refreshLocalizedCopy();
    });
  } else {
    scanAndEnhance(document);
    refreshLocalizedCopy();
  }
  window.addEventListener("dashboard:language-change", () => {
    refreshLocalizedCopy();
  });
})();
