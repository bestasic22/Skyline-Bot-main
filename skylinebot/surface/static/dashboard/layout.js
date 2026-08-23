(function () {
  const DASHBOARD_TOAST_DURATION_MS = 3800;
  const DASHBOARD_TOAST_DEDUPE_MS = 1200;
  const DASHBOARD_BUSY_MIN_VISIBLE_MS = 240;
  const DASHBOARD_BUSY_FALLBACK_RELEASE_MS = 18000;
  const DASHBOARD_INITIAL_BUSY_DELAY_MS = 420;
  const DASHBOARD_PREFETCH_AUTO_LIMIT = 6;
  const DASHBOARD_PREFETCH_TOTAL_LIMIT = 18;
  const DASHBOARD_PREFETCH_TIMEOUT_MS = 9000;
  const DASHBOARD_PROGRESSIVE_REVEAL_BATCH_SIZE = 2;
  const DASHBOARD_PROGRESSIVE_REVEAL_DELAY_MS = 100;
  const DASHBOARD_PREFETCH_SELECTORS = [
    ".sidebar-nav a[href]",
    ".server-rail-item[href]",
    ".topbar a[href]",
    ".topbar-action-link[href]",
  ].join(", ");
  const busyModePriority = Object.freeze({ work: 1, save: 2, page: 3 });
  const busyModeClassMap = Object.freeze({
    work: "dashboard-loading-work",
    save: "dashboard-loading-save",
    page: "dashboard-loading-page",
  });
  const busyTokens = new Map();
  const submitBusyState = new WeakMap();
  const invalidToastState = { at: 0 };
  let busyTokenSequence = 0;
  let busyVisibleSince = 0;
  let busyHideTimer = 0;
  let initialPageBusyToken = "";
  let initialPageBusyDelayTimer = 0;
  let fetchWrapped = false;
  let navigationBusyToken = "";
  let beforeUnloadBusyToken = "";
  let suppressDirtyBeforeUnloadUntil = 0;
  let lastToastSignature = "";
  let lastToastAt = 0;

  const feedbackCopy = Object.freeze({
    th: Object.freeze({
      loadingTitle: "Loading data...",
      loadingSubtitle: "Please wait a moment",
      savingTitle: "Saving changes...",
      savingSubtitle: "Your request is being processed",
      workingTitle: "Processing...",
      workingSubtitle: "Please wait",
      savingToast: "Saving in progress...",
      invalidRequired: "Please complete all required fields before submitting.",
      networkError: "Network error. Please check your connection and try again.",
      sessionExpired: "Your session has expired. Please sign in again.",
      permissionDenied: "Permission denied for this action.",
      requestFailed: "Request failed (HTTP {status}).",
    }),
    en: Object.freeze({
      loadingTitle: "Loading data...",
      loadingSubtitle: "Please wait a moment",
      savingTitle: "Saving changes...",
      savingSubtitle: "Your request is being processed",
      workingTitle: "Processing...",
      workingSubtitle: "Please wait",
      savingToast: "Saving in progress...",
      invalidRequired: "Please complete all required fields before submitting.",
      networkError: "Network error. Please check your connection and try again.",
      sessionExpired: "Your session has expired. Please sign in again.",
      permissionDenied: "Permission denied for this action.",
      requestFailed: "Request failed (HTTP {status}).",
    }),
  });

  function dashboardLanguage() {
    const lang = String(document.documentElement.lang || "th").trim().toLowerCase();
    return lang.startsWith("en") ? "en" : "th";
  }

  function feedbackText(key, tokens = {}) {
    const lang = dashboardLanguage();
    const dict = feedbackCopy[lang] || feedbackCopy.th;
    const template = String(dict[key] || feedbackCopy.en[key] || key);
    if (!tokens || typeof tokens !== "object") return template;
    return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_all, name) => {
      if (!Object.prototype.hasOwnProperty.call(tokens, name)) return "";
      return String(tokens[name]);
    });
  }

  function localizeRuntimeText(value) {
    const raw = String(value ?? "");
    if (!raw) return raw;
    try {
      if (typeof window.dashboardTranslateLoose === "function") {
        const translated = window.dashboardTranslateLoose(raw);
        if (typeof translated === "string" && translated) {
          return translated;
        }
      }
    } catch (_error) {
    }
    return raw;
  }

  function iconForToast(type) {
    if (type === "error") return "bi-x-octagon-fill";
    if (type === "warning") return "bi-exclamation-triangle-fill";
    return "bi-check-circle-fill";
  }

  function showToast(message, type = "success", options = {}) {
    const text = localizeRuntimeText(message).trim();
    if (!text) return;
    const dedupeMs =
      Number.isFinite(Number(options && options.dedupeWindowMs))
        ? Math.max(0, Number(options.dedupeWindowMs))
        : DASHBOARD_TOAST_DEDUPE_MS;
    const signature = `${String(type || "success")}::${text}`;
    const now = Date.now();
    if (signature === lastToastSignature && now - lastToastAt < dedupeMs) {
      return;
    }
    lastToastSignature = signature;
    lastToastAt = now;

    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const iconWrap = document.createElement("span");
    iconWrap.className = "toast-icon";
    const icon = document.createElement("i");
    icon.className = `bi ${iconForToast(type)}`;
    icon.setAttribute("aria-hidden", "true");
    iconWrap.appendChild(icon);
    const textNode = document.createElement("span");
    textNode.className = "toast-message";
    textNode.textContent = text;
    toast.append(iconWrap, textNode);
    container.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 260);
    }, DASHBOARD_TOAST_DURATION_MS);
  }

  function notifyOperation(message, type = "success", options = {}) {
    const text = localizeRuntimeText(message).trim();
    if (!text) return;
    const normalized = type === "error" || type === "warning" ? type : "success";
    showToast(text, normalized, options);
  }

  function ensureGlobalLoader() {
    let loader = document.getElementById("dashboard-global-loader");
    if (!(loader instanceof HTMLElement)) {
      loader = document.createElement("div");
      loader.id = "dashboard-global-loader";
      loader.className = "dashboard-global-loader";
      loader.setAttribute("aria-hidden", "true");
      loader.innerHTML = `
        <div class="dashboard-global-loader-card" role="status" aria-live="polite">
          <span class="dashboard-global-loader-spinner" aria-hidden="true"></span>
          <div class="dashboard-global-loader-copy">
            <strong data-dashboard-loader-title></strong>
            <span data-dashboard-loader-subtitle></span>
          </div>
          <div class="dashboard-global-loader-skeleton" aria-hidden="true">
            <span></span><span></span><span></span>
          </div>
        </div>
      `;
      document.body.appendChild(loader);
    }
    return loader;
  }

  function pickTopBusyToken() {
    let winner = null;
    busyTokens.forEach((state, token) => {
      if (!state || typeof state !== "object") return;
      if (!winner) {
        winner = { token, state };
        return;
      }
      const winnerPriority = busyModePriority[winner.state.mode] || 0;
      const challengerPriority = busyModePriority[state.mode] || 0;
      if (challengerPriority > winnerPriority) {
        winner = { token, state };
        return;
      }
      if (challengerPriority === winnerPriority && Number(state.seq || 0) > Number(winner.state.seq || 0)) {
        winner = { token, state };
      }
    });
    return winner;
  }

  function applyLoaderCopy(state) {
    const loader = ensureGlobalLoader();
    if (!(loader instanceof HTMLElement)) return;
    const titleNode = loader.querySelector("[data-dashboard-loader-title]");
    const subtitleNode = loader.querySelector("[data-dashboard-loader-subtitle]");
    const mode = String(state?.mode || "work");
    const defaultTitle =
      mode === "page"
        ? feedbackText("loadingTitle")
        : mode === "save"
          ? feedbackText("savingTitle")
          : feedbackText("workingTitle");
    const defaultSubtitle =
      mode === "page"
        ? feedbackText("loadingSubtitle")
        : mode === "save"
          ? feedbackText("savingSubtitle")
          : feedbackText("workingSubtitle");
    const nextTitle = localizeRuntimeText(state?.title || defaultTitle);
    const nextSubtitle = localizeRuntimeText(state?.subtitle || defaultSubtitle);
    if (titleNode instanceof HTMLElement) {
      titleNode.textContent = nextTitle;
    }
    if (subtitleNode instanceof HTMLElement) {
      subtitleNode.textContent = nextSubtitle;
    }
  }

  function setBusyBodyMode(mode) {
    const body = document.body;
    if (!body) return;
    body.classList.remove(
      busyModeClassMap.work,
      busyModeClassMap.save,
      busyModeClassMap.page
    );
    const modeClass = busyModeClassMap[mode] || busyModeClassMap.work;
    body.classList.add(modeClass);
  }

  function showBusyOverlay(state) {
    const loader = ensureGlobalLoader();
    if (!(loader instanceof HTMLElement)) return;
    if (busyHideTimer) {
      window.clearTimeout(busyHideTimer);
      busyHideTimer = 0;
    }
    applyLoaderCopy(state);
    loader.classList.add("show");
    loader.setAttribute("aria-hidden", "false");
    loader.setAttribute("aria-busy", "true");
    document.body.classList.add("dashboard-loading-active");
    setBusyBodyMode(String(state?.mode || "work"));
    if (!busyVisibleSince) {
      busyVisibleSince = Date.now();
    }
  }

  function hideBusyOverlayNow() {
    const loader = ensureGlobalLoader();
    if (!(loader instanceof HTMLElement)) return;
    loader.classList.remove("show");
    loader.setAttribute("aria-hidden", "true");
    loader.setAttribute("aria-busy", "false");
    document.body.classList.remove(
      "dashboard-loading-active",
      busyModeClassMap.work,
      busyModeClassMap.save,
      busyModeClassMap.page
    );
    busyVisibleSince = 0;
  }

  function renderBusyOverlay() {
    const winner = pickTopBusyToken();
    if (winner && winner.state) {
      showBusyOverlay(winner.state);
      return;
    }
    if (!busyVisibleSince) {
      hideBusyOverlayNow();
      return;
    }
    const elapsed = Date.now() - busyVisibleSince;
    const remain = Math.max(0, DASHBOARD_BUSY_MIN_VISIBLE_MS - elapsed);
    if (remain <= 0) {
      hideBusyOverlayNow();
      return;
    }
    if (busyHideTimer) {
      return;
    }
    busyHideTimer = window.setTimeout(() => {
      busyHideTimer = 0;
      if (busyTokens.size) {
        renderBusyOverlay();
        return;
      }
      hideBusyOverlayNow();
    }, remain);
  }

  function beginBusy(mode = "work", options = {}) {
    busyTokenSequence += 1;
    const token = `busy_${Date.now()}_${busyTokenSequence}`;
    const state = {
      mode: String(mode || "work").toLowerCase(),
      title: String(options.title || "").trim(),
      subtitle: String(options.subtitle || "").trim(),
      seq: busyTokenSequence,
    };
    busyTokens.set(token, state);
    renderBusyOverlay();
    const fallbackMs = Number(options.timeoutMs);
    const timeoutMs = Number.isFinite(fallbackMs) && fallbackMs > 0
      ? Math.max(1000, fallbackMs)
      : DASHBOARD_BUSY_FALLBACK_RELEASE_MS;
    window.setTimeout(() => {
      if (!busyTokens.has(token)) return;
      busyTokens.delete(token);
      renderBusyOverlay();
    }, timeoutMs);
    return token;
  }

  function endBusy(token) {
    const key = String(token || "").trim();
    if (!key) return;
    if (!busyTokens.has(key)) return;
    busyTokens.delete(key);
    renderBusyOverlay();
  }

  function resetSubmitControl(control) {
    if (!(control instanceof HTMLElement)) return;
    control.classList.remove("dashboard-submit-loading");
    control.removeAttribute("aria-busy");
    if (control instanceof HTMLInputElement) {
      const previousValue = String(control.dataset.dashboardPrevValue || "");
      if (previousValue) {
        control.value = previousValue;
      }
      delete control.dataset.dashboardPrevValue;
      control.disabled = false;
      return;
    }
    if (control instanceof HTMLButtonElement) {
      control.disabled = false;
    }
  }

  function markSubmitControlLoading(control) {
    if (!(control instanceof HTMLElement)) return;
    if (control.classList.contains("dashboard-submit-loading")) return;
    control.classList.add("dashboard-submit-loading");
    control.setAttribute("aria-busy", "true");
    if (control instanceof HTMLInputElement) {
      if (!control.dataset.dashboardPrevValue) {
        control.dataset.dashboardPrevValue = String(control.value || "");
      }
      control.value = feedbackText("savingTitle");
      control.disabled = true;
      return;
    }
    if (control instanceof HTMLButtonElement) {
      control.disabled = true;
    }
  }

  function findSubmitControl(form, submitter) {
    if (submitter instanceof HTMLElement) {
      return submitter;
    }
    const first = form.querySelector('button[type="submit"], input[type="submit"]');
    return first instanceof HTMLElement ? first : null;
  }

  function clearSubmitState(form) {
    const state = submitBusyState.get(form);
    if (!state) return;
    if (state.token) {
      endBusy(state.token);
    }
    if (state.timeoutId) {
      window.clearTimeout(state.timeoutId);
    }
    if (state.control) {
      resetSubmitControl(state.control);
    }
    submitBusyState.delete(form);
  }

  function beginFormSubmitState(form, submitter) {
    clearSubmitState(form);
    const control = findSubmitControl(form, submitter);
    if (control) {
      markSubmitControlLoading(control);
    }
    const token = beginBusy("save", {
      title: feedbackText("savingTitle"),
      subtitle: feedbackText("savingSubtitle"),
      timeoutMs: 20000,
    });
    const timeoutId = window.setTimeout(() => {
      clearSubmitState(form);
    }, 20000);
    submitBusyState.set(form, { token, timeoutId, control });
  }

  function normalizeRequestMeta(input, init) {
    const payload = init && typeof init === "object" ? init : {};
    const inputMethod =
      input && typeof input === "object" && "method" in input
        ? String(input.method || "").trim().toUpperCase()
        : "";
    const method = String(payload.method || inputMethod || "GET").trim().toUpperCase() || "GET";
    let url = null;
    try {
      if (typeof input === "string") {
        url = new URL(input, window.location.origin);
      } else if (input instanceof URL) {
        url = new URL(String(input), window.location.origin);
      } else if (input && typeof input === "object" && "url" in input) {
        url = new URL(String(input.url || ""), window.location.origin);
      }
    } catch (_error) {
      url = null;
    }
    return {
      method,
      url,
      isMutating: !["GET", "HEAD", "OPTIONS"].includes(method),
    };
  }

  function isPassiveEndpoint(url) {
    if (!(url instanceof URL)) return false;
    const path = String(url.pathname || "");
    if (path.startsWith("/dashboard/runtime/discord")) return true;
    if (path.includes("/live-options")) return true;
    if (path.startsWith("/dashboard/admin/ownerbot/live")) return true;
    if (path.startsWith("/contact/realtime/")) return true;
    if (path.startsWith("/dashboard/guild/") && path.endsWith("/live")) return true;
    return false;
  }

  function httpFailureMessage(status) {
    const code = Number(status || 0);
    if (code === 401) return feedbackText("sessionExpired");
    if (code === 403) return feedbackText("permissionDenied");
    return feedbackText("requestFailed", { status: code || "?" });
  }

  function shouldTrackNavigationAnchor(anchor) {
    if (!(anchor instanceof HTMLAnchorElement)) return false;
    if (anchor.hasAttribute("download")) return false;
    const target = String(anchor.getAttribute("target") || "").trim();
    if (target && target !== "_self") return false;
    const href = String(anchor.getAttribute("href") || "").trim();
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return false;
    if (anchor.dataset.noGlobalLoader === "1") return false;
    let url = null;
    try {
      url = new URL(anchor.href, window.location.origin);
    } catch (_error) {
      return false;
    }
    if (!url) return false;
    if (url.origin !== window.location.origin) return false;
    if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) {
      return false;
    }
    return true;
  }

  function initGlobalFetchFeedback() {
    if (fetchWrapped || typeof window.fetch !== "function") return;
    fetchWrapped = true;
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const requestInit = init && typeof init === "object" ? init : {};
      const silentFeedback = requestInit.dashboardSilent === true;
      const meta = normalizeRequestMeta(input, requestInit);
      const passive = isPassiveEndpoint(meta.url);
      const shouldShowBusy = meta.isMutating && !passive && requestInit.dashboardNoBusy !== true;
      const busyToken = shouldShowBusy
        ? beginBusy("save", {
            title: feedbackText("savingTitle"),
            subtitle: feedbackText("savingSubtitle"),
            timeoutMs: 20000,
          })
        : "";
      try {
        const response = await nativeFetch(input, init);
        if (!response.ok) {
          const shouldNotifyHttpError = !passive && (response.status >= 500 || response.status === 401 || response.status === 403);
          if (shouldNotifyHttpError && !silentFeedback) {
            notifyOperation(httpFailureMessage(response.status), "error");
          }
        }
        if (response.ok && typeof requestInit.dashboardSuccessMessage === "string") {
          const successText = String(requestInit.dashboardSuccessMessage || "").trim();
          if (successText) {
            notifyOperation(successText, "success");
          }
        }
        return response;
      } catch (error) {
        const aborted = error && typeof error === "object" && String(error.name || "").toLowerCase() === "aborterror";
        if (!passive && !silentFeedback && !aborted) {
          notifyOperation(feedbackText("networkError"), "error");
        }
        throw error;
      } finally {
        if (busyToken) {
          endBusy(busyToken);
        }
      }
    };
  }

  function initFormSubmissionFeedback() {
    document.addEventListener(
      "submit",
      (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (event.defaultPrevented) return;
        const method = String(form.getAttribute("method") || "get").trim().toUpperCase();
        if (!["POST", "PUT", "PATCH", "DELETE"].includes(method)) return;
        markDirtyBeforeUnloadSuppressed(25000);
        beginFormSubmitState(form, event.submitter);
        notifyOperation(feedbackText("savingToast"), "warning", { dedupeWindowMs: 500 });
      },
      true
    );

    document.addEventListener(
      "invalid",
      (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const now = Date.now();
        if (now - invalidToastState.at < 1400) return;
        invalidToastState.at = now;
        notifyOperation(feedbackText("invalidRequired"), "warning");
      },
      true
    );

    window.addEventListener("pageshow", () => {
      document.querySelectorAll(".dashboard-submit-loading").forEach((node) => {
        if (!(node instanceof HTMLElement)) return;
        resetSubmitControl(node);
      });
    });
  }

  function initNavigationFeedback() {
    document.addEventListener(
      "click",
      (event) => {
        if (event.defaultPrevented) return;
        if (event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const target = event.target;
        if (!(target instanceof Element)) return;
        const anchor = target.closest("a[href]");
        if (!(anchor instanceof HTMLAnchorElement)) return;
        if (!shouldTrackNavigationAnchor(anchor)) return;
        if (!navigationBusyToken) {
          const currentHref = String(window.location.href || "");
          navigationBusyToken = beginBusy("page", {
            title: feedbackText("loadingTitle"),
            subtitle: feedbackText("loadingSubtitle"),
            timeoutMs: 20000,
          });
          window.setTimeout(() => {
            if (!navigationBusyToken) return;
            if (document.visibilityState !== "visible") return;
            if (String(window.location.href || "") !== currentHref) return;
            endBusy(navigationBusyToken);
            navigationBusyToken = "";
          }, 1400);
        }
      },
      true
    );

    window.addEventListener("beforeunload", () => {
      if (!beforeUnloadBusyToken) {
        beforeUnloadBusyToken = beginBusy("page", {
          title: feedbackText("loadingTitle"),
          subtitle: feedbackText("loadingSubtitle"),
          timeoutMs: 10000,
        });
      }
    });
  }

  function shouldPrefetchNavigationUrl(url) {
    if (!(url instanceof URL)) return false;
    if (url.origin !== window.location.origin) return false;
    const path = String(url.pathname || "").trim();
    if (!path) return false;
    if (path.startsWith("/dashboard/static/")) return false;
    if (path.startsWith("/dashboard/auth/")) return false;
    if (path.startsWith("/dashboard/runtime/")) return false;
    if (path.startsWith("/dashboard/logout")) return false;
    if (path.endsWith("/live") || path.endsWith("/live-options")) return false;
    if (path === String(window.location.pathname || "") && url.search === String(window.location.search || "")) {
      return false;
    }
    return true;
  }

  function initBackgroundNavigationPrefetch() {
    const bootstrap = readDashboardBootstrap();
    const perf = bootstrap && typeof bootstrap === "object" ? (bootstrap.perf || {}) : {};
    const enabled =
      window.SKYLINE_ENABLE_NAV_PREFETCH === true ||
      perf.navigationPrefetch === true;
    if (!enabled) return;
    const currentPath = String(window.location.pathname || "");
    if (!currentPath.startsWith("/dashboard")) return;
    if (typeof window.fetch !== "function") return;
    const connection = navigator.connection;
    if (connection) {
      const saveDataEnabled = connection.saveData === true;
      const effectiveType = String(connection.effectiveType || "").toLowerCase();
      if (saveDataEnabled || effectiveType.includes("2g")) return;
    }

    const prefetchState = new Map();
    const prefetchQueue = [];
    let activePrefetchCount = 0;
    let totalQueuedCount = 0;

    const markQueued = (href) => {
      prefetchState.set(href, "queued");
      totalQueuedCount += 1;
    };

    const markDone = (href) => {
      prefetchState.set(href, "done");
    };

    const markFailed = (href) => {
      prefetchState.set(href, "failed");
    };

    const normalizeAnchorToUrl = (anchor) => {
      if (!(anchor instanceof HTMLAnchorElement)) return null;
      if (!shouldTrackNavigationAnchor(anchor)) return null;
      const href = String(anchor.getAttribute("href") || "").trim();
      if (!href || href.startsWith("#") || href.startsWith("javascript:")) return null;
      try {
        const resolved = new URL(anchor.href, window.location.origin);
        if (!shouldPrefetchNavigationUrl(resolved)) return null;
        return resolved;
      } catch (_error) {
        return null;
      }
    };

    const schedulePrefetch = (anchor, mode = "auto") => {
      const url = normalizeAnchorToUrl(anchor);
      if (!(url instanceof URL)) return;
      const href = url.toString();
      const state = String(prefetchState.get(href) || "");
      if (state === "queued" || state === "running" || state === "done") return;
      if (mode === "auto" && totalQueuedCount >= DASHBOARD_PREFETCH_AUTO_LIMIT) return;
      if (totalQueuedCount >= DASHBOARD_PREFETCH_TOTAL_LIMIT) return;
      markQueued(href);
      prefetchQueue.push(href);
      drainPrefetchQueue();
    };

    const prefetchUrl = async (href) => {
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      let timeoutId = 0;
      if (controller) {
        timeoutId = window.setTimeout(() => controller.abort(), DASHBOARD_PREFETCH_TIMEOUT_MS);
      }
      try {
        const response = await window.fetch(href, {
          method: "GET",
          credentials: "same-origin",
          cache: "force-cache",
          mode: "same-origin",
          redirect: "follow",
          dashboardNoBusy: true,
          dashboardSilent: true,
          signal: controller ? controller.signal : undefined,
        });
        if (response && response.ok) {
          markDone(href);
          return;
        }
        markFailed(href);
      } catch (_error) {
        markFailed(href);
      } finally {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
      }
    };

    const drainPrefetchQueue = () => {
      while (activePrefetchCount < 2 && prefetchQueue.length) {
        const href = prefetchQueue.shift();
        if (!href) continue;
        prefetchState.set(href, "running");
        activePrefetchCount += 1;
        prefetchUrl(href).finally(() => {
          activePrefetchCount = Math.max(0, activePrefetchCount - 1);
          drainPrefetchQueue();
        });
      }
    };

    const queueAutoTargets = () => {
      const anchors = Array.from(document.querySelectorAll(DASHBOARD_PREFETCH_SELECTORS)).filter(
        (node) => node instanceof HTMLAnchorElement
      );
      if (!anchors.length) return;

      const activeIndex = anchors.findIndex((node) =>
        node.classList.contains("active") || node.getAttribute("aria-current") === "page"
      );
      if (activeIndex >= 0) {
        const nearbyIndices = [activeIndex - 1, activeIndex + 1, activeIndex + 2, activeIndex - 2];
        nearbyIndices.forEach((index) => {
          if (index < 0 || index >= anchors.length) return;
          schedulePrefetch(anchors[index], "auto");
        });
      }
      anchors.forEach((anchor) => {
        schedulePrefetch(anchor, "auto");
      });
    };

    const onHintPrefetch = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const anchor = target.closest("a[href]");
      if (!(anchor instanceof HTMLAnchorElement)) return;
      schedulePrefetch(anchor, "hint");
    };

    document.addEventListener("pointerenter", onHintPrefetch, true);
    document.addEventListener("focusin", onHintPrefetch, true);
    document.addEventListener("touchstart", onHintPrefetch, { passive: true, capture: true });

    const kickoff = () => {
      if (document.visibilityState !== "visible") return;
      queueAutoTargets();
    };
    if (typeof window.requestIdleCallback === "function") {
      window.requestIdleCallback(kickoff, { timeout: 1200 });
    } else {
      window.setTimeout(kickoff, 800);
    }
  }

  function initProgressiveSectionReveal() {
    const bootstrap = readDashboardBootstrap();
    const pageMode = String(bootstrap.pageMode || "").trim().toLowerCase();
    if (pageMode !== "dashboard") return;
    try {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        return;
      }
    } catch (_error) {}

    const container = document.querySelector(".dashboard-dynamic-content");
    if (!(container instanceof HTMLElement)) return;

    const isRenderableElement = (node) => {
      if (!(node instanceof HTMLElement)) return false;
      const tag = String(node.tagName || "").toUpperCase();
      if (tag === "SCRIPT" || tag === "STYLE" || tag === "LINK") return false;
      if (node.hasAttribute("data-no-progressive-reveal")) return false;
      return true;
    };

    let chunks = [];
    const stackCandidates = Array.from(container.querySelectorAll(".section-stack")).filter(
      (node) => node instanceof HTMLElement
    );
    for (const stack of stackCandidates) {
      const children = Array.from(stack.children).filter(isRenderableElement);
      if (children.length >= 3) {
        chunks = children;
        break;
      }
    }
    if (!chunks.length) {
      chunks = Array.from(container.children).filter(isRenderableElement);
    }
    if (chunks.length < 3) return;

    chunks.forEach((chunk, index) => {
      chunk.classList.add("dashboard-progressive-chunk");
      if (index < 2) {
        chunk.classList.add("is-visible");
      }
    });

    let cursor = 2;
    const revealMore = () => {
      const nextCursor = Math.min(cursor + DASHBOARD_PROGRESSIVE_REVEAL_BATCH_SIZE, chunks.length);
      for (let index = cursor; index < nextCursor; index += 1) {
        const chunk = chunks[index];
        if (!(chunk instanceof HTMLElement)) continue;
        chunk.classList.add("is-visible");
      }
      cursor = nextCursor;
      if (cursor < chunks.length) {
        window.setTimeout(revealMore, DASHBOARD_PROGRESSIVE_REVEAL_DELAY_MS);
      }
    };

    window.setTimeout(revealMore, 80);
  }

  function releaseInitialPageLoader() {
    if (initialPageBusyDelayTimer) {
      window.clearTimeout(initialPageBusyDelayTimer);
      initialPageBusyDelayTimer = 0;
    }
    if (document.body) {
      document.body.classList.remove("dashboard-boot-loading");
    }
    if (initialPageBusyToken) {
      endBusy(initialPageBusyToken);
      initialPageBusyToken = "";
    }
  }

  function normalizeTagSearchText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function inferTagSearchPlaceholder(name) {
    const isEn = dashboardLanguage() === "en";
    const toLang = (englishText) => {
      if (isEn) return englishText;
      try {
        if (typeof window.dashboardTranslateLoose === "function") {
          const translated = window.dashboardTranslateLoose(englishText, "th");
          if (typeof translated === "string" && translated.trim()) {
            return translated;
          }
        }
      } catch (_error) {
      }
      return englishText;
    };
    const code = String(name || "").trim().toLowerCase();
    if (code.includes("user")) return toLang("Search users...");
    if (code.includes("channel")) return toLang("Search channels...");
    if (code.includes("role")) return toLang("Search roles...");
    return toLang("Search...");
  }

  function getSelectLabelByValue(select, value) {
    if (!(select instanceof HTMLSelectElement)) return "";
    const target = String(value || "");
    if (!target) return "";
    const matched = Array.from(select.options || []).find((option) => String(option.value || "") === target);
    return matched ? String(matched.textContent || matched.label || "").trim() : "";
  }

  function collectComboboxRows(select, query = "", { includePlaceholder = false } = {}) {
    if (!(select instanceof HTMLSelectElement)) return [];
    const needle = normalizeTagSearchText(query);
    const rows = [];
    Array.from(select.options || []).forEach((option, index) => {
      if (!(option instanceof HTMLOptionElement)) return;
      const value = String(option.value || "").trim();
      const label = String(option.textContent || option.label || value).trim();
      const isPlaceholder = index === 0 || !value;
      if (!includePlaceholder && isPlaceholder) return;
      if (option.disabled && !isPlaceholder) return;
      if (needle) {
        const valueText = normalizeTagSearchText(value);
        const labelText = normalizeTagSearchText(label);
        if (!valueText.includes(needle) && !labelText.includes(needle)) return;
      }
      rows.push({ value, label });
    });
    return rows;
  }

  function closeComboboxMenu(wrapper) {
    if (!(wrapper instanceof HTMLElement)) return;
    if (!wrapper.classList.contains("is-open")) return;
    wrapper.classList.remove("is-open");
    releaseComboboxOverflowContext(wrapper);
    const menu = wrapper.querySelector(".dashboard-combobox-menu");
    if (menu instanceof HTMLElement) {
      menu.hidden = true;
      menu.innerHTML = "";
    }
  }

  function openComboboxMenu(wrapper) {
    if (!(wrapper instanceof HTMLElement)) return;
    if (wrapper.classList.contains("is-open")) return;
    wrapper.classList.add("is-open");
    lockComboboxOverflowContext(wrapper);
    const menu = wrapper.querySelector(".dashboard-combobox-menu");
    if (menu instanceof HTMLElement) {
      menu.hidden = false;
    }
  }

  function lockComboboxOverflowContext(wrapper) {
    if (!(wrapper instanceof HTMLElement)) return;
    let node = wrapper.parentElement;
    while (node && node !== document.body) {
      if (node instanceof HTMLElement) {
        const count = Number(node.dataset.comboboxOpenCount || "0");
        node.dataset.comboboxOpenCount = String(count + 1);
        node.classList.add("dashboard-combobox-overflow-open");
      }
      node = node.parentElement;
    }
  }

  function releaseComboboxOverflowContext(wrapper) {
    if (!(wrapper instanceof HTMLElement)) return;
    let node = wrapper.parentElement;
    while (node && node !== document.body) {
      if (node instanceof HTMLElement) {
        const count = Math.max(0, Number(node.dataset.comboboxOpenCount || "0") - 1);
        if (count <= 0) {
          node.dataset.comboboxOpenCount = "";
          node.classList.remove("dashboard-combobox-overflow-open");
        } else {
          node.dataset.comboboxOpenCount = String(count);
        }
      }
      node = node.parentElement;
    }
  }

  function scheduleComboboxClose(wrapper, delayMs = 120) {
    if (!(wrapper instanceof HTMLElement)) return;
    const previousTimer = Number(wrapper.dataset.closeTimerId || "0");
    if (previousTimer > 0) {
      window.clearTimeout(previousTimer);
    }
    const timerId = window.setTimeout(() => {
      closeComboboxMenu(wrapper);
      wrapper.dataset.closeTimerId = "";
    }, Math.max(40, Number(delayMs || 120)));
    wrapper.dataset.closeTimerId = String(timerId);
  }

  function cancelComboboxClose(wrapper) {
    if (!(wrapper instanceof HTMLElement)) return;
    const timerId = Number(wrapper.dataset.closeTimerId || "0");
    if (timerId > 0) {
      window.clearTimeout(timerId);
      wrapper.dataset.closeTimerId = "";
    }
  }

  function renderComboboxMenu({ wrapper, select, query, noResultsText, onChoose, openMenu = true }) {
    if (!(wrapper instanceof HTMLElement)) return;
    if (!(select instanceof HTMLSelectElement)) return;
    const menu = wrapper.querySelector(".dashboard-combobox-menu");
    if (!(menu instanceof HTMLElement)) return;

    const rows = collectComboboxRows(select, query, { includePlaceholder: false });
    menu.innerHTML = "";

    if (rows.length <= 0) {
      const empty = document.createElement("div");
      empty.className = "dashboard-combobox-empty";
      empty.textContent = noResultsText;
      menu.appendChild(empty);
      if (openMenu) {
        openComboboxMenu(wrapper);
      } else {
        closeComboboxMenu(wrapper);
      }
      return;
    }

    const fragment = document.createDocumentFragment();
    rows.slice(0, 240).forEach((row, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "dashboard-combobox-option";
      button.dataset.value = row.value;
      button.dataset.label = row.label;
      if (index === 0) button.dataset.firstOption = "1";
      button.textContent = row.label;
      button.addEventListener("click", () => onChoose(row.value, row.label));
      fragment.appendChild(button);
    });
    menu.appendChild(fragment);
    if (openMenu) {
      openComboboxMenu(wrapper);
    } else {
      closeComboboxMenu(wrapper);
    }
  }

  function applyTagSearchFilter(select, query, { openMenu = true } = {}) {
    if (!(select instanceof HTMLSelectElement)) return;
    const wrap = select.closest(".multi-role-select");
    if (!(wrap instanceof HTMLElement)) return;
    const comboWrap = wrap.querySelector(".tag-search-combo");
    if (!(comboWrap instanceof HTMLElement)) return;
    const roleName = wrap.id.startsWith("multi_") ? wrap.id.slice(6) : "";
    if (!roleName) return;

    renderComboboxMenu({
      wrapper: comboWrap,
      select,
      query,
      noResultsText: inferNoResultsText("role"),
      openMenu,
      onChoose: (value) => {
        select.value = value;
        addTag(select, roleName);
        const searchInput = comboWrap.querySelector("input.tag-search-input");
        if (searchInput instanceof HTMLInputElement) {
          searchInput.value = "";
          searchInput.focus();
        }
        applyTagSearchFilter(select, "");
      },
    });
  }

  function syncTagSearchForSelect(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    const wrap = select.closest(".multi-role-select");
    if (!(wrap instanceof HTMLElement)) return;
    const searchInput = wrap.querySelector("input.tag-search-input");
    applyTagSearchFilter(select, searchInput instanceof HTMLInputElement ? searchInput.value : "", { openMenu: false });
  }

  function mountTagSearchForWrap(wrap) {
    if (!(wrap instanceof HTMLElement)) return;
    const select = wrap.querySelector("select.tag-adder");
    if (!(select instanceof HTMLSelectElement)) return;

    let searchInput = wrap.querySelector("input.tag-search-input");
    if (!(searchInput instanceof HTMLInputElement)) {
      searchInput = document.createElement("input");
      searchInput.type = "text";
      searchInput.className = "tag-search-input";
      searchInput.autocomplete = "off";
      searchInput.setAttribute("data-no-auto-i18n", "1");
    }
    const roleName = wrap.id.startsWith("multi_") ? wrap.id.slice(6) : "";
    searchInput.setAttribute("data-no-auto-i18n", "1");
    searchInput.placeholder = inferTagSearchPlaceholder(roleName);

    let comboWrap = wrap.querySelector(".tag-search-combo");
    if (!(comboWrap instanceof HTMLElement)) {
      comboWrap = document.createElement("div");
      comboWrap.className = "tag-search-combo";
      if (select.parentElement === wrap) {
        wrap.insertBefore(comboWrap, select);
      } else {
        wrap.appendChild(comboWrap);
      }
    }
    if (searchInput.parentElement !== comboWrap) {
      comboWrap.appendChild(searchInput);
    }
    if (select.parentElement !== comboWrap) {
      comboWrap.appendChild(select);
    }
    select.classList.add("tag-adder-hidden");

    let menu = comboWrap.querySelector(".dashboard-combobox-menu");
    if (!(menu instanceof HTMLElement)) {
      menu = document.createElement("div");
      menu.className = "dashboard-combobox-menu";
      menu.hidden = true;
      comboWrap.appendChild(menu);
    }

    if (searchInput.dataset.comboBound !== "1") {
      searchInput.dataset.comboBound = "1";
      searchInput.addEventListener("focus", () => {
        cancelComboboxClose(comboWrap);
        applyTagSearchFilter(select, searchInput.value);
      });
      searchInput.addEventListener("click", () => {
        cancelComboboxClose(comboWrap);
        applyTagSearchFilter(select, searchInput.value);
      });
      searchInput.addEventListener("input", () => {
        applyTagSearchFilter(select, searchInput.value);
      });
      searchInput.addEventListener("blur", () => {
        scheduleComboboxClose(comboWrap, 140);
      });
      searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          closeComboboxMenu(comboWrap);
          return;
        }
        if (event.key === "Enter") {
          const first = comboWrap.querySelector(".dashboard-combobox-option[data-first-option='1']");
          if (first instanceof HTMLButtonElement) {
            event.preventDefault();
            first.click();
          }
          return;
        }
        if (event.key === "ArrowDown") {
          applyTagSearchFilter(select, searchInput.value);
        }
      });
    }

    if (menu.dataset.comboBound !== "1") {
      menu.dataset.comboBound = "1";
      menu.addEventListener("mousedown", (event) => {
        event.preventDefault();
        cancelComboboxClose(comboWrap);
      });
    }

    syncTagSearchForSelect(select);
  }

  function initTagSearchFields(root = document) {
    if (!(root instanceof Document || root instanceof HTMLElement)) return;
    root.querySelectorAll(".multi-role-select").forEach((wrap) => {
      mountTagSearchForWrap(wrap);
    });
  }

  function normalizeDashboardSelectSearchText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function inferSearchableEntityKind(select) {
    if (!(select instanceof HTMLSelectElement)) return "";
    const explicitKind = normalizeDashboardSelectSearchText(
      select.dataset.searchableEntity || select.getAttribute("data-searchable-entity")
    );
    if (explicitKind === "channel" || explicitKind === "role" || explicitKind === "category") {
      return explicitKind;
    }

    const liveKind = normalizeDashboardSelectSearchText(select.dataset.liveOptions);
    if (liveKind === "channel") return "channel";
    if (liveKind === "role") return "role";

    const key = normalizeDashboardSelectSearchText(
      `${select.name || ""} ${select.id || ""} ${select.getAttribute("aria-label") || ""}`
    );
    if (!key) return "";

    const hasKeyword = /(channel|role|category|room)/i.test(key);
    if (!hasKeyword) return "";

    const snowflakeOptionCount = Array.from(select.options || []).filter((option) => {
      if (!(option instanceof HTMLOptionElement)) return false;
      const value = String(option.value || "").trim();
      return /^\d{15,22}$/.test(value);
    }).length;
    if (snowflakeOptionCount <= 0) return "";

    if (/role/i.test(key)) return "role";
    return "channel";
  }

  function inferSearchableSelectPlaceholder(kind) {
    const isEn = dashboardLanguage() === "en";
    const toLang = (englishText) => {
      if (isEn) return englishText;
      try {
        if (typeof window.dashboardTranslateLoose === "function") {
          const translated = window.dashboardTranslateLoose(englishText, "th");
          if (typeof translated === "string" && translated.trim()) {
            return translated;
          }
        }
      } catch (_error) {
      }
      return englishText;
    };
    if (kind === "role") return toLang("Search roles...");
    if (kind === "category") return toLang("Search categories...");
    return toLang("Search channels/categories...");
  }

  function inferNoResultsText(kind) {
    const isEn = dashboardLanguage() === "en";
    if (kind === "role") {
      return isEn ? "No matching roles found" : "ไม่พบยศที่ตรงกับคำค้นหา";
    }
    if (kind === "category") {
      return isEn ? "No matching categories found" : "ไม่พบหมวดหมู่ที่ตรงกับคำค้นหา";
    }
    return isEn ? "No matching channels found" : "ไม่พบห้องที่ตรงกับคำค้นหา";
  }

  function applyDashboardSelectSearchFilter(select, query) {
    if (!(select instanceof HTMLSelectElement)) return;
    const wrapper = select.closest(".dashboard-searchable-select");
    if (!(wrapper instanceof HTMLElement)) return;
    const kind = String(wrapper.dataset.searchKind || "");
    renderComboboxMenu({
      wrapper,
      select,
      query,
      noResultsText: inferNoResultsText(kind || "channel"),
      onChoose: (value, label) => {
        if (String(select.value || "") !== String(value || "")) {
          select.value = String(value || "");
          notifyFormMutationFromField(select);
        }
        const input = wrapper.querySelector("input.dashboard-select-search-input");
        if (input instanceof HTMLInputElement) {
          input.value = label;
        }
        closeComboboxMenu(wrapper);
      },
    });
  }

  function ensureSearchableSelectContainer(select) {
    if (!(select instanceof HTMLSelectElement)) return null;
    const currentParent = select.parentElement;
    if (currentParent instanceof HTMLElement && currentParent.classList.contains("dashboard-searchable-select")) {
      return currentParent;
    }
    if (!(currentParent instanceof HTMLElement)) return null;
    const wrapper = document.createElement("div");
    wrapper.className = "dashboard-searchable-select";
    currentParent.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    return wrapper;
  }

  function syncDashboardSearchableSelect(select) {
    if (!(select instanceof HTMLSelectElement)) return;
    if (select.closest(".multi-role-select")) return;
    if (String(select.dataset.searchableSkip || "").trim() === "1") return;

    const kind = inferSearchableEntityKind(select);
    if (!kind) return;

    const wrapper = ensureSearchableSelectContainer(select);
    if (!(wrapper instanceof HTMLElement)) return;
    wrapper.dataset.searchKind = kind;

    let searchInput = wrapper.querySelector("input.dashboard-select-search-input");
    if (!(searchInput instanceof HTMLInputElement)) {
      searchInput = document.createElement("input");
      searchInput.type = "text";
      searchInput.className = "dashboard-select-search-input";
      searchInput.autocomplete = "off";
      searchInput.setAttribute("data-no-auto-i18n", "1");
      wrapper.insertBefore(searchInput, select);
    }
    searchInput.setAttribute("data-no-auto-i18n", "1");
    searchInput.placeholder = inferSearchableSelectPlaceholder(kind);
    searchInput.disabled = Boolean(select.disabled);
    select.classList.add("dashboard-select-native-hidden");

    let menu = wrapper.querySelector(".dashboard-combobox-menu");
    if (!(menu instanceof HTMLElement)) {
      menu = document.createElement("div");
      menu.className = "dashboard-combobox-menu";
      menu.hidden = true;
      wrapper.appendChild(menu);
    }

    if (searchInput.dataset.comboBound !== "1") {
      searchInput.dataset.comboBound = "1";
      searchInput.addEventListener("focus", () => {
        cancelComboboxClose(wrapper);
        applyDashboardSelectSearchFilter(select, "");
      });
      searchInput.addEventListener("click", () => {
        cancelComboboxClose(wrapper);
        applyDashboardSelectSearchFilter(select, "");
      });
      searchInput.addEventListener("input", () => {
        applyDashboardSelectSearchFilter(select, searchInput.value);
      });
      searchInput.addEventListener("blur", () => {
        scheduleComboboxClose(wrapper, 140);
        searchInput.value = getSelectLabelByValue(select, select.value);
      });
      searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          closeComboboxMenu(wrapper);
          searchInput.value = getSelectLabelByValue(select, select.value);
          return;
        }
        if (event.key === "Enter") {
          const first = wrapper.querySelector(".dashboard-combobox-option[data-first-option='1']");
          if (first instanceof HTMLButtonElement) {
            event.preventDefault();
            first.click();
          }
          return;
        }
        if (event.key === "ArrowDown") {
          applyDashboardSelectSearchFilter(select, "");
        }
      });
    }

    if (menu.dataset.comboBound !== "1") {
      menu.dataset.comboBound = "1";
      menu.addEventListener("mousedown", (event) => {
        event.preventDefault();
        cancelComboboxClose(wrapper);
      });
    }

    if (document.activeElement !== searchInput) {
      searchInput.value = getSelectLabelByValue(select, select.value);
    }
  }

  function initDashboardSearchableSelects(root = document) {
    if (!(root instanceof Document || root instanceof HTMLElement)) return;
    if (root instanceof HTMLSelectElement) {
      syncDashboardSearchableSelect(root);
      return;
    }
    root.querySelectorAll("select").forEach((select) => {
      syncDashboardSearchableSelect(select);
    });
  }

  function initDashboardSearchableSelectObserver() {
    const observerRoot = document.querySelector(".dashboard-dynamic-content") || document.body;
    if (!(observerRoot instanceof HTMLElement)) return;
    let queued = false;
    const scheduleRefresh = () => {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(() => {
        queued = false;
        initDashboardSearchableSelects(observerRoot);
      });
    };

    const observer = new MutationObserver((mutations) => {
      let shouldRefresh = false;
      for (const mutation of mutations) {
        if (mutation.type === "childList" || mutation.type === "attributes") {
          shouldRefresh = true;
          break;
        }
      }
      if (shouldRefresh) {
        scheduleRefresh();
      }
    });
    observer.observe(observerRoot, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["disabled"],
    });

    document.addEventListener(
      "click",
      (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        document.querySelectorAll(".dashboard-searchable-select.is-open, .tag-search-combo.is-open").forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          if (node.contains(target)) return;
          closeComboboxMenu(node);
        });
      },
      true
    );
  }

  function notifyFormMutationFromField(field) {
    if (!(field instanceof HTMLElement)) return;
    const eventOptions = { bubbles: true };
    try {
      field.dispatchEvent(new Event("input", eventOptions));
    } catch (_error) {}
    try {
      field.dispatchEvent(new Event("change", eventOptions));
    } catch (_error) {}
    const form = field.closest("form");
    if (form instanceof HTMLFormElement) {
      try {
        form.dispatchEvent(new Event("dashboard:dirty-check", eventOptions));
      } catch (_error) {}
    }
  }

  function addTag(select, name) {
    const value = select.value;
    if (!value) return;
    const text = select.options[select.selectedIndex].text;
    const container = document.getElementById("tags_" + name);
    const input = document.getElementById("input_" + name);
    if (!container || !input) return;

    const currentValues = input.value ? input.value.split(",") : [];
    if (currentValues.includes(value)) return;

    currentValues.push(value);
    input.value = currentValues.join(",");
    notifyFormMutationFromField(input);

    const tag = document.createElement("div");
    tag.className = "tag-pill";
    tag.dataset.id = value;
    tag.innerHTML = `${text} <span class="remove" onclick="removeTag(this, '${name}')">&times;</span>`;
    container.appendChild(tag);

    select.value = "";
    syncTagSearchForSelect(select);
    if (typeof window.__refreshLiveRoleOptions === "function") {
      window.__refreshLiveRoleOptions();
    }
  }

  function removeTag(span, name) {
    const tag = span && span.parentElement;
    if (!tag) return;
    const id = tag.dataset.id;
    const input = document.getElementById("input_" + name);
    if (!input) return;

    const currentValues = input.value ? input.value.split(",") : [];
    input.value = currentValues.filter((v) => v !== id).join(",");
    notifyFormMutationFromField(input);
    tag.remove();

    const wrap = document.getElementById("multi_" + name);
    if (wrap) {
      const select = wrap.querySelector("select.tag-adder");
      syncTagSearchForSelect(select);
    }

    if (typeof window.__refreshLiveRoleOptions === "function") {
      window.__refreshLiveRoleOptions();
    }
  }

  function detectNoticeType(text) {
    const lower = String(text || "").toLowerCase();
    if (
      lower.includes("error") ||
      lower.includes("fail") ||
      lower.includes("invalid") ||
      lower.includes("ผิดพลาด") ||
      lower.includes("ล้มเหลว")
    ) {
      return "error";
    }
    if (lower.includes("warn") || lower.includes("เตือน")) {
      return "warning";
    }
    return "success";
  }

  function clearTransientNoticeBanners() {
    const banners = document.querySelectorAll('.notice[data-transient-notice="1"]');
    banners.forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      node.style.transition = "opacity 0.22s ease, transform 0.22s ease";
      node.style.opacity = "0";
      node.style.transform = "translateY(-6px)";
      window.setTimeout(() => node.remove(), 240);
    });
  }

  function bootstrapNotices() {
    const urlParams = new URLSearchParams(window.location.search);
    const notice = urlParams.get("notice");
    if (!notice) return;
    showToast(notice, detectNoticeType(notice));
    window.setTimeout(clearTransientNoticeBanners, 60);
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  const DASHBOARD_SCROLL_RESTORE_KEY = "dashboard:scroll-restore";
  const DASHBOARD_SCROLL_RESTORE_MAX_AGE_MS = 2 * 60 * 1000;

  function persistDashboardScrollPosition() {
    try {
      const payload = {
        x: Math.max(0, Number(window.scrollX || 0)),
        y: Math.max(0, Number(window.scrollY || 0)),
        path: String(window.location.pathname || ""),
        ts: Date.now(),
      };
      window.sessionStorage.setItem(DASHBOARD_SCROLL_RESTORE_KEY, JSON.stringify(payload));
    } catch (_error) {}
  }

  function restoreDashboardScrollPosition() {
    let payload = null;
    try {
      const raw = window.sessionStorage.getItem(DASHBOARD_SCROLL_RESTORE_KEY);
      if (!raw) return;
      window.sessionStorage.removeItem(DASHBOARD_SCROLL_RESTORE_KEY);
      payload = JSON.parse(raw);
    } catch (_error) {
      return;
    }

    if (!payload || typeof payload !== "object") return;
    if (String(payload.path || "") !== String(window.location.pathname || "")) return;
    if (Math.abs(Date.now() - Number(payload.ts || 0)) > DASHBOARD_SCROLL_RESTORE_MAX_AGE_MS) return;

    const targetX = Math.max(0, Number(payload.x || 0));
    const targetY = Math.max(0, Number(payload.y || 0));
    const maxAttempts = 18;
    let attempts = 0;

    const applyRestore = () => {
      attempts += 1;
      const maxScrollY = Math.max(
        0,
        Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) - window.innerHeight
      );
      const safeY = Math.min(targetY, maxScrollY);
      window.scrollTo(targetX, safeY);
      if (safeY + 2 >= targetY || attempts >= maxAttempts) return;
      window.requestAnimationFrame(applyRestore);
    };

    window.requestAnimationFrame(applyRestore);
  }

  function initDashboardScrollPersistenceGuards() {
    const currentPath = String(window.location.pathname || "");
    if (!currentPath.startsWith("/dashboard")) return;

    document.addEventListener(
      "submit",
      (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        persistDashboardScrollPosition();
      },
      true
    );

    document.addEventListener(
      "click",
      (event) => {
        if (event.defaultPrevented) return;
        if (event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

        const target = event.target;
        if (!(target instanceof Element)) return;
        const anchor = target.closest("a[href]");
        if (!(anchor instanceof HTMLAnchorElement)) return;
        if (anchor.hasAttribute("download")) return;
        if (String(anchor.getAttribute("target") || "").trim() && String(anchor.getAttribute("target") || "").trim() !== "_self") return;

        let nextUrl = null;
        try {
          nextUrl = new URL(anchor.href, window.location.origin);
        } catch (_error) {
          return;
        }
        if (!nextUrl) return;
        if (nextUrl.origin !== window.location.origin) return;
        if (String(nextUrl.pathname || "") !== currentPath) return;
        if (nextUrl.hash && !nextUrl.search) return;

        persistDashboardScrollPosition();
      },
      true
    );
  }

  function readDashboardBootstrap() {
    const node = document.getElementById("dashboard-bootstrap");
    if (!node) return {};
    const raw = String(node.textContent || "{}");
    try {
      return JSON.parse(raw);
    } catch (_error) {
      const textarea = document.createElement("textarea");
      textarea.innerHTML = raw;
      try {
        return JSON.parse(String(textarea.value || "{}"));
      } catch (_innerError) {
        return {};
      }
    }
  }

  function formatDiscordRuntimeNotice(state) {
    const payload = state && typeof state === "object" ? state : {};
    const level = String(payload.level || "").trim().toLowerCase();
    if (!level || level === "ok") return { message: "", kind: "" };

    const statusCode = Number(payload.status_code);
    const retryAfter = Number(payload.retry_after);
    const stateMessage = String(payload.message || "").trim();
    const statusText = Number.isFinite(statusCode) && statusCode > 0 ? `HTTP ${Math.floor(statusCode)}` : "HTTP ไม่ทราบรหัส";
    const retryText =
      Number.isFinite(retryAfter) && retryAfter > 0
        ? ` ระบบกำลังลองเชื่อมต่อใหม่ใน ${Math.max(1, Math.round(retryAfter))} วินาที`
        : "";

    const kind =
      level === "outage" || level === "auth_error" || level === "stopped"
        ? "outage"
        : (level === "degraded" || level === "starting" ? "degraded" : "");
    if (!kind) {
      return { message: "", kind: "" };
    }
    if (stateMessage) {
      return { message: `${stateMessage}${retryText}`, kind };
    }
    const fallback =
      kind === "outage"
        ? `Discord ไม่พร้อมใช้งานชั่วคราว (${statusText}) บางฟีเจอร์อาจใช้งานไม่ได้.${retryText}`
        : `Discord กำลังมีปัญหา/จำกัดการเรียกใช้งาน (${statusText}) อาจช้า หรือใช้บางฟีเจอร์ไม่ได้ชั่วคราว.${retryText}`;
    return { message: fallback, kind };
  }

  function upsertDiscordOutageBanner(noticePayload) {
    const container = document.querySelector(".dashboard-dynamic-content");
    if (!(container instanceof HTMLElement)) return;
    const payload = noticePayload && typeof noticePayload === "object" ? noticePayload : {};
    const message = String(payload.message || "");
    const kind = String(payload.kind || "");

    let node = container.querySelector('[data-discord-runtime-banner="1"]');
    if (message && kind) {
      if (!(node instanceof HTMLElement)) {
        node = document.createElement("div");
        node.setAttribute("data-discord-runtime-banner", "1");
        container.prepend(node);
      }
      node.className = `notice ${kind === "outage" ? "notice-discord-outage" : "notice-discord-degraded"}`;
      node.textContent = String(message);
      return;
    }

    if (node instanceof HTMLElement) {
      node.remove();
    }
  }

  function initDiscordRuntimeBanner() {
    const bootstrap = readDashboardBootstrap();
    upsertDiscordOutageBanner(formatDiscordRuntimeNotice(bootstrap.discordRuntime));
    const currentPath = String(window.location.pathname || "");
    const pageMode = String(bootstrap.pageMode || "").trim().toLowerCase();
    const shouldSkipPolling =
      currentPath.startsWith("/dashboard/donate/") ||
      pageMode === "landing";
    if (shouldSkipPolling) return;

    const RUNTIME_POLL_VISIBLE_MS = 60000;
    const RUNTIME_POLL_HIDDEN_MS = 180000;
    let polling = false;
    let pollTimer = 0;
    const runWhenIdle = (callback, timeoutMs = 2500) => {
      if (typeof window.requestIdleCallback === "function") {
        window.requestIdleCallback(callback, { timeout: timeoutMs });
      } else {
        window.setTimeout(callback, Math.min(timeoutMs, 1200));
      }
    };
    const scheduleNextPoll = (ms) => {
      if (pollTimer) {
        window.clearTimeout(pollTimer);
      }
      pollTimer = window.setTimeout(() => {
        pollRuntime();
      }, Math.max(1000, Number(ms) || RUNTIME_POLL_VISIBLE_MS));
    };

    const pollRuntime = async (force = false) => {
      if (polling) return;
      if (!force && document.visibilityState !== "visible") {
        scheduleNextPoll(RUNTIME_POLL_HIDDEN_MS);
        return;
      }
      polling = true;
      try {
        const response = await fetch("/dashboard/runtime/discord?compact=1", {
          method: "GET",
          credentials: "same-origin",
          cache: "no-cache",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        const payload = await response.json();
        upsertDiscordOutageBanner(formatDiscordRuntimeNotice(payload));
      } catch (_error) {
      } finally {
        polling = false;
        const nextDelay = document.visibilityState === "visible"
          ? RUNTIME_POLL_VISIBLE_MS
          : RUNTIME_POLL_HIDDEN_MS;
        scheduleNextPoll(nextDelay);
      }
    };

    runWhenIdle(() => pollRuntime(true), 2600);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        pollRuntime(true);
      }
    });
  }

  function normalizeText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function markDirtyBeforeUnloadSuppressed(timeoutMs = 20000) {
    const safeTimeout = Math.max(1000, Number(timeoutMs) || 0);
    suppressDirtyBeforeUnloadUntil = Date.now() + safeTimeout;
  }

  function isDirtyBeforeUnloadSuppressed() {
    return Date.now() < suppressDirtyBeforeUnloadUntil;
  }

  function patchProgrammaticFormSubmitSuppression() {
    if (
      typeof HTMLFormElement === "undefined" ||
      !HTMLFormElement.prototype ||
      typeof HTMLFormElement.prototype.submit !== "function"
    ) {
      return;
    }
    if (HTMLFormElement.prototype.submit.__dashboardDirtyPatched === true) {
      return;
    }
    const nativeSubmit = HTMLFormElement.prototype.submit;
    const wrappedSubmit = function (...args) {
      markDirtyBeforeUnloadSuppressed(25000);
      return nativeSubmit.apply(this, args);
    };
    wrappedSubmit.__dashboardDirtyPatched = true;
    HTMLFormElement.prototype.submit = wrappedSubmit;
  }

  function controlText(control) {
    if (!control) return "";
    if (control instanceof HTMLInputElement) {
      return normalizeText(
        control.value || control.getAttribute("value") || control.getAttribute("aria-label") || ""
      );
    }
    if (control instanceof HTMLElement) {
      return normalizeText(
        control.textContent || control.getAttribute("aria-label") || control.getAttribute("title") || ""
      );
    }
    return "";
  }

  function isSaveActionControl(control) {
    const text = controlText(control);
    if (!text) return false;
    const saveKeywords = [
      "บันทึก",
      "save",
      "อัปเดต",
      "update",
      "apply",
      "submit changes",
      "save changes",
      "save settings",
    ];
    return saveKeywords.some((kw) => text.includes(kw));
  }

  function isResetActionControl(control) {
    const text = controlText(control);
    if (!text) return false;
    const resetKeywords = ["รีเซ็ต", "reset", "discard", "ยกเลิก", "cancel"];
    return resetKeywords.some((kw) => text.includes(kw));
  }

  function isSaveSubmitControl(control) {
    if (!(control instanceof HTMLButtonElement || control instanceof HTMLInputElement)) return false;
    const inputType =
      control instanceof HTMLInputElement ? normalizeText(control.type || "") : "button";
    const buttonType =
      control instanceof HTMLButtonElement ? normalizeText(control.getAttribute("type") || "submit") : "";
    const isSubmitControl = inputType === "submit" || buttonType === "submit";
    if (!isSubmitControl) return false;
    return isSaveActionControl(control);
  }

  function isLikelySettingsForm(form) {
    if (!(form instanceof HTMLFormElement)) return false;
    const method = normalizeText(form.getAttribute("method") || "get");
    if (method !== "post") return false;
    const action = normalizeText(form.getAttribute("action") || "");
    const isGuildSettingsAction = action.includes("/dashboard/guild/");
    const isOwnerbotAdminAction = action.includes("/dashboard/admin/ownerbot/");
    if (!isGuildSettingsAction && !isOwnerbotAdminAction) return false;
    if (form.hasAttribute("data-no-discord-savebar")) return false;

    const submitControls = Array.from(
      form.querySelectorAll('button[type="submit"], input[type="submit"]')
    );
    const hasSaveSubmit = submitControls.some((control) => isSaveSubmitControl(control));
    if (!hasSaveSubmit) return false;

    const editableFieldCount = form.querySelectorAll(
      'input[name], select[name], textarea[name]'
    ).length;
    return editableFieldCount > 0;
  }

  function serializeForm(form) {
    const rows = [];
    const formData = new FormData(form);
    for (const [key, value] of formData.entries()) {
      if (value instanceof File) {
        rows.push([String(key), `__file:${value.name}:${value.size}:${value.type}`]);
      } else {
        rows.push([String(key), String(value)]);
      }
    }
    const fileInputs = Array.from(form.querySelectorAll('input[type="file"][name]'));
    fileInputs.forEach((input) => {
      const files = Array.from(input.files || []);
      const digest = files.map((f) => `${f.name}:${f.size}:${f.type}`).join("|");
      rows.push([`__fileinput__${String(input.name)}`, digest]);
    });
    rows.sort((a, b) => {
      const ak = `${a[0]}::${a[1]}`;
      const bk = `${b[0]}::${b[1]}`;
      if (ak < bk) return -1;
      if (ak > bk) return 1;
      return 0;
    });
    return JSON.stringify(rows);
  }

  function createGlobalDirtyBar() {
    const bar = document.createElement("div");
    bar.className = "dashboard-dirty-bar";
    bar.hidden = true;
    bar.innerHTML = `
      <div class="dashboard-dirty-text">ระวัง - คุณมีการเปลี่ยนแปลงที่ไม่ได้บันทึก</div>
      <div class="dashboard-dirty-actions">
        <button type="button" class="ghost-btn dirty-reset-btn" data-dirty-action="reset">รีเซ็ต</button>
        <button type="button" class="primary-btn" data-dirty-action="save">บันทึกการเปลี่ยนแปลง</button>
      </div>
    `;
    document.body.appendChild(bar);
    return bar;
  }

  function initDiscordLikeSaveBar() {
    const forms = Array.from(document.querySelectorAll("form")).filter((form) =>
      isLikelySettingsForm(form)
    );
    if (!forms.length) return;

    const dirtyBar = createGlobalDirtyBar();
    const resetButton = dirtyBar.querySelector('[data-dirty-action="reset"]');
    const saveButton = dirtyBar.querySelector('[data-dirty-action="save"]');
    const formState = new Map();
    let activeForm = null;
    const dirtyWarningText = () =>
      dashboardLanguage() === "en"
        ? "You have unsaved changes. Please Save or Reset before leaving this page."
        : "คุณมีการเปลี่ยนแปลงที่ยังไม่บันทึก กรุณากด บันทึก หรือ รีเซ็ต ก่อนเปลี่ยนหน้า";

    const dirtyForms = () => forms.filter((form) => formState.get(form)?.dirty);
    const resolveActiveDirtyForm = () => {
      if (activeForm && formState.get(activeForm)?.dirty) {
        return activeForm;
      }
      const current = dirtyForms()[0] || null;
      activeForm = current;
      return current;
    };

    const syncBarVisibility = () => {
      const currentDirtyForms = dirtyForms();
      if (!currentDirtyForms.length) {
        activeForm = null;
        dirtyBar.hidden = true;
        document.body.classList.remove("dashboard-dirty-open");
        return;
      }
      if (!activeForm || !formState.get(activeForm)?.dirty) {
        activeForm = currentDirtyForms[0];
      }
      dirtyBar.hidden = false;
      document.body.classList.add("dashboard-dirty-open");
    };

    const pulseDirtyBar = () => {
      dirtyBar.classList.remove("dashboard-dirty-bar-attention");
      void dirtyBar.offsetWidth;
      dirtyBar.classList.add("dashboard-dirty-bar-attention");
      window.setTimeout(() => {
        dirtyBar.classList.remove("dashboard-dirty-bar-attention");
      }, 1100);
    };

    const cssEscape = (value) => {
      const text = String(value || "").trim();
      if (!text) return "";
      if (window.CSS && typeof window.CSS.escape === "function") {
        return window.CSS.escape(text);
      }
      return text.replace(/["\\]/g, "\\$&");
    };

    const clickFirstSelector = (selectors) => {
      const list = Array.isArray(selectors) ? selectors : [selectors];
      for (const selector of list) {
        const text = String(selector || "").trim();
        if (!text) continue;
        const target = document.querySelector(text);
        if (!(target instanceof HTMLElement)) continue;
        try {
          target.click();
          return true;
        } catch (_error) {}
      }
      return false;
    };

    const revealFormSection = (form) => {
      if (!(form instanceof HTMLElement)) return;
      const ownerbotSubtabPanel = form.closest("[data-ownerbot-subtab-panel]");
      if (ownerbotSubtabPanel instanceof HTMLElement) {
        const subtabKey = String(
          ownerbotSubtabPanel.getAttribute("data-ownerbot-subtab-panel") || ""
        ).trim();
        if (subtabKey) {
          const escapedKey = cssEscape(subtabKey);
          clickFirstSelector(`[data-ownerbot-subtab-trigger="${escapedKey}"]`);
        }
      }
      const ownerbotSectionGroup = form.closest("[data-ownerbot-section]");
      if (ownerbotSectionGroup instanceof HTMLElement) {
        const sectionKey = String(
          ownerbotSectionGroup.getAttribute("data-ownerbot-section") || ""
        ).trim();
        if (sectionKey) {
          const escapedSection = cssEscape(sectionKey);
          clickFirstSelector(`[data-ownerbot-section-tab="${escapedSection}"]`);
        }
      }

      const section = form.closest("[id], .panel, .panel-sub, section");
      if (!(section instanceof HTMLElement)) return;

      const sectionId = String(section.id || "").trim();
      if (sectionId) {
        const selectorId = cssEscape(sectionId);
        clickFirstSelector([
          `[data-target="${selectorId}"]`,
          `[data-tab-target="${selectorId}"]`,
          `[data-section="${selectorId}"]`,
          `[href="#${selectorId}"]`,
        ]);
      }

      section.classList.remove("dashboard-dirty-section-attention");
      void section.offsetWidth;
      section.classList.add("dashboard-dirty-section-attention");
      window.setTimeout(() => {
        section.classList.remove("dashboard-dirty-section-attention");
      }, 1400);
    };

    const focusDirtyForm = (form) => {
      if (!(form instanceof HTMLFormElement)) return;
      activeForm = form;
      syncBarVisibility();
      revealFormSection(form);
      pulseDirtyBar();
      form.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      const firstEditable = form.querySelector("input, select, textarea");
      if (firstEditable instanceof HTMLElement) {
        window.setTimeout(() => {
          try {
            firstEditable.focus({ preventScroll: true });
          } catch (_error) {
            firstEditable.focus();
          }
        }, 140);
      }
    };

    const blockNavigationWithDirtyState = (event) => {
      const dirtyForm = resolveActiveDirtyForm();
      if (!dirtyForm) return false;
      if (event) {
        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === "function") {
          event.stopImmediatePropagation();
        }
      }
      focusDirtyForm(dirtyForm);
      notifyOperation(dirtyWarningText(), "warning", { dedupeWindowMs: 1000 });
      return true;
    };

    const markFormDirtyState = (form) => {
      const state = formState.get(form);
      if (!state) return;
      const current = serializeForm(form);
      state.dirty = current !== state.initial;
      if (state.dirty) activeForm = form;
      syncBarVisibility();
    };

    const queueFormDirtyStateCheck = (form) => {
      const state = formState.get(form);
      if (!state || state.pendingCheck) return;
      state.pendingCheck = true;
      window.requestAnimationFrame(() => {
        const latestState = formState.get(form);
        if (!latestState) return;
        latestState.pendingCheck = false;
        markFormDirtyState(form);
      });
    };

    const resolveFormActionUrl = (form) => {
      if (!(form instanceof HTMLFormElement)) return null;
      const rawAction = String(form.getAttribute("action") || "").trim();
      const fallback = String(window.location.href || "");
      try {
        return new URL(rawAction || fallback, window.location.origin);
      } catch (_error) {
        return null;
      }
    };

    const normalizeUrlForInPlaceSubmit = (urlValue) => {
      let url = null;
      try {
        url =
          urlValue instanceof URL
            ? new URL(urlValue.toString(), window.location.origin)
            : new URL(String(urlValue || ""), window.location.origin);
      } catch (_error) {
        return "";
      }
      url.hash = "";
      url.searchParams.delete("notice");
      const query = url.searchParams.toString();
      return `${String(url.pathname || "")}${query ? `?${query}` : ""}`;
    };

    const extractNoticeFromUrl = (urlValue) => {
      let url = null;
      try {
        url =
          urlValue instanceof URL
            ? new URL(urlValue.toString(), window.location.origin)
            : new URL(String(urlValue || ""), window.location.origin);
      } catch (_error) {
        return "";
      }
      const rawNotice = String(url.searchParams.get("notice") || "").trim();
      if (!rawNotice) return "";
      try {
        return decodeURIComponent(rawNotice).trim();
      } catch (_error) {
        return rawNotice;
      }
    };

    const commitCurrentFormDefaults = (form) => {
      if (!(form instanceof HTMLFormElement)) return;
      Array.from(form.elements || []).forEach((node) => {
        if (!(node instanceof HTMLElement)) return;
        if (node instanceof HTMLSelectElement) {
          Array.from(node.options || []).forEach((option) => {
            if (!(option instanceof HTMLOptionElement)) return;
            option.defaultSelected = option.selected;
          });
          return;
        }
        if (node instanceof HTMLTextAreaElement) {
          node.defaultValue = String(node.value || "");
          return;
        }
        if (!(node instanceof HTMLInputElement)) return;
        const inputType = normalizeText(node.type || "");
        if (inputType === "file") return;
        if (inputType === "checkbox" || inputType === "radio") {
          node.defaultChecked = node.checked;
          return;
        }
        node.defaultValue = String(node.value || "");
      });
    };

    const buildFormPayload = (form, submitter) => {
      let formData = null;
      if (submitter instanceof HTMLElement) {
        try {
          formData = new FormData(form, submitter);
        } catch (_error) {
          formData = null;
        }
      }
      if (!(formData instanceof FormData)) {
        formData = new FormData(form);
      }

      if (
        submitter instanceof HTMLButtonElement ||
        submitter instanceof HTMLInputElement
      ) {
        const submitterName = String(submitter.getAttribute("name") || "").trim();
        if (submitterName && !formData.has(submitterName)) {
          formData.append(submitterName, String(submitter.value || ""));
        }
      }

      const enctype = normalizeText(form.getAttribute("enctype") || "application/x-www-form-urlencoded");
      if (enctype === "multipart/form-data") {
        return { body: formData, headers: {} };
      }

      const params = new URLSearchParams();
      for (const [key, value] of formData.entries()) {
        if (value instanceof File) {
          params.append(String(key), String(value.name || ""));
        } else {
          params.append(String(key), String(value));
        }
      }
      return {
        body: params,
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
      };
    };

    const canSubmitFormInPlace = (form, submitter) => {
      if (!(form instanceof HTMLFormElement)) return false;
      if (form.dataset.noAsyncSubmit === "1" || form.dataset.forcePageReload === "1") return false;
      if (submitter instanceof HTMLElement) {
        if (submitter.dataset.noAsyncSubmit === "1" || submitter.dataset.forcePageReload === "1") return false;
      }
      const method =
        submitter instanceof HTMLButtonElement || submitter instanceof HTMLInputElement
          ? normalizeText(submitter.getAttribute("formmethod") || form.getAttribute("method") || "post")
          : normalizeText(form.getAttribute("method") || "post");
      if (!["post", "put", "patch", "delete"].includes(method)) return false;

      const targetAttr =
        submitter instanceof HTMLButtonElement || submitter instanceof HTMLInputElement
          ? String(submitter.getAttribute("formtarget") || form.getAttribute("target") || "").trim()
          : String(form.getAttribute("target") || "").trim();
      if (targetAttr && targetAttr !== "_self") return false;

      const actionUrl = resolveFormActionUrl(form);
      if (!(actionUrl instanceof URL)) return false;
      if (actionUrl.origin !== window.location.origin) return false;
      const path = String(actionUrl.pathname || "");
      return path.startsWith("/dashboard/guild/");
    };

    const finalizeAsyncSavedForm = (form) => {
      const state = formState.get(form);
      if (!state) return;
      commitCurrentFormDefaults(form);
      state.initial = serializeForm(form);
      state.dirty = false;
      state.pendingCheck = false;
      state.submitting = false;
      syncBarVisibility();
    };

    const submitFormInPlace = async (form, submitter) => {
      const state = formState.get(form);
      if (!state || state.submitting) return;
      state.submitting = true;
      activeForm = form;
      dirtyBar.hidden = true;
      document.body.classList.remove("dashboard-dirty-open");

      let handoffToNavigation = false;
      try {
        if (!submitBusyState.get(form)) {
          beginFormSubmitState(form, submitter);
        }
        const actionUrl = resolveFormActionUrl(form);
        if (!(actionUrl instanceof URL)) {
          throw new Error(feedbackText("requestFailed", { status: "?" }));
        }
        const formMethod =
          submitter instanceof HTMLButtonElement || submitter instanceof HTMLInputElement
            ? String(submitter.getAttribute("formmethod") || form.getAttribute("method") || "POST").trim().toUpperCase()
            : String(form.getAttribute("method") || "POST").trim().toUpperCase();
        const payload = buildFormPayload(form, submitter);
        const headers = {
          Accept: "text/html,application/json;q=0.9,*/*;q=0.8",
          "X-Requested-With": "fetch",
          ...(payload.headers || {}),
        };
        const response = await fetch(actionUrl.toString(), {
          method: formMethod || "POST",
          body: payload.body,
          credentials: "same-origin",
          cache: "no-store",
          redirect: "follow",
          headers,
          dashboardNoBusy: true,
          dashboardSilent: true,
        });

        const responseUrl = (() => {
          try {
            return new URL(String(response.url || actionUrl.toString()), window.location.origin);
          } catch (_error) {
            return actionUrl;
          }
        })();

        if (!response.ok) {
          const noticeText = extractNoticeFromUrl(responseUrl) || httpFailureMessage(response.status);
          throw new Error(noticeText);
        }

        const currentComparable = normalizeUrlForInPlaceSubmit(window.location.href);
        const nextComparable = normalizeUrlForInPlaceSubmit(responseUrl);
        if (nextComparable && currentComparable && nextComparable !== currentComparable) {
          handoffToNavigation = true;
          persistDashboardScrollPosition();
          window.location.href = responseUrl.toString();
          return;
        }

        const noticeText = extractNoticeFromUrl(responseUrl);
        if (noticeText) {
          notifyOperation(noticeText, detectNoticeType(noticeText), { dedupeWindowMs: 800 });
        }

        try {
          const addressUrl = new URL(responseUrl.toString());
          addressUrl.searchParams.delete("notice");
          if (addressUrl.toString() !== window.location.href) {
            window.history.replaceState({}, document.title, addressUrl.toString());
          }
        } catch (_error) {}

        if (typeof window.__initTagSearchFields === "function") {
          window.__initTagSearchFields(form);
        }
        if (typeof window.__initDashboardSearchableSelects === "function") {
          window.__initDashboardSearchableSelects(form);
        }
        if (typeof window.__refreshLiveRoleOptions === "function") {
          window.__refreshLiveRoleOptions();
        }

        finalizeAsyncSavedForm(form);
      } catch (error) {
        const fallbackError = feedbackText("networkError");
        const message =
          error instanceof Error
            ? String(error.message || "").trim()
            : "";
        notifyOperation(message || fallbackError, "error");
        const latestState = formState.get(form);
        if (latestState) {
          latestState.submitting = false;
        }
        queueFormDirtyStateCheck(form);
      } finally {
        if (!handoffToNavigation) {
          clearSubmitState(form);
        }
      }
    };

    forms.forEach((form) => {
      const submitControls = Array.from(
        form.querySelectorAll('button[type="submit"], input[type="submit"]')
      );
      submitControls.forEach((control) => {
        if (isSaveSubmitControl(control)) {
          control.classList.add("dashboard-managed-save-hidden");
        }
      });

      const actionBlocks = Array.from(form.querySelectorAll(".form-actions-fixed, .econ-savebar"));
      actionBlocks.forEach((block) => {
        const actionControls = Array.from(
          block.querySelectorAll("button, input[type='submit'], a[href]")
        );
        if (!actionControls.length) return;
        const hasSave = actionControls.some((control) => isSaveActionControl(control));
        if (!hasSave) return;
        const hasNonSaveAction = actionControls.some(
          (control) => !isSaveActionControl(control) && !isResetActionControl(control)
        );
        if (!hasNonSaveAction) {
          block.classList.add("dashboard-managed-actions-hidden");
        }
      });

      formState.set(form, {
        initial: serializeForm(form),
        dirty: false,
        pendingCheck: false,
        submitting: false,
      });

      form.addEventListener("input", () => queueFormDirtyStateCheck(form), true);
      form.addEventListener("change", () => queueFormDirtyStateCheck(form), true);
      form.addEventListener("click", () => queueFormDirtyStateCheck(form), true);
      form.addEventListener("dashboard:dirty-check", () => queueFormDirtyStateCheck(form), true);
      form.addEventListener("focusin", () => {
        if (formState.get(form)?.dirty) {
          activeForm = form;
          syncBarVisibility();
        }
      });
      form.addEventListener("submit", (event) => {
        const state = formState.get(form);
        if (!state) return;
        const submitter = event.submitter instanceof HTMLElement ? event.submitter : null;
        if (canSubmitFormInPlace(form, submitter)) {
          event.preventDefault();
          submitFormInPlace(form, submitter);
          return;
        }
        dirtyBar.hidden = true;
        document.body.classList.remove("dashboard-dirty-open");
        formState.set(form, {
          initial: serializeForm(form),
          dirty: false,
          pendingCheck: false,
          submitting: false,
        });
      });
    });

    document.addEventListener(
      "click",
      (event) => {
        if (event.defaultPrevented) return;
        if (event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

        const target = event.target;
        if (!(target instanceof Element)) return;
        const anchor = target.closest("a[href]");
        if (!(anchor instanceof HTMLAnchorElement)) return;
        if (anchor.hasAttribute("download")) return;
        if (anchor.dataset.allowDirtyNav === "1") return;
        const targetAttr = String(anchor.getAttribute("target") || "").trim();
        if (targetAttr && targetAttr !== "_self") return;

        const rawHref = String(anchor.getAttribute("href") || "").trim();
        if (!rawHref || rawHref.startsWith("javascript:")) return;

        let nextUrl = null;
        try {
          nextUrl = new URL(anchor.href, window.location.origin);
        } catch (_error) {
          return;
        }
        if (!(nextUrl instanceof URL)) return;

        const currentUrl = new URL(String(window.location.href || ""), window.location.origin);
        if (nextUrl.href === currentUrl.href) return;
        blockNavigationWithDirtyState(event);
      },
      true
    );

    const isTabSwitchTrigger = (element) => {
      if (!(element instanceof Element)) return false;
      const control = element.closest(
        [
          "[data-ownerbot-subtab-trigger]",
          "[data-ownerbot-section-tab]",
          "[data-tab-target]",
          "[role='tab']",
        ].join(", ")
      );
      if (!(control instanceof HTMLElement)) return false;
      if (control.dataset.allowDirtyNav === "1" || control.dataset.allowDirtyTabSwitch === "1") {
        return false;
      }
      if (control instanceof HTMLAnchorElement) return false;
      return true;
    };

    const onTabSwitchAttempt = (event) => {
      if (event.defaultPrevented) return;
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (!isTabSwitchTrigger(target)) return;
      blockNavigationWithDirtyState(event);
    };

    document.addEventListener("click", onTabSwitchAttempt, true);
    document.addEventListener(
      "keydown",
      (event) => {
        if (event.defaultPrevented) return;
        if (event.metaKey || event.ctrlKey || event.altKey) return;
        if (event.key !== "Enter" && event.key !== " ") return;
        onTabSwitchAttempt(event);
      },
      true
    );

    window.addEventListener("beforeunload", (event) => {
      if (isDirtyBeforeUnloadSuppressed()) return;
      const dirtyForm = resolveActiveDirtyForm();
      if (!dirtyForm) return;
      event.preventDefault();
      event.returnValue = "";
    });

    resetButton?.addEventListener("click", () => {
      if (!activeForm) return;
      const state = formState.get(activeForm);
      if (state?.submitting) return;
      activeForm.reset();
      if (typeof window.__initTagSearchFields === "function") {
        window.__initTagSearchFields(activeForm);
      }
      if (typeof window.__initDashboardSearchableSelects === "function") {
        window.__initDashboardSearchableSelects(activeForm);
      }
      queueFormDirtyStateCheck(activeForm);
      window.requestAnimationFrame(() => {
        const latestState = formState.get(activeForm);
        if (!latestState) return;
        latestState.dirty = false;
        latestState.pendingCheck = false;
        syncBarVisibility();
      });
    });

    saveButton?.addEventListener("click", () => {
      if (!activeForm) return;
      if (formState.get(activeForm)?.submitting) return;
      persistDashboardScrollPosition();
      if (typeof activeForm.requestSubmit === "function") {
        activeForm.requestSubmit();
      } else {
        activeForm.submit();
      }
    });

    syncBarVisibility();
  }

  initGlobalFetchFeedback();
  patchProgrammaticFormSubmitSuppression();
  initFormSubmissionFeedback();
  initNavigationFeedback();
  const armInitialPageBusy = () => {
    if (initialPageBusyToken || initialPageBusyDelayTimer) return;
    initialPageBusyDelayTimer = window.setTimeout(() => {
      initialPageBusyDelayTimer = 0;
      if (document.readyState === "interactive" || document.readyState === "complete") {
        return;
      }
      initialPageBusyToken = beginBusy("page", {
        title: feedbackText("loadingTitle"),
        subtitle: feedbackText("loadingSubtitle"),
        timeoutMs: 25000,
      });
    }, DASHBOARD_INITIAL_BUSY_DELAY_MS);
  };
  armInitialPageBusy();

  window.showToast = showToast;
  window.__dashboardFeedback = {
    notify: notifyOperation,
    beginBusy,
    endBusy,
    text: feedbackText,
    releaseBootLoader: releaseInitialPageLoader,
  };
  window.addTag = addTag;
  window.removeTag = removeTag;
  window.__initTagSearchFields = initTagSearchFields;
  window.__syncTagSearchForSelect = syncTagSearchForSelect;
  window.__initDashboardSearchableSelects = initDashboardSearchableSelects;
  window.__syncDashboardSearchableSelect = syncDashboardSearchableSelect;
  window.addEventListener("DOMContentLoaded", () => {
    releaseInitialPageLoader();
    initDashboardScrollPersistenceGuards();
    restoreDashboardScrollPosition();
    initProgressiveSectionReveal();
    initBackgroundNavigationPrefetch();
    initTagSearchFields();
    initDashboardSearchableSelects();
    initDashboardSearchableSelectObserver();
    bootstrapNotices();
    initDiscordLikeSaveBar();
    initDiscordRuntimeBanner();
  });
  window.addEventListener("dashboard:language-change", () => {
    initTagSearchFields();
    initDashboardSearchableSelects();
  });
  window.addEventListener("load", () => {
    releaseInitialPageLoader();
  });
})();
