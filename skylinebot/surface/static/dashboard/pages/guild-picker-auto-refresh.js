(function () {
  const STORAGE_KEY = "skylinebot_invite_pending_sync";
  const PIN_STORAGE_KEY = "skylinebot_managed_guild_pins_v1";
  const RETURN_DELAY_MS = 1200;
  const STALE_MS = 15 * 60 * 1000;

  let reloadQueued = false;

  function parseState(raw) {
    if (!raw) return null;
    try {
      const parsed = JSON.parse(String(raw));
      if (!parsed || typeof parsed !== "object") return null;
      return parsed;
    } catch (_error) {
      return null;
    }
  }

  function readState() {
    return parseState(window.sessionStorage.getItem(STORAGE_KEY));
  }

  function writeState(state) {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state || {}));
    } catch (_error) {
      // Ignore storage write failures and keep normal invite behavior.
    }
  }

  function clearState() {
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch (_error) {
      // Ignore storage cleanup failures.
    }
  }

  function queueReload(delayMs) {
    if (reloadQueued) return;
    reloadQueued = true;
    window.setTimeout(function () {
      clearState();
      window.location.reload();
    }, Math.max(0, Number(delayMs) || 0));
  }

  function maybeRefreshAfterInvite() {
    const state = readState();
    if (!state) return;

    const openedAt = Number(state.openedAt || 0);
    if (!Number.isFinite(openedAt) || openedAt <= 0) {
      clearState();
      return;
    }

    const age = Date.now() - openedAt;
    if (age > STALE_MS) {
      clearState();
      return;
    }

    if (document.visibilityState !== "visible") return;

    if (age < RETURN_DELAY_MS) {
      queueReload((RETURN_DELAY_MS - age) + 100);
      return;
    }

    queueReload(80);
  }

  function onInviteClick(event) {
    const link = event.currentTarget;
    if (!(link instanceof HTMLElement)) return;

    const guildId = String(link.getAttribute("data-invite-guild-id") || "").trim();
    writeState({
      guildId: guildId,
      openedAt: Date.now(),
      sourcePath: window.location.pathname
    });

    link.dataset.invitePending = "1";
    link.classList.add("invite-sync-pending");
  }

  function bindInviteLinks() {
    const links = document.querySelectorAll("a[data-invite-guild-id]");
    links.forEach(function (node) {
      if (!(node instanceof HTMLElement)) return;
      if (node.dataset.inviteBound === "1") return;
      node.addEventListener("click", onInviteClick);
      node.dataset.inviteBound = "1";
    });
  }

  function parsePinnedIds(raw) {
    if (!raw) return [];
    try {
      const parsed = JSON.parse(String(raw));
      if (!Array.isArray(parsed)) return [];
      return parsed
        .map(function (item) {
          return String(item || "").trim();
        })
        .filter(function (guildId) {
          return guildId.length > 0;
        });
    } catch (_error) {
      return [];
    }
  }

  function readPinnedIds() {
    try {
      return parsePinnedIds(window.localStorage.getItem(PIN_STORAGE_KEY));
    } catch (_error) {
      return [];
    }
  }

  function writePinnedIds(pinnedIds) {
    const unique = Array.from(new Set(Array.isArray(pinnedIds) ? pinnedIds : []));
    try {
      window.localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify(unique));
    } catch (_error) {
      // Ignore write failures and keep normal UI behavior.
    }
  }

  function updatePinUi(card, pinned) {
    if (!(card instanceof HTMLElement)) return;
    const pinButton = card.querySelector("[data-guild-pin-toggle='1']");
    const pinBadge = card.querySelector("[data-guild-pin-badge]");
    card.classList.toggle("is-pinned", pinned);
    if (pinBadge instanceof HTMLElement) {
      pinBadge.hidden = !pinned;
    }
    if (!(pinButton instanceof HTMLButtonElement)) {
      return;
    }
    pinButton.classList.toggle("is-active", pinned);
    pinButton.setAttribute("aria-pressed", pinned ? "true" : "false");

    const icon = pinButton.querySelector("i");
    if (icon instanceof HTMLElement) {
      icon.className = pinned ? "fa-solid fa-bookmark" : "fa-regular fa-bookmark";
    }
    const label = pinButton.querySelector("span");
    if (label instanceof HTMLElement) {
      label.textContent = pinned ? "Pinned" : "Pin";
    }
  }

  function initManagedGuildPins() {
    const grid = document.querySelector("[data-managed-guild-grid='1']");
    if (!(grid instanceof HTMLElement)) return;

    const cards = Array.from(grid.querySelectorAll("[data-managed-guild-card='1'][data-guild-id]")).filter(function (node) {
      return node instanceof HTMLElement;
    });
    if (!cards.length) return;

    cards.forEach(function (card, index) {
      if (!(card instanceof HTMLElement)) return;
      card.dataset.guildSortIndex = String(index);
    });

    const managedGuildIds = new Set(
      cards.map(function (card) {
        return String(card.getAttribute("data-guild-id") || "").trim();
      }).filter(Boolean)
    );
    let pinnedIds = readPinnedIds().filter(function (guildId) {
      return managedGuildIds.has(guildId);
    });
    pinnedIds = Array.from(new Set(pinnedIds));
    writePinnedIds(pinnedIds);

    const sortCards = function () {
      const pinnedOrderMap = new Map();
      pinnedIds.forEach(function (guildId, index) {
        if (!pinnedOrderMap.has(guildId)) {
          pinnedOrderMap.set(guildId, index);
        }
      });

      cards.sort(function (aNode, bNode) {
        if (!(aNode instanceof HTMLElement) || !(bNode instanceof HTMLElement)) return 0;
        const aGuildId = String(aNode.getAttribute("data-guild-id") || "").trim();
        const bGuildId = String(bNode.getAttribute("data-guild-id") || "").trim();
        const aPinnedIndex = pinnedOrderMap.has(aGuildId) ? Number(pinnedOrderMap.get(aGuildId)) : -1;
        const bPinnedIndex = pinnedOrderMap.has(bGuildId) ? Number(pinnedOrderMap.get(bGuildId)) : -1;
        const aPinned = aPinnedIndex >= 0;
        const bPinned = bPinnedIndex >= 0;
        if (aPinned && bPinned) {
          return aPinnedIndex - bPinnedIndex;
        }
        if (aPinned !== bPinned) {
          return aPinned ? -1 : 1;
        }
        const aIndex = Number(aNode.dataset.guildSortIndex || 0);
        const bIndex = Number(bNode.dataset.guildSortIndex || 0);
        return aIndex - bIndex;
      });

      cards.forEach(function (card) {
        if (!(card instanceof HTMLElement)) return;
        const guildId = String(card.getAttribute("data-guild-id") || "").trim();
        updatePinUi(card, pinnedOrderMap.has(guildId));
        grid.appendChild(card);
      });
    };
    const togglePin = function (guildId) {
      const normalizedGuildId = String(guildId || "").trim();
      if (!normalizedGuildId) return;
      const currentIndex = pinnedIds.indexOf(normalizedGuildId);
      if (currentIndex >= 0) {
        pinnedIds.splice(currentIndex, 1);
      } else {
        pinnedIds.push(normalizedGuildId);
      }
      writePinnedIds(pinnedIds);
      sortCards();
    };

    if (grid.dataset.pinDelegated !== "1") {
      grid.addEventListener("click", function (event) {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const pinButton = target.closest("[data-guild-pin-toggle='1']");
        if (!(pinButton instanceof HTMLButtonElement)) return;
        if (!grid.contains(pinButton)) return;
        event.preventDefault();
        const guildId = String(pinButton.getAttribute("data-guild-id") || "").trim();
        togglePin(guildId);
      });
      grid.dataset.pinDelegated = "1";
    }

    sortCards();
  }

  initManagedGuildPins();
  bindInviteLinks();
  maybeRefreshAfterInvite();
  window.addEventListener("focus", maybeRefreshAfterInvite);
  document.addEventListener("visibilitychange", maybeRefreshAfterInvite);
})();
