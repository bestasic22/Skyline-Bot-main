(function () {
  const ICON_BY_KEY = Object.freeze({
    overview: "bi-speedometer2",
    dashboard: "bi-grid-1x2-fill",
    home: "bi-house-door",
    server_settings: "bi-sliders",
    embed_messages: "bi-chat-left-text",
    premium_receive: "bi-gem",
    tools: "bi-tools",
    welcome_center: "bi-person-hearts",
    welcome: "bi-person-hearts",
    leaver: "bi-box-arrow-right",
    auto_reply_center: "bi-reply-all",
    economy: "bi-cash-stack",
    levels: "bi-graph-up-arrow",
    autoroles: "bi-people",
    colors: "bi-palette",
    reaction_roles: "bi-emoji-smile",
    starboard: "bi-stars",
    join_to_create: "bi-broadcast",
    temp_channels: "bi-broadcast",
    temp_links: "bi-link-45deg",
    statistics_plus: "bi-bar-chart-line",
    screening: "bi-shield-lock",
    screening_categories: "bi-collection",
    automation: "bi-cpu",
    anti_raid: "bi-shield-exclamation",
    extra_protection: "bi-shield-check",
    alerts_twitch: "bi-twitch",
    alerts_youtube: "bi-youtube",
    alerts_tiktok: "bi-tiktok",
    alerts_github: "bi-github",
    alerts_facebook: "bi-facebook",
    security: "bi-shield-check",
    moderation: "bi-hammer",
    music: "bi-music-note-beamed",
    promote: "bi-megaphone",
    commands: "bi-terminal",
    tickets: "bi-life-preserver",
    giveaways: "bi-gift",
    server_stats: "bi-activity",
    donate: "bi-heart",
    verify: "bi-patch-check",
    ocr: "bi-camera",
    aichat: "bi-robot",
    autoresponder: "bi-chat-dots",
    customrole: "bi-person-badge",
    media: "bi-images",
    control_panel: "bi-sliders2-vertical",
    audit_logs: "bi-journal-text",
    logs: "bi-journal-text",
    alerts: "bi-bell",
    status: "bi-wifi",
    leaderboard: "bi-trophy",
    invite: "bi-box-arrow-up-right",
    contact: "bi-envelope-paper",
    donatebot: "bi-heart-fill",
    logout: "bi-box-arrow-right",
    login: "bi-box-arrow-in-right",
    theme: "bi-circle-half",
    redeem: "bi-ticket-perforated",
    ownerbot: "bi-gear-wide-connected",
    section: "bi-grid",
    music_now_playing: "bi-disc",
    music_controls: "bi-sliders2",
    music_queue: "bi-music-note-list",
    levels_status: "bi-broadcast-pin",
    levels_preview: "bi-eye",
    levels_modules: "bi-toggles2",
    levels_xp: "bi-lightning-charge",
    levels_rewards: "bi-award",
    tickets_preview: "bi-window-stack",
    tickets_overview: "bi-bar-chart",
    tickets_history: "bi-clock-history",
    welcome_message: "bi-chat-left-text",
    welcome_roles: "bi-people",
    welcome_media: "bi-image",
    welcome_card: "bi-card-image",
    welcome_preview: "bi-eye",
    antinuke: "bi-shield-shaded",
    autoresponder_setup: "bi-chat-square-dots",
    autoresponder_list: "bi-list-ul",
    customrole_setup: "bi-person-plus",
    customrole_catalog: "bi-person-vcard",
    server_stats_category: "bi-diagram-3",
    server_stats_general: "bi-bar-chart-line",
    server_stats_presence: "bi-person-check",
    server_stats_cleanup: "bi-trash",
    ocr_status: "bi-toggle-on",
    ocr_rules: "bi-sliders",
    ocr_channels: "bi-hash",
    ocr_embed: "bi-card-text",
    ocr_keywords: "bi-search",
    dashboard_home: "bi-house-door",
    dashboard_joined: "bi-check2-circle",
    dashboard_invite: "bi-person-plus",
    overview_activity: "bi-activity",
    overview_range: "bi-calendar3",
    overview_membership: "bi-people",
    overview_messages: "bi-chat-square-text",
    index_growth: "bi-graph-up-arrow",
    index_bot_status: "bi-activity",
    index_developers: "bi-cpu",
    index_trusted: "bi-patch-check",
    index_features: "bi-stars",
    index_features_security: "bi-shield-lock",
    index_features_giveaway: "bi-gift",
    index_features_customize: "bi-sliders2-vertical",
    index_plugins: "bi-grid",
    index_resources: "bi-journal-text",
    index_resources_tutorials: "bi-book",
    index_resources_company: "bi-people",
    index_resources_spotlight: "bi-award",
    index_public_commands: "bi-terminal",
    index_pricing_compare: "bi-bar-chart",
    index_command_plan: "bi-list-ul",
    index_pricing_cards: "bi-gem",
    index_tutorials: "bi-journal-text",
    index_cta: "bi-megaphone",
    index_footer: "bi-grid-1x2-fill",
    index_footer_plugins: "bi-tools",
    index_footer_brand: "bi-robot",
    index_footer_company: "bi-building"
  });

  const I18N_TO_KEY = Object.freeze({
    tab_overview: "overview",
    tab_server_settings: "server_settings",
    tab_embed_messages: "embed_messages",
    tab_premium_receive: "premium_receive",
    tab_tools: "tools",
    tab_welcome_center: "welcome_center",
    tab_welcomer: "welcome_center",
    tab_auto_reply_center: "auto_reply_center",
    tab_economy: "economy",
    tab_levels: "levels",
    tab_autoroles: "autoroles",
    tab_colors: "colors",
    tab_reaction_roles: "reaction_roles",
    tab_starboard: "starboard",
    tab_temp_channels: "temp_channels",
    tab_join_to_create: "join_to_create",
    tab_temp_links: "temp_links",
    tab_statistics_plus: "statistics_plus",
    tab_screening: "screening",
    tab_screening_categories: "screening_categories",
    tab_automation: "automation",
    tab_anti_raid: "anti_raid",
    tab_extra_protection: "extra_protection",
    tab_alerts_twitch: "alerts_twitch",
    tab_alerts_youtube: "alerts_youtube",
    tab_alerts_tiktok: "alerts_tiktok",
    tab_alerts_github: "alerts_github",
    tab_alerts_facebook: "alerts_facebook",
    tab_security: "security",
    tab_moderation: "moderation",
    tab_music: "music",
    tab_promote: "promote",
    tab_commands: "commands",
    tab_tickets: "tickets",
    tab_giveaways: "giveaways",
    tab_server_stats: "server_stats",
    tab_donate: "donate",
    tab_verify: "verify",
    tab_ocr: "ocr",
    tab_aichat: "aichat",
    tab_autoresponder: "autoresponder",
    tab_customrole: "customrole",
    tab_media: "media",
    tab_control_panel: "control_panel",
    tab_audit_logs: "audit_logs"
  });

  const TAB_THEME_BY_SLUG = Object.freeze({
    overview: { brand: "#4f7dff", brand2: "#22d0ed" },
    server_settings: { brand: "#4f7dff", brand2: "#7aa2ff" },
    embed_messages: { brand: "#5468ff", brand2: "#22d0ed" },
    premium_receive: { brand: "#f59e0b", brand2: "#fbbf24" },
    tools: { brand: "#4f7dff", brand2: "#22d0ed" },
    welcome_center: { brand: "#22c55e", brand2: "#14b8a6" },
    welcome: { brand: "#22c55e", brand2: "#14b8a6" },
    leaver: { brand: "#16a34a", brand2: "#059669" },
    auto_reply_center: { brand: "#06b6d4", brand2: "#60a5fa" },
    economy: { brand: "#10b981", brand2: "#34d399" },
    levels: { brand: "#f59e0b", brand2: "#f97316" },
    autoroles: { brand: "#3b82f6", brand2: "#22d3ee" },
    colors: { brand: "#8b5cf6", brand2: "#ec4899" },
    reaction_roles: { brand: "#a855f7", brand2: "#22d3ee" },
    starboard: { brand: "#f59e0b", brand2: "#facc15" },
    join_to_create: { brand: "#06b6d4", brand2: "#3b82f6" },
    temp_channels: { brand: "#06b6d4", brand2: "#3b82f6" },
    temp_links: { brand: "#3b82f6", brand2: "#22d3ee" },
    statistics_plus: { brand: "#0ea5e9", brand2: "#22d3ee" },
    screening: { brand: "#22c55e", brand2: "#10b981" },
    screening_categories: { brand: "#22c55e", brand2: "#14b8a6" },
    automation: { brand: "#8b5cf6", brand2: "#3b82f6" },
    anti_raid: { brand: "#ef4444", brand2: "#f97316" },
    extra_protection: { brand: "#16a34a", brand2: "#0ea5e9" },
    alerts_twitch: { brand: "#a855f7", brand2: "#3b82f6" },
    alerts_youtube: { brand: "#ef4444", brand2: "#f97316" },
    alerts_tiktok: { brand: "#06b6d4", brand2: "#8b5cf6" },
    alerts_github: { brand: "#475569", brand2: "#3b82f6" },
    alerts_facebook: { brand: "#2563eb", brand2: "#06b6d4" },
    alerts: { brand: "#7c3aed", brand2: "#3b82f6" },
    security: { brand: "#16a34a", brand2: "#06b6d4" },
    moderation: { brand: "#ef4444", brand2: "#f97316" },
    music: { brand: "#3b82f6", brand2: "#22d3ee" },
    promote: { brand: "#ec4899", brand2: "#8b5cf6" },
    commands: { brand: "#6366f1", brand2: "#06b6d4" },
    tickets: { brand: "#14b8a6", brand2: "#3b82f6" },
    giveaways: { brand: "#f59e0b", brand2: "#fb7185" },
    server_stats: { brand: "#0ea5e9", brand2: "#22d3ee" },
    donate: { brand: "#fb7185", brand2: "#f97316" },
    verify: { brand: "#22c55e", brand2: "#3b82f6" },
    ocr: { brand: "#0ea5e9", brand2: "#14b8a6" },
    aichat: { brand: "#8b5cf6", brand2: "#06b6d4" },
    autoresponder: { brand: "#6366f1", brand2: "#22d3ee" },
    customrole: { brand: "#f97316", brand2: "#f59e0b" },
    media: { brand: "#06b6d4", brand2: "#6366f1" },
    control_panel: { brand: "#475569", brand2: "#3b82f6" },
    audit_logs: { brand: "#334155", brand2: "#6366f1" },
    logs: { brand: "#334155", brand2: "#6366f1" }
  });

  const ICON_SELECTOR = [
    ".main-nav a",
    ".sidebar-nav a",
    ".tab",
    ".guild-pill",
    ".server-rail-item",
    ".topbar .top-cta",
    ".topbar-action-link",
    ".topbar-action-btn"
  ].join(", ");

  const CONTEXT_ICON_SELECTOR = [
    ".panel-title h1",
    ".panel-title h2",
    ".panel > h1",
    ".panel > h2",
    ".panel > h3",
    ".dashboard-section-heading",
    ".cmd-all-head h1",
    ".cmd-disabled-head h2",
    ".cmd-favorite-head h2",
    ".hub-head h1",
    ".landing-hero-copy h1",
    ".panel-sub > h2",
    ".panel-sub > strong",
    ".panel-sub summary strong",
    ".side-group summary",
    ".public-card h1",
    ".public-card h2",
    ".public-link-box strong"
  ].join(", ");

  const RIPPLE_SELECTOR = [
    ".primary-btn",
    ".save-btn",
    ".ghost-btn",
    ".ux-btn",
    ".top-cta",
    "button[type='submit']"
  ].join(", ");

  function normalizeKey(value) {
    return String(value || "").trim().toLowerCase();
  }

  function iconByKey(key) {
    const normalized = normalizeKey(key);
    return ICON_BY_KEY[normalized] || ICON_BY_KEY.section;
  }

  function keyFromHref(hrefValue) {
    const raw = String(hrefValue || "").trim();
    if (!raw) return "";
    try {
      const url = new URL(raw, window.location.origin);
      const path = normalizeKey(url.pathname || "");
      if ((url.hostname || "").includes("discord.") && path.includes("/oauth2/authorize")) {
        return "invite";
      }
      if (path === "/dashboard" || path === "/dashboard/") return "overview";
      if (path.startsWith("/dashboard/music/")) return "music";
      if (path.startsWith("/status")) return "status";
      if (path.startsWith("/dashboard/status")) return "status";
      if (path.startsWith("/donatebot")) return "donatebot";
      if (path.startsWith("/redeem")) return "redeem";
      if (path.startsWith("/commands")) return "commands";
      if (path.startsWith("/premium")) return "premium_receive";
      if (path.startsWith("/contact")) return "contact";
      if (path.startsWith("/dashboard/contact")) return "contact";
      if (path.startsWith("/dashboard/donatebot")) return "donatebot";
      if (path.startsWith("/dashboard/redeem")) return "redeem";
      if (path.startsWith("/dashboard/login")) return "login";
      if (path.startsWith("/dashboard/logout")) return "logout";
      if (path.startsWith("/dashboard/commands")) return "commands";
      if (path.startsWith("/dashboard/premium")) return "premium_receive";
      if (path.startsWith("/dashboard/guild/")) {
        const parts = path.split("/").filter(Boolean);
        if (parts.length >= 4) return normalizeKey(parts[3]);
        return "overview";
      }
      return "";
    } catch (_error) {
      return "";
    }
  }

  function keyFromNode(node) {
    if (!(node instanceof HTMLElement)) return "";
    const explicit = normalizeKey(node.dataset.iconKey || "");
    if (explicit) return explicit;
    const tabSlug = normalizeKey(node.dataset.tabSlug || "");
    if (tabSlug) return tabSlug;
    const i18nKey = normalizeKey(node.dataset.i18n || "");
    if (i18nKey && I18N_TO_KEY[i18nKey]) return I18N_TO_KEY[i18nKey];
    const dashboardAction = normalizeKey(node.getAttribute("data-dashboard-action") || "");
    if (dashboardAction === "toggle-theme") return "theme";
    const hrefKey = keyFromHref(node.getAttribute("href") || "");
    if (hrefKey) return hrefKey;
    return "";
  }

  function keyFromContextNode(node) {
    if (!(node instanceof HTMLElement)) return "";
    const explicit = normalizeKey(node.dataset.iconKey || "");
    if (explicit) return explicit;
    const i18nKey = normalizeKey(node.dataset.i18n || "");
    if (i18nKey && I18N_TO_KEY[i18nKey]) return I18N_TO_KEY[i18nKey];
    return getActiveTabSlug() || "section";
  }

  function readDashboardBootstrap() {
    const node = document.getElementById("dashboard-bootstrap");
    if (!node) return {};
    const raw = String(node.textContent || "{}");
    try {
      return JSON.parse(raw);
    } catch (_error) {
      try {
        const textarea = document.createElement("textarea");
        textarea.innerHTML = raw;
        return JSON.parse(String(textarea.value || "{}"));
      } catch (_innerError) {
        return {};
      }
    }
  }

  function activeTabFromPath() {
    const path = normalizeKey(window.location.pathname || "");
    if (path.startsWith("/commands")) return "commands";
    if (path.startsWith("/contact")) return "contact";
    if (path.startsWith("/donatebot")) return "donatebot";
    if (path.startsWith("/redeem")) return "redeem";
    if (path.startsWith("/status")) return "server_stats";
    if (path.startsWith("/premium")) return "premium_receive";
    if (!path.startsWith("/dashboard")) return "";
    if (path === "/dashboard" || path === "/dashboard/") return "overview";
    if (path.startsWith("/dashboard/music/")) return "music";
    if (path.startsWith("/dashboard/guild/")) {
      const parts = path.split("/").filter(Boolean);
      if (parts.length >= 4) return normalizeKey(parts[3]);
      return "overview";
    }
    if (path.startsWith("/dashboard/commands")) return "commands";
    if (path.startsWith("/dashboard/contact")) return "contact";
    if (path.startsWith("/dashboard/donatebot")) return "donatebot";
    if (path.startsWith("/dashboard/redeem")) return "redeem";
    if (path.startsWith("/dashboard/status")) return "server_stats";
    return "";
  }

  function getActiveTabSlug() {
    const fromPath = activeTabFromPath();
    if (fromPath) return fromPath;
    const bootstrap = readDashboardBootstrap();
    const fromBootstrap = normalizeKey(bootstrap.activeTab || "");
    if (fromBootstrap) return fromBootstrap;
    return "";
  }

  function sanitizeClassToken(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
  }

  function clearPrefixedClasses(node, prefix) {
    if (!(node instanceof HTMLElement)) return;
    const toRemove = [];
    node.classList.forEach((name) => {
      if (name.startsWith(prefix)) toRemove.push(name);
    });
    toRemove.forEach((name) => node.classList.remove(name));
  }

  function applyDashboardTabTheme() {
    const slug = sanitizeClassToken(getActiveTabSlug());
    if (!slug) return;
    const body = document.body;
    if (!(body instanceof HTMLElement)) return;

    clearPrefixedClasses(body, "dashboard-tab-");
    body.classList.add(`dashboard-tab-${slug}`);
    body.dataset.activeTab = slug;

    const palette = TAB_THEME_BY_SLUG[slug] || TAB_THEME_BY_SLUG.overview || { brand: "#4f7dff", brand2: "#22d0ed" };
    body.style.setProperty("--tab-accent", String(palette.brand || "#4f7dff"));
    body.style.setProperty("--tab-accent-2", String(palette.brand2 || "#22d0ed"));
  }

  function applyDashboardTabDecorations(root = document) {
    const slug = sanitizeClassToken(getActiveTabSlug());
    if (!slug) return;
    const container = document.querySelector(".dashboard-dynamic-content");
    if (!(container instanceof HTMLElement)) return;

    clearPrefixedClasses(container, "dashboard-tab-content-");
    container.classList.add(`dashboard-tab-content-${slug}`);

    const firstPanel = container.querySelector(".panel");
    if (firstPanel instanceof HTMLElement) {
      firstPanel.classList.add("dashboard-first-panel");
      const header = firstPanel.querySelector(":scope > .panel-header");
      if (header instanceof HTMLElement) {
        const hasCustomHero = header.classList.contains("detail-page-hero");
        if (!hasCustomHero) {
          header.classList.add("detail-page-hero-auto");
        } else {
          header.classList.remove("detail-page-hero-auto");
        }
      }
    }

    root.querySelectorAll(".dashboard-dynamic-content .panel-sub").forEach((section) => {
      if (!(section instanceof HTMLElement)) return;
      if (!section.classList.contains("detail-page-section")) {
        section.classList.add("detail-page-section-auto");
      } else {
        section.classList.remove("detail-page-section-auto");
      }
    });
  }

  function shouldSkipIcon(node) {
    if (!(node instanceof HTMLElement)) return true;
    if (node.dataset.iconified === "1") return true;
    if (node.dataset.noIcon === "1") return true;
    if (node.querySelector(":scope > .ui-icon")) return true;
    if (node.querySelector(":scope > i, :scope > svg, :scope > img")) return true;
    const text = String(node.textContent || "").trim();
    return text.length < 2;
  }

  function applyIcons(root = document) {
    root.querySelectorAll(ICON_SELECTOR).forEach((node) => {
      const key = keyFromNode(node);
      if (!key) return;
      const iconClass = iconByKey(key);

      const sideIcon = node.querySelector(":scope > .side-icon");
      if (sideIcon instanceof HTMLElement) {
        if (sideIcon.dataset.iconified === "1") return;
        sideIcon.classList.add("ui-icon", "side-icon-ui");
        sideIcon.innerHTML = `<i class="bi ${iconClass}" aria-hidden="true"></i>`;
        sideIcon.dataset.iconified = "1";
        node.dataset.iconified = "1";
        return;
      }

      if (shouldSkipIcon(node)) return;
      const iconWrap = document.createElement("span");
      iconWrap.className = "ui-icon";
      iconWrap.innerHTML = `<i class="bi ${iconClass}" aria-hidden="true"></i>`;
      node.insertBefore(iconWrap, node.firstChild);
      node.dataset.iconified = "1";
    });
  }

  function shouldSkipContextIcon(node) {
    if (!(node instanceof HTMLElement)) return true;
    if (node.dataset.iconified === "1") return true;
    if (node.querySelector(":scope > .side-group-title > .side-group-icon")) return true;
    if (node.querySelector(":scope > .ui-icon")) return true;
    if (node.querySelector(":scope > i, :scope > svg, :scope > img")) return true;
    const text = String(node.textContent || "").trim();
    return text.length < 2;
  }

  function applyContextIcons(root = document) {
    root.querySelectorAll(CONTEXT_ICON_SELECTOR).forEach((node) => {
      if (shouldSkipContextIcon(node)) return;
      const iconClass = iconByKey(keyFromContextNode(node));
      const iconWrap = document.createElement("span");
      iconWrap.className = "ui-icon context-icon";
      iconWrap.innerHTML = `<i class="bi ${iconClass}" aria-hidden="true"></i>`;

      node.insertBefore(iconWrap, node.firstChild);
      node.dataset.iconified = "1";
    });
  }

  function normalizeDashboardPanels(root = document) {
    root.querySelectorAll(".dashboard-dynamic-content .panel").forEach((panel) => {
      if (!(panel instanceof HTMLElement)) return;
      panel.classList.add("dashboard-auto-panel");
      if (panel.querySelector(":scope > .panel-header")) return;

      const heading = panel.querySelector(":scope > h1, :scope > h2, :scope > h3");
      if (!(heading instanceof HTMLElement)) return;

      const header = document.createElement("div");
      header.className = "panel-header dashboard-auto-header";
      const title = document.createElement("div");
      title.className = "panel-title dashboard-auto-title";

      heading.classList.add("dashboard-section-heading");
      title.appendChild(heading);

      const next = heading.nextElementSibling;
      if (next instanceof HTMLElement && next.matches("p, .muted")) {
        title.appendChild(next);
      }

      header.appendChild(title);
      panel.insertBefore(header, panel.firstChild);
    });
  }

  function normalizeDashboardForms(root = document) {
    root.querySelectorAll(".dashboard-dynamic-content form").forEach((form) => {
      if (!(form instanceof HTMLFormElement)) return;
      form.classList.add("dashboard-auto-form");

      form.querySelectorAll("label").forEach((label) => {
        if (!(label instanceof HTMLElement)) return;
        if (label.classList.contains("ux-toggle")) return;
        if (label.querySelector(".ux-switch")) return;
        if (label.classList.contains("form-check-label")) return;
        if (label.dataset.noAutoField === "1") return;
        const hasControl = Boolean(label.querySelector("input, select, textarea"));
        if (!hasControl) return;
        if (label.classList.contains("field-item")) return;
        label.classList.add("field-item", "dashboard-auto-field");
      });
    });
  }

  function normalizeDashboardTables(root = document) {
    root.querySelectorAll(".dashboard-dynamic-content table").forEach((table) => {
      if (!(table instanceof HTMLTableElement)) return;
      if (table.closest(".table-wrap")) return;

      const wrap = document.createElement("div");
      wrap.className = "table-wrap dashboard-table-wrap";
      const parent = table.parentNode;
      if (!parent) return;
      parent.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  function normalizeDashboardStacks() {
    const container = document.querySelector(".dashboard-dynamic-content");
    if (!(container instanceof HTMLElement)) return;
    if (container.dataset.stackNormalized === "1") return;

    const stackCandidates = Array.from(container.children).filter((node) => {
      return node instanceof HTMLElement && !["SCRIPT", "STYLE", "LINK"].includes(node.tagName);
    });
    if (!stackCandidates.length) {
      container.dataset.stackNormalized = "1";
      return;
    }

    const hasSectionStack = stackCandidates.some((node) => node.classList.contains("section-stack"));
    if (!hasSectionStack) {
      const wrapper = document.createElement("div");
      wrapper.className = "section-stack dashboard-auto-stack";
      stackCandidates[0].before(wrapper);
      stackCandidates.forEach((node) => wrapper.appendChild(node));
    }
    container.dataset.stackNormalized = "1";
  }

  function normalizeDashboardContent(root = document) {
    normalizeDashboardStacks();
    normalizeDashboardPanels(root);
    normalizeDashboardForms(root);
    normalizeDashboardTables(root);
  }

  function initButtonRipple() {
    const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) return;

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const btn = target.closest(RIPPLE_SELECTOR);
      if (!(btn instanceof HTMLElement)) return;

      const rect = btn.getBoundingClientRect();
      const ripple = document.createElement("span");
      ripple.className = "btn-ripple";
      ripple.style.left = `${event.clientX - rect.left}px`;
      ripple.style.top = `${event.clientY - rect.top}px`;

      if (!btn.style.position) btn.style.position = "relative";
      btn.style.overflow = "hidden";
      btn.appendChild(ripple);
      window.setTimeout(() => ripple.remove(), 500);
    });
  }

  function initMobileSidebarToggle() {
    const sidebar = document.querySelector(".dashboard-sidebar");
    const topbarLeft = document.querySelector(".topbar-left");
    if (!(sidebar instanceof HTMLElement) || !(topbarLeft instanceof HTMLElement)) return;
    if (document.querySelector(".sidebar-toggle")) return;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "sidebar-toggle ux-btn";
    toggle.innerHTML = '<span class="ui-icon"><i class="bi bi-layout-sidebar" aria-hidden="true"></i></span><span>เมนู</span>';
    topbarLeft.insertBefore(toggle, topbarLeft.firstChild);

    const closeSidebar = () => document.body.classList.remove("sidebar-open");

    toggle.addEventListener("click", () => {
      document.body.classList.toggle("sidebar-open");
    });

    document.addEventListener("click", (event) => {
      if (window.innerWidth > 980) return;
      if (!document.body.classList.contains("sidebar-open")) return;
      const node = event.target;
      if (!(node instanceof Element)) return;
      if (node.closest(".dashboard-sidebar") || node.closest(".sidebar-toggle")) return;
      closeSidebar();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeSidebar();
    });
  }

  let topbarAccountMenuEventsBound = false;
  function initTopbarAccountMenu() {
    const menus = Array.from(document.querySelectorAll(".topbar-account-menu"));
    if (!menus.length) return;

    menus.forEach((menu) => {
      if (!(menu instanceof HTMLDetailsElement)) return;
      if (menu.dataset.dropdownReady === "1") return;
      menu.dataset.dropdownReady = "1";

      menu.querySelectorAll("a").forEach((linkNode) => {
        if (!(linkNode instanceof HTMLElement)) return;
        linkNode.addEventListener("click", () => {
          menu.removeAttribute("open");
        });
      });
    });

    if (topbarAccountMenuEventsBound) return;
    topbarAccountMenuEventsBound = true;

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest(".topbar-account-menu")) return;
      document.querySelectorAll(".topbar-account-menu[open]").forEach((menuNode) => {
        if (menuNode instanceof HTMLDetailsElement) {
          menuNode.removeAttribute("open");
        }
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      document.querySelectorAll(".topbar-account-menu[open]").forEach((menuNode) => {
        if (menuNode instanceof HTMLDetailsElement) {
          menuNode.removeAttribute("open");
        }
      });
    });
  }

  function initMutationRefresh() {
    if (!(window.MutationObserver && document.body)) return;

    let timer = 0;
    const observeRoot = document.querySelector(".dashboard-dynamic-content") || document.body;
    const observer = new MutationObserver((mutations) => {
      const hasAddedNodes = mutations.some((item) => {
        if (!item.addedNodes || !item.addedNodes.length) return false;
        return Array.from(item.addedNodes).some((node) => {
          if (!(node instanceof HTMLElement)) return false;
          if (node.matches(".ui-icon, .context-icon, i.bi, img")) return false;
          if (node.closest && node.closest(".ui-icon, .context-icon")) return false;
          return true;
        });
      });
      if (!hasAddedNodes) return;

      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        normalizeDashboardContent(observeRoot);
        applyDashboardTabTheme();
        applyDashboardTabDecorations(observeRoot);
        applyIcons(observeRoot);
        applyContextIcons(observeRoot);
        initTopbarAccountMenu();
      }, 180);
    });
    observer.observe(observeRoot, { childList: true, subtree: true });
  }

  function init() {
    normalizeDashboardContent();
    applyDashboardTabTheme();
    applyDashboardTabDecorations();
    applyIcons();
    applyContextIcons();
    initButtonRipple();
    initMobileSidebarToggle();
    initTopbarAccountMenu();
    initMutationRefresh();
  }

  window.addEventListener("DOMContentLoaded", init);
})();
