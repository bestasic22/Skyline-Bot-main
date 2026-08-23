(() => {
  const i18nRegistry =
    window.SKYLINE_DASHBOARD_I18N && typeof window.SKYLINE_DASHBOARD_I18N === "object"
      ? window.SKYLINE_DASHBOARD_I18N
      : {};
  const fallbackDict = i18nRegistry.th && typeof i18nRegistry.th === "object" ? i18nRegistry.th : {};

  function resolveLanguage() {
    const lang = String(document.documentElement.lang || "th").toLowerCase();
    return lang === "en" ? "en" : "th";
  }

  function t(key, fallback) {
    const lang = resolveLanguage();
    const activeDict =
      i18nRegistry[lang] && typeof i18nRegistry[lang] === "object"
        ? i18nRegistry[lang]
        : {};
    const translated = activeDict[key] ?? fallbackDict[key];
    return typeof translated === "string" && translated.trim()
      ? translated
      : String(fallback || "");
  }

  const FAVORITE_KEY = "skyline_cmd_help_favorites_v1";
  const state = {
    category: "",
    plan: "",
    status: "",
    query: "",
  };
  let favorites = new Set();

  const cards = Array.from(document.querySelectorAll("[data-command-card]"));
  const searchInput = document.getElementById("commandHelpSearch");
  const planFilter = document.getElementById("commandHelpPlanFilter");
  const statusFilter = document.getElementById("commandHelpStatusFilter");
  const emptyEl = document.getElementById("commandHelpEmpty");
  const favoriteWrap = document.getElementById("commandHelpFavoriteList");
  const clearFavoriteBtn = document.getElementById("commandHelpFavoriteClearBtn");
  const categoryChips = Array.from(document.querySelectorAll("[data-cat-chip]"));
  const presetButtons = Array.from(document.querySelectorAll("[data-filter-preset]"));

  function normalizeName(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/^\/+/, "")
      .replace(/\s+/g, " ");
  }

  function escapeSelectorValue(value) {
    const raw = String(value || "");
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(raw);
    }
    return raw.replace(/["\\]/g, "\\$&");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function loadFavorites() {
    try {
      const raw = localStorage.getItem(FAVORITE_KEY);
      const parsed = JSON.parse(raw || "[]");
      if (!Array.isArray(parsed)) {
        favorites = new Set();
        return;
      }
      favorites = new Set(parsed.map((item) => normalizeName(item)).filter(Boolean));
    } catch (_error) {
      favorites = new Set();
    }
  }

  function saveFavorites() {
    try {
      localStorage.setItem(FAVORITE_KEY, JSON.stringify(Array.from(favorites)));
    } catch (_error) {
      // Ignore storage write failures.
    }
  }

  function commandMetaFromCard(card) {
    const favButton = card.querySelector("[data-fav-toggle]");
    const title = card.querySelector(".cmdhelp-title");
    const brief = card.querySelector(".cmdhelp-brief");
    const statusBadge = card.querySelector(".cmdhelp-badge.status");
    const planBadge = card.querySelector(".cmdhelp-badge.plan");
    const modeBadge = card.querySelector(".cmdhelp-badge.mode");
    const name = normalizeName(favButton ? favButton.getAttribute("data-command-name") : "");
    const primaryUsage = String(card.getAttribute("data-primary-usage") || "").trim();

    return {
      name,
      title: title ? title.textContent.trim() : name,
      brief: brief ? brief.textContent.trim() : "",
      status: statusBadge ? statusBadge.textContent.trim() : "",
      plan: planBadge ? planBadge.textContent.trim() : "",
      mode: modeBadge ? modeBadge.textContent.trim() : "",
      primaryUsage,
    };
  }

  function applyFavoriteButtons() {
    document.querySelectorAll("[data-fav-toggle]").forEach((button) => {
      const name = normalizeName(button.getAttribute("data-command-name"));
      const active = Boolean(name) && favorites.has(name);
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.setAttribute(
        "title",
        active ? t("cmdhelp_fav_remove", "Remove favorite") : t("cmdhelp_fav_add", "Add favorite")
      );
    });
  }

  function renderFavoriteList() {
    if (!favoriteWrap) return;

    const cardsHtml = [];
    cards.forEach((card) => {
      const meta = commandMetaFromCard(card);
      if (!meta.name || !favorites.has(meta.name)) return;

      const copyValue = meta.primaryUsage || (meta.name ? `/${meta.name}` : "");
      const safeName = escapeHtml(meta.name);
      const safeTitle = escapeHtml(meta.title || meta.name);
      const safeBrief = escapeHtml(meta.brief || t("cmdhelp_no_description", "No description"));
      const safeMode = escapeHtml(meta.mode);
      const safePlan = escapeHtml(meta.plan);
      const safeStatus = escapeHtml(meta.status);
      const safeCopyValue = escapeHtml(copyValue);

      cardsHtml.push(`
        <article class="cmdhelp-favorite-card">
          <div class="cmdhelp-favorite-main">
            <strong>${safeTitle}</strong>
            <small>${safeBrief}</small>
            <small>${safeMode} | ${safePlan} | ${safeStatus}</small>
          </div>
          <div class="cmdhelp-favorite-actions">
            <button type="button" class="cmdhelp-favorite-btn" data-favorite-open="${safeName}">${escapeHtml(t("cmdhelp_open", "Open"))}</button>
            <button type="button" class="cmdhelp-favorite-btn" data-copy-command="${safeCopyValue}">${escapeHtml(t("cmdhelp_copy", "Copy"))}</button>
            <button type="button" class="cmdhelp-favorite-btn remove" data-favorite-remove="${safeName}">${escapeHtml(t("cmdhelp_remove", "Remove"))}</button>
          </div>
        </article>
      `);
    });

    favoriteWrap.innerHTML = cardsHtml.length
      ? cardsHtml.join("")
      : `<div class="notice">${escapeHtml(t("cmdhelp_no_favorites", "No favorites yet. Press heart on any command to pin it here."))}</div>`;

    if (clearFavoriteBtn) {
      clearFavoriteBtn.style.display = cardsHtml.length ? "" : "none";
    }
  }

  function focusCommand(name) {
    const normalized = normalizeName(name);
    if (!normalized) return;

    const selector = `[data-fav-toggle][data-command-name="${escapeSelectorValue(normalized)}"]`;
    const button = document.querySelector(selector);
    if (!button) return;

    const card = button.closest("[data-command-card]");
    if (!card) return;

    card.open = true;
    card.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function toggleFavorite(name) {
    const normalized = normalizeName(name);
    if (!normalized) return;

    if (favorites.has(normalized)) {
      favorites.delete(normalized);
    } else {
      favorites.add(normalized);
    }

    saveFavorites();
    applyFavoriteButtons();
    renderFavoriteList();
  }

  async function copyTextValue(value) {
    const text = String(value || "").trim();
    if (!text) return false;

    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (_error) {
        // Fall through to legacy method.
      }
    }

    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "readonly");
    helper.style.position = "fixed";
    helper.style.top = "-1000px";
    helper.style.left = "-1000px";
    document.body.appendChild(helper);
    helper.select();

    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (_error) {
      ok = false;
    }

    helper.remove();
    return ok;
  }

  function markCopied(button, ok) {
    if (!button) return;
    if (!button.dataset.copyLabel) {
      button.dataset.copyLabel = String(button.textContent || t("cmdhelp_copy", "Copy"));
    }

    button.textContent = ok ? t("cmdhelp_copied", "Copied") : t("cmdhelp_copy_failed", "Copy failed");
    button.classList.add("copied");

    window.setTimeout(() => {
      button.textContent = button.dataset.copyLabel || t("cmdhelp_copy", "Copy");
      button.classList.remove("copied");
    }, 1100);
  }

  function setCategory(nextCategory) {
    state.category = String(nextCategory || "");
    categoryChips.forEach((chip) => {
      const value = chip.getAttribute("data-cat-chip") || "";
      chip.classList.toggle("active", value === state.category);
    });
    filterCards();
  }

  function currentPresetKey() {
    if (!state.plan && !state.status) return "";
    if (!state.plan && state.status === "open") return "open";
    if (state.plan === "free" && !state.status) return "free";
    if (state.plan === "free" && state.status === "open") return "open_free";
    return "__custom__";
  }

  function syncPresetButtons() {
    const activeKey = currentPresetKey();
    presetButtons.forEach((button) => {
      const key = String(button.getAttribute("data-filter-preset") || "");
      button.classList.toggle("active", key === activeKey);
    });
  }

  function applyPreset(key) {
    const preset = String(key || "");
    if (preset === "open") {
      state.plan = "";
      state.status = "open";
    } else if (preset === "free") {
      state.plan = "free";
      state.status = "";
    } else if (preset === "open_free") {
      state.plan = "free";
      state.status = "open";
    } else {
      state.plan = "";
      state.status = "";
    }

    if (planFilter) planFilter.value = state.plan;
    if (statusFilter) statusFilter.value = state.status;
    syncPresetButtons();
    filterCards();
  }

  function filterCards() {
    const query = String(state.query || "").toLowerCase().trim();
    let visibleCount = 0;

    cards.forEach((card) => {
      const searchBlob = String(card.getAttribute("data-search") || "").toLowerCase();
      const category = card.getAttribute("data-category") || "";
      const plan = card.getAttribute("data-plan") || "";
      const status = card.getAttribute("data-status") || "";

      const matchCategory = !state.category || category === state.category;
      const matchPlan = !state.plan || plan === state.plan;
      const matchStatus = !state.status || status === state.status;
      const matchQuery = !query || searchBlob.includes(query);
      const visible = matchCategory && matchPlan && matchStatus && matchQuery;

      card.style.display = visible ? "" : "none";
      if (visible) visibleCount += 1;
    });

    if (emptyEl) {
      emptyEl.style.display = visibleCount ? "none" : "";
    }
  }

  categoryChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      setCategory(chip.getAttribute("data-cat-chip") || "");
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.query = searchInput.value || "";
      filterCards();
    });
  }

  if (planFilter) {
    planFilter.addEventListener("change", () => {
      state.plan = String(planFilter.value || "");
      syncPresetButtons();
      filterCards();
    });
  }

  if (statusFilter) {
    statusFilter.addEventListener("change", () => {
      state.status = String(statusFilter.value || "");
      syncPresetButtons();
      filterCards();
    });
  }

  presetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      applyPreset(button.getAttribute("data-filter-preset") || "");
    });
  });

  document.addEventListener("click", (event) => {
    const copyBtn = event.target.closest("[data-copy-command]");
    if (copyBtn) {
      event.preventDefault();
      event.stopPropagation();
      copyTextValue(copyBtn.getAttribute("data-copy-command")).then((ok) => markCopied(copyBtn, ok));
      return;
    }

    const favoriteToggle = event.target.closest("[data-fav-toggle]");
    if (favoriteToggle) {
      event.preventDefault();
      event.stopPropagation();
      toggleFavorite(favoriteToggle.getAttribute("data-command-name"));
      return;
    }

    const favoriteOpen = event.target.closest("[data-favorite-open]");
    if (favoriteOpen) {
      event.preventDefault();
      focusCommand(favoriteOpen.getAttribute("data-favorite-open"));
      return;
    }

    const favoriteRemove = event.target.closest("[data-favorite-remove]");
    if (favoriteRemove) {
      event.preventDefault();
      toggleFavorite(favoriteRemove.getAttribute("data-favorite-remove"));
    }
  });

  if (clearFavoriteBtn) {
    clearFavoriteBtn.addEventListener("click", () => {
      favorites = new Set();
      saveFavorites();
      applyFavoriteButtons();
      renderFavoriteList();
    });
  }

  loadFavorites();
  applyFavoriteButtons();
  renderFavoriteList();
  syncPresetButtons();
  setCategory("");

  window.addEventListener("dashboard:language-change", () => {
    applyFavoriteButtons();
    renderFavoriteList();
  });
})();
