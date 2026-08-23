(() => {
  const tabs = Array.from(document.querySelectorAll(".studio-tab[data-studio-tab]"));
  const panels = Array.from(document.querySelectorAll(".studio-panel[data-studio-panel]"));
  if (!tabs.length || !panels.length) return;

  const switchTab = (targetKey) => {
    const key = String(targetKey || "").trim().toLowerCase();
    let matched = false;

    tabs.forEach((tab) => {
      if (!(tab instanceof HTMLElement)) return;
      const tabKey = String(tab.getAttribute("data-studio-tab") || "").trim().toLowerCase();
      const active = tabKey === key;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
      if (active) matched = true;
    });

    panels.forEach((panel) => {
      if (!(panel instanceof HTMLElement)) return;
      const panelKey = String(panel.getAttribute("data-studio-panel") || "").trim().toLowerCase();
      const active = panelKey === key;
      panel.classList.toggle("is-active", active);
      panel.hidden = !active;
      panel.setAttribute("aria-hidden", active ? "false" : "true");
    });

    if (matched) {
      window.location.hash = key === "theme" ? "#theme-guildstyle" : "#roleplay";
    }
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      switchTab(tab.getAttribute("data-studio-tab"));
    });
  });

  const initialHash = String(window.location.hash || "").toLowerCase();
  if (initialHash.includes("theme")) {
    switchTab("theme");
  } else {
    switchTab("roleplay");
  }
})();
