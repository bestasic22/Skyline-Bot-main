(() => {{
  const GS_SECTION_COLLAPSE_STORAGE_PREFIX = "guildstyle.studio.section.collapsed.";

  const initGuildstyleSectionCollapse = () => {{
    const sections = Array.from(document.querySelectorAll(".page-guildstyle-studio .detail-page-section"));
    const sectionState = new Map();

    const getStoredCollapsed = (key) => {{
      try {{
        return window.localStorage.getItem(key) === "1";
      }} catch (_error) {{
        return false;
      }}
    }};
    const setStoredCollapsed = (key, collapsed) => {{
      try {{
        window.localStorage.setItem(key, collapsed ? "1" : "0");
      }} catch (_error) {{
        // ignore localStorage errors
      }}
    }};

    sections.forEach((section, index) => {{
      if (!(section instanceof HTMLElement)) return;
      if (section.getAttribute("data-gs-collapse-ready") === "1") return;
      const heading = section.querySelector("h2");
      if (!(heading instanceof HTMLElement)) return;

      const sectionKey = String(section.id || `section-${{index + 1}}`).trim();
      const storageKey = `${{GS_SECTION_COLLAPSE_STORAGE_PREFIX}}${{sectionKey}}`;

      const toggleButton = document.createElement("button");
      toggleButton.type = "button";
      toggleButton.className = "ghost-btn gs-section-toggle";
      toggleButton.setAttribute("aria-controls", sectionKey);
      toggleButton.setAttribute("aria-label", "Collapse section");
      toggleButton.title = "Collapse / Expand";

      heading.classList.add("gs-section-title");
      heading.appendChild(toggleButton);

      const bodyWrap = document.createElement("div");
      bodyWrap.className = "gs-section-body";

      let cursor = heading.nextSibling;
      while (cursor) {{
        const next = cursor.nextSibling;
        bodyWrap.appendChild(cursor);
        cursor = next;
      }}
      section.appendChild(bodyWrap);

      const setCollapsed = (collapsed) => {{
        const shouldCollapse = Boolean(collapsed);
        section.classList.toggle("is-collapsed", shouldCollapse);
        bodyWrap.hidden = shouldCollapse;
        toggleButton.textContent = shouldCollapse ? ">" : "v";
        toggleButton.setAttribute("aria-label", shouldCollapse ? "Expand section" : "Collapse section");
        toggleButton.setAttribute("aria-expanded", shouldCollapse ? "false" : "true");
        setStoredCollapsed(storageKey, shouldCollapse);
      }};

      toggleButton.addEventListener("click", () => {{
        const nextCollapsed = !section.classList.contains("is-collapsed");
        setCollapsed(nextCollapsed);
      }});

      sectionState.set(sectionKey, setCollapsed);
      section.setAttribute("data-gs-collapse-ready", "1");
      setCollapsed(getStoredCollapsed(storageKey));
    }});

    const expandTargetFromHash = () => {{
      const rawHash = String(window.location.hash || "").trim();
      if (!rawHash.startsWith("#")) return;
      const targetId = rawHash.slice(1);
      if (!targetId) return;
      const target = document.getElementById(targetId);
      if (!(target instanceof HTMLElement)) return;
      const setter = sectionState.get(targetId);
      if (typeof setter === "function") {{
        setter(false);
      }}
    }};

    window.addEventListener("hashchange", expandTargetFromHash);
    expandTargetFromHash();
  }};

  initGuildstyleSectionCollapse();

  const guildstyleCreateAction = document.querySelector('form input[name="action"][value="guildstyle_create_layout"]');
  const guildstyleCreateForm = guildstyleCreateAction && guildstyleCreateAction.form
    ? guildstyleCreateAction.form
    : null;
  const guildstyleThemeSelect = guildstyleCreateForm
    ? guildstyleCreateForm.querySelector('select[name="guildstyle_create_theme"]')
    : null;
  const guildstyleFontStyleSelect = guildstyleCreateForm
    ? guildstyleCreateForm.querySelector('select[name="guildstyle_create_font_style"]')
    : null;
  const guildstyleThemeEngineThemeHidden = document.getElementById("gsThemeEngineThemeHidden");
  const guildstyleThemeEngineFontStyleSelect = document.querySelector('select[name="guildstyle_font_style"]');
  const gsNameModeSelect = document.getElementById("gsNameModeSelect");
  const gsNameTemplateInput = document.getElementById("gsNameTemplateInput");
  const gsEngineCompareRows = Array.from(document.querySelectorAll(".gs-engine-compare-row"));
  const gsLiveThemeLabel = document.getElementById("gsLiveThemeLabel");
  const gsLiveFontLabel = document.getElementById("gsLiveFontLabel");
  const gsThemePreviewGrid = document.getElementById("gsThemePreviewGrid");
  const gsThemePreviewHint = document.getElementById("gsThemePreviewLiveHint");
  const gsThemeQuickButtons = Array.from(document.querySelectorAll(".gsThemeQuickButton"));
  const gsPreviewFontPills = Array.from(document.querySelectorAll(".gsPreviewFontPill"));
  const gsThemePreviewCards = gsThemePreviewGrid
    ? Array.from(gsThemePreviewGrid.querySelectorAll(".gs-preview-card[data-gs-theme-key][data-gs-font-style]"))
    : [];
  const allowedFontStyleSet = new Set();
  const optionCollectors = [];
  if (guildstyleFontStyleSelect instanceof HTMLSelectElement) optionCollectors.push(guildstyleFontStyleSelect);
  if (guildstyleThemeEngineFontStyleSelect instanceof HTMLSelectElement) optionCollectors.push(guildstyleThemeEngineFontStyleSelect);
  const attrStyles = String(gsThemePreviewGrid?.getAttribute("data-gs-font-style-options") || "")
    .split(",")
    .map((item) => String(item || "").trim().toLowerCase())
    .filter(Boolean);
  attrStyles.forEach((item) => allowedFontStyleSet.add(item));
  optionCollectors.forEach((selectEl) => {{
    Array.from(selectEl.options || []).forEach((opt) => {{
      const key = String(opt.value || "").trim().toLowerCase();
      if (key) allowedFontStyleSet.add(key);
    }});
  }});
  if (!allowedFontStyleSet.size) {{
    allowedFontStyleSet.add("bold");
  }}
  const fallbackFontStyle = allowedFontStyleSet.has("bold")
    ? "bold"
    : (Array.from(allowedFontStyleSet)[0] || "bold");

  const normalizeGuildstyleTheme = (value) => {{
    const key = String(value || "").trim().toLowerCase();
    if (key === "community" || key === "shop" || key === "gaming" || key === "roleplay") {{
      return key;
    }}
    return "roleplay";
  }};

  const normalizeGuildstyleFontStyle = (value) => {{
    const key = String(value || "").trim().toLowerCase();
    if (allowedFontStyleSet.has(key)) {{
      return key;
    }}
    return fallbackFontStyle;
  }};

  const normalizeEngineThemeKey = (value) => {{
    const key = String(value || "").trim().toLowerCase();
    if (key === "community" || key === "shop" || key === "gaming" || key === "roleplay") {{
      return key;
    }}
    return "__custom__";
  }};

  const renderTemplateName = (template, emojiValue, styledValue, fallbackValue) => {{
    const safeTemplate = String(template || "{{emoji}} {{name}}")
      .replaceAll("{{{{emoji}}}}", "{{emoji}}")
      .replaceAll("{{{{name}}}}", "{{name}}");
    const rendered = safeTemplate
      .replaceAll("{{emoji}}", String(emojiValue || ""))
      .replaceAll("{{name}}", String(styledValue || ""))
      .replace(/\s+/g, " ")
      .trim();
    return rendered || String(fallbackValue || "-");
  }};

  const readEnginePreviewMap = (row) => {{
    if (!(row instanceof HTMLElement)) return null;
    let previewMap = row._gsPreviewMap;
    if (previewMap && typeof previewMap === "object") {{
      return previewMap;
    }}
    const rawMap = String(row.getAttribute("data-gs-preview-map") || "").trim();
    if (!rawMap) return null;
    try {{
      previewMap = JSON.parse(rawMap);
      row._gsPreviewMap = previewMap;
      return previewMap;
    }} catch (_error) {{
      return null;
    }}
  }};

  const resolveEngineThemePack = (previewMap, themeKey) => {{
    if (!previewMap || typeof previewMap !== "object") return {{}};
    const currentThemePack = previewMap[themeKey];
    if (currentThemePack && typeof currentThemePack === "object") {{
      return currentThemePack;
    }}
    const customThemePack = previewMap.__custom__;
    if (customThemePack && typeof customThemePack === "object") {{
      return customThemePack;
    }}
    return {{}};
  }};

  const resolveEngineStylePack = (themePack, fontStyle) => {{
    if (!themePack || typeof themePack !== "object") return null;
    const currentStylePack = themePack[fontStyle];
    if (currentStylePack && typeof currentStylePack === "object") {{
      return currentStylePack;
    }}
    return Object.values(themePack).find((item) => item && typeof item === "object") || null;
  }};

  const buildEngineModePreviewValue = (modeKey, stylePack, templateValue) => {{
    const fancyValue = String(stylePack?.fancy || stylePack?.plain || "-");
    const plainValue = String(stylePack?.plain || fancyValue || "-");
    const styledValue = String(stylePack?.styled || "");
    const prettyValue = String(stylePack?.pretty || styledValue || "");
    const emojiValue = String(stylePack?.emoji || "");

    if (modeKey === "plain") {{
      return plainValue;
    }}
    if (modeKey === "styled") {{
      return styledValue || prettyValue || plainValue;
    }}
    if (modeKey === "emoji_bracket") {{
      return `[${{emojiValue}}] ${{styledValue || prettyValue}}`.trim();
    }}
    if (modeKey === "emoji_dash") {{
      return `${{emojiValue}} - ${{styledValue || prettyValue}}`.trim();
    }}
    if (modeKey === "emoji_dot") {{
      return `${{emojiValue}} . ${{styledValue || prettyValue}}`.trim();
    }}
    if (modeKey === "capsule") {{
      return `[${{styledValue || prettyValue}}]`.trim();
    }}
    if (modeKey === "template") {{
      return renderTemplateName(templateValue, emojiValue, styledValue || prettyValue, plainValue);
    }}
    return fancyValue;
  }};

  const refreshNameModePresetCards = (selectedFontStyle) => {{
    if (!(gsNameModeSelect instanceof HTMLSelectElement) || !gsNameModeSelect.options.length) return;
    const themeKey = normalizeEngineThemeKey(
      guildstyleThemeEngineThemeHidden instanceof HTMLInputElement
        ? guildstyleThemeEngineThemeHidden.value
        : ""
    );
    const fontStyle = normalizeGuildstyleFontStyle(
      selectedFontStyle
      || (guildstyleThemeEngineFontStyleSelect instanceof HTMLSelectElement
        ? guildstyleThemeEngineFontStyleSelect.value
        : fallbackFontStyle)
    );
    const templateValue = gsNameTemplateInput instanceof HTMLInputElement
      ? String(gsNameTemplateInput.value || "")
      : "{{emoji}} {{name}}";

    const sampleRow = gsEngineCompareRows.find((row) => row instanceof HTMLElement) || null;
    const samplePreviewMap = sampleRow ? readEnginePreviewMap(sampleRow) : null;
    const sampleThemePack = resolveEngineThemePack(samplePreviewMap, themeKey);
    const sampleStylePack = resolveEngineStylePack(sampleThemePack, fontStyle) || {{
      fancy: "💬 Information",
      plain: "💬 Information",
      styled: "Information",
      pretty: "Information",
      emoji: "💬",
    }};

    Array.from(gsNameModeSelect.options).forEach((option) => {{
      if (!(option instanceof HTMLOptionElement)) return;
      const baseLabel = String(option.getAttribute("data-base-label") || option.textContent || option.value || "").trim();
      if (!baseLabel) return;
      option.setAttribute("data-base-label", baseLabel);
      const modeKey = String(option.value || "").trim().toLowerCase();
      const previewValue = buildEngineModePreviewValue(modeKey, sampleStylePack, templateValue);
      const compactPreview = previewValue.length > 56
        ? `${{previewValue.slice(0, 56)}}...`
        : previewValue;
      option.textContent = `${{baseLabel}} | ${{compactPreview}}`;
      option.title = `${{baseLabel}} | ${{previewValue}}`;
    }});
  }};

  const refreshEngineComparisonPreview = (selectedFontStyle) => {{
    if (!gsEngineCompareRows.length) return;
    const themeKey = normalizeEngineThemeKey(
      guildstyleThemeEngineThemeHidden instanceof HTMLInputElement
        ? guildstyleThemeEngineThemeHidden.value
        : ""
    );
    const modeKey = String(
      gsNameModeSelect instanceof HTMLSelectElement
        ? gsNameModeSelect.value
        : "fancy"
    ).trim().toLowerCase();
    const templateValue = gsNameTemplateInput instanceof HTMLInputElement
      ? String(gsNameTemplateInput.value || "")
      : "{{emoji}} {{name}}";
    const fontStyle = normalizeGuildstyleFontStyle(
      selectedFontStyle
      || (guildstyleThemeEngineFontStyleSelect instanceof HTMLSelectElement
        ? guildstyleThemeEngineFontStyleSelect.value
        : fallbackFontStyle)
    );

    refreshNameModePresetCards(fontStyle);

    gsEngineCompareRows.forEach((row) => {{
      if (!(row instanceof HTMLElement)) return;
      const previewMap = readEnginePreviewMap(row);
      const themePack = resolveEngineThemePack(previewMap, themeKey);
      const stylePack = resolveEngineStylePack(themePack, fontStyle);
      if (!stylePack) return;
      const nextValue = buildEngineModePreviewValue(modeKey, stylePack, templateValue);
      const outputNode = row.querySelector(".gs-engine-after-value");
      if (outputNode) outputNode.textContent = nextValue;
    }});
  }};

  const syncThemeQuickButtons = (selectedTheme) => {{
    gsThemeQuickButtons.forEach((button) => {{
      if (!(button instanceof HTMLElement)) return;
      const buttonTheme = normalizeGuildstyleTheme(button.getAttribute("data-gs-theme-value"));
      const isActive = buttonTheme === selectedTheme;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    }});
  }};

  const syncFontPills = (selectedFontStyle) => {{
    gsPreviewFontPills.forEach((pill) => {{
      if (!(pill instanceof HTMLElement)) return;
      const pillStyle = normalizeGuildstyleFontStyle(pill.getAttribute("data-gs-font-style"));
      pill.classList.toggle("is-active", pillStyle === selectedFontStyle);
    }});
  }};

  const syncLiveSelectionLabels = (selectedTheme, selectedFontStyle) => {{
    if (gsLiveThemeLabel) gsLiveThemeLabel.textContent = selectedTheme;
    if (gsLiveFontLabel) gsLiveFontLabel.textContent = selectedFontStyle;
  }};

  const refreshGuildstyleThemePreview = () => {{
    const selectedTheme = normalizeGuildstyleTheme(
      guildstyleThemeSelect instanceof HTMLSelectElement
        ? guildstyleThemeSelect.value
        : (gsThemePreviewGrid?.getAttribute("data-gs-selected-theme") || "roleplay")
    );
    const selectedFontStyle = normalizeGuildstyleFontStyle(
      guildstyleFontStyleSelect instanceof HTMLSelectElement
        ? guildstyleFontStyleSelect.value
        : (gsThemePreviewGrid?.getAttribute("data-gs-selected-font-style") || "bold")
    );

    syncThemeQuickButtons(selectedTheme);
    syncFontPills(selectedFontStyle);
    syncLiveSelectionLabels(selectedTheme, selectedFontStyle);

    if (!gsThemePreviewCards.length) {{
      if (gsThemePreviewHint) {{
        gsThemePreviewHint.textContent = `Live preview: ${{selectedTheme}} theme, ${{selectedFontStyle}} font`;
      }}
      refreshEngineComparisonPreview(selectedFontStyle);
      return;
    }}

    gsThemePreviewCards.forEach((card) => {{
      const cardTheme = normalizeGuildstyleTheme(card.getAttribute("data-gs-theme-key"));
      const cardFontStyle = normalizeGuildstyleFontStyle(card.getAttribute("data-gs-font-style"));
      const shouldShow = cardTheme === selectedTheme && cardFontStyle === selectedFontStyle;
      card.hidden = !shouldShow;
      card.setAttribute("aria-hidden", shouldShow ? "false" : "true");
    }});

    gsThemePreviewGrid?.setAttribute("data-gs-selected-theme", selectedTheme);
    gsThemePreviewGrid?.setAttribute("data-gs-selected-font-style", selectedFontStyle);
    if (gsThemePreviewHint) {{
      gsThemePreviewHint.textContent = `Live preview: ${{selectedTheme}} theme, ${{selectedFontStyle}} font`;
    }}
    refreshEngineComparisonPreview(selectedFontStyle);
  }};

  gsThemeQuickButtons.forEach((button) => {{
    button.addEventListener("click", () => {{
      const nextTheme = normalizeGuildstyleTheme(button.getAttribute("data-gs-theme-value"));
      if (guildstyleThemeSelect instanceof HTMLSelectElement) {{
        guildstyleThemeSelect.value = nextTheme;
      }}
      refreshGuildstyleThemePreview();
    }});
  }});
  gsPreviewFontPills.forEach((pill) => {{
    pill.addEventListener("click", () => {{
      const nextStyle = normalizeGuildstyleFontStyle(pill.getAttribute("data-gs-font-style"));
      if (guildstyleFontStyleSelect instanceof HTMLSelectElement) {{
        guildstyleFontStyleSelect.value = nextStyle;
      }}
      if (guildstyleThemeEngineFontStyleSelect instanceof HTMLSelectElement) {{
        guildstyleThemeEngineFontStyleSelect.value = nextStyle;
      }}
      refreshGuildstyleThemePreview();
    }});
  }});

  if (guildstyleThemeSelect instanceof HTMLSelectElement) {{
    guildstyleThemeSelect.addEventListener("change", () => {{
      refreshGuildstyleThemePreview();
    }});
    guildstyleThemeSelect.addEventListener("input", () => {{
      refreshGuildstyleThemePreview();
    }});
  }}
  if (guildstyleFontStyleSelect instanceof HTMLSelectElement) {{
    guildstyleFontStyleSelect.addEventListener("change", () => {{
      if (guildstyleThemeEngineFontStyleSelect instanceof HTMLSelectElement) {{
        guildstyleThemeEngineFontStyleSelect.value = normalizeGuildstyleFontStyle(guildstyleFontStyleSelect.value);
      }}
      refreshGuildstyleThemePreview();
    }});
    guildstyleFontStyleSelect.addEventListener("input", () => {{
      if (guildstyleThemeEngineFontStyleSelect instanceof HTMLSelectElement) {{
        guildstyleThemeEngineFontStyleSelect.value = normalizeGuildstyleFontStyle(guildstyleFontStyleSelect.value);
      }}
      refreshGuildstyleThemePreview();
    }});
  }}
  if (guildstyleThemeEngineFontStyleSelect instanceof HTMLSelectElement) {{
    guildstyleThemeEngineFontStyleSelect.addEventListener("change", () => {{
      if (guildstyleFontStyleSelect instanceof HTMLSelectElement) {{
        guildstyleFontStyleSelect.value = normalizeGuildstyleFontStyle(guildstyleThemeEngineFontStyleSelect.value);
      }}
      refreshGuildstyleThemePreview();
    }});
    guildstyleThemeEngineFontStyleSelect.addEventListener("input", () => {{
      if (guildstyleFontStyleSelect instanceof HTMLSelectElement) {{
        guildstyleFontStyleSelect.value = normalizeGuildstyleFontStyle(guildstyleThemeEngineFontStyleSelect.value);
      }}
      refreshGuildstyleThemePreview();
    }});
  }}
  if (gsNameModeSelect instanceof HTMLSelectElement) {{
    gsNameModeSelect.addEventListener("change", () => {{
      refreshEngineComparisonPreview();
    }});
    gsNameModeSelect.addEventListener("input", () => {{
      refreshEngineComparisonPreview();
    }});
  }}
  if (gsNameTemplateInput instanceof HTMLInputElement) {{
    gsNameTemplateInput.addEventListener("input", () => {{
      refreshEngineComparisonPreview();
    }});
    gsNameTemplateInput.addEventListener("change", () => {{
      refreshEngineComparisonPreview();
    }});
  }}
  refreshGuildstyleThemePreview();

  const hasOptionValue = (selectEl, value) => {{
    if (!(selectEl instanceof HTMLSelectElement)) return false;
    const targetValue = String(value || "").trim();
    if (!targetValue) return false;
    return Array.from(selectEl.options).some((option) => String(option.value || "").trim() === targetValue);
  }};

  const setSelectValueAndDispatch = (selectEl, value, focus = false) => {{
    if (!(selectEl instanceof HTMLSelectElement)) return false;
    const nextValue = String(value || "").trim();
    if (!nextValue || !hasOptionValue(selectEl, nextValue)) return false;
    const changed = String(selectEl.value || "").trim() !== nextValue;
    selectEl.value = nextValue;
    if (changed) {{
      selectEl.dispatchEvent(new Event("input", {{ bubbles: true }}));
      selectEl.dispatchEvent(new Event("change", {{ bubbles: true }}));
    }}
    if (focus) {{
      selectEl.focus();
    }}
    return true;
  }};

  const clearSelectValueAndDispatch = (selectEl, focus = false) => {{
    if (!(selectEl instanceof HTMLSelectElement)) return false;
    const hadValue = String(selectEl.value || "").trim().length > 0;
    selectEl.value = "";
    if (hadValue) {{
      selectEl.dispatchEvent(new Event("input", {{ bubbles: true }}));
      selectEl.dispatchEvent(new Event("change", {{ bubbles: true }}));
    }}
    if (focus) {{
      selectEl.focus();
    }}
    return hadValue;
  }};

  const bindDndListQuickSelect = (listEl, getValueFromItem, applySelection, syncActiveState) => {{
    if (!(listEl instanceof HTMLElement)) return;
    const items = Array.from(listEl.querySelectorAll(".gs-dnd-item"));
    if (!items.length) return;
    items.forEach((item) => {{
      if (!(item instanceof HTMLElement)) return;
      item.tabIndex = 0;
      item.setAttribute("role", "button");
      item.setAttribute("aria-label", "Select this item");
      const applyFromItem = () => {{
        const nextValue = getValueFromItem(item);
        if (!nextValue) return;
        applySelection(nextValue);
        if (typeof syncActiveState === "function") {{
          syncActiveState();
        }}
      }};
      item.addEventListener("click", (event) => {{
        const target = event.target;
        if (target instanceof HTMLElement && target.closest("a, button, input, select, textarea")) return;
        applyFromItem();
      }});
      item.addEventListener("keydown", (event) => {{
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        applyFromItem();
      }});
    }});
  }};

  const gsRoleColorSelect = document.getElementById("gsRoleColorSelect");
  const gsRoleRenameSelect = document.getElementById("gsRoleRenameSelect");
  const gsRolePaletteRows = Array.from(document.querySelectorAll("#gsRolePaletteBody .gs-role-palette-row"));
  const gsRoleDndList = document.getElementById("gsRoleDndList");

  const selectedRoleIdFromForms = () => {{
    const colorValue = gsRoleColorSelect instanceof HTMLSelectElement ? String(gsRoleColorSelect.value || "").trim() : "";
    if (colorValue) return colorValue;
    const renameValue = gsRoleRenameSelect instanceof HTMLSelectElement ? String(gsRoleRenameSelect.value || "").trim() : "";
    return renameValue;
  }};

  const syncRoleSelectionUi = () => {{
    const selectedRoleId = selectedRoleIdFromForms();
    gsRolePaletteRows.forEach((row) => {{
      if (!(row instanceof HTMLElement)) return;
      const rowRoleId = String(row.getAttribute("data-role-id") || "").trim();
      row.classList.toggle("is-active", Boolean(selectedRoleId) && rowRoleId === selectedRoleId);
    }});
    if (gsRoleDndList instanceof HTMLElement) {{
      Array.from(gsRoleDndList.querySelectorAll(".gs-dnd-item")).forEach((item) => {{
        if (!(item instanceof HTMLElement)) return;
        const itemRoleId = String(item.getAttribute("data-role-id") || "").trim();
        item.classList.toggle("is-active", Boolean(selectedRoleId) && itemRoleId === selectedRoleId);
      }});
    }}
  }};

  const selectGuildstyleRoleById = (roleId, focus = false) => {{
    const nextRoleId = String(roleId || "").trim();
    if (!nextRoleId) return false;
    if (nextRoleId === selectedRoleIdFromForms()) {{
      let cleared = false;
      if (gsRoleColorSelect instanceof HTMLSelectElement) {{
        cleared = clearSelectValueAndDispatch(gsRoleColorSelect, focus) || cleared;
      }}
      if (gsRoleRenameSelect instanceof HTMLSelectElement) {{
        cleared = clearSelectValueAndDispatch(gsRoleRenameSelect, false) || cleared;
      }}
      syncRoleSelectionUi();
      return cleared;
    }}
    let applied = false;
    if (gsRoleColorSelect instanceof HTMLSelectElement) {{
      applied = setSelectValueAndDispatch(gsRoleColorSelect, nextRoleId, focus) || applied;
    }}
    if (gsRoleRenameSelect instanceof HTMLSelectElement) {{
      applied = setSelectValueAndDispatch(gsRoleRenameSelect, nextRoleId, false) || applied;
    }}
    syncRoleSelectionUi();
    return applied;
  }};

  if (gsRolePaletteRows.length) {{
    gsRolePaletteRows.forEach((row) => {{
      if (!(row instanceof HTMLElement)) return;
      row.tabIndex = 0;
      row.setAttribute("role", "button");
      row.setAttribute("aria-label", "Select this role");
      const applyRowSelection = () => {{
        const roleId = String(row.getAttribute("data-role-id") || "").trim();
        if (!roleId) return;
        selectGuildstyleRoleById(roleId, true);
      }};
      row.addEventListener("click", (event) => {{
        const target = event.target;
        if (target instanceof HTMLElement && target.closest("a, button, input, select, textarea")) return;
        applyRowSelection();
      }});
      row.addEventListener("keydown", (event) => {{
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        applyRowSelection();
      }});
    }});
  }}

  gsRoleColorSelect?.addEventListener("change", syncRoleSelectionUi);
  gsRoleColorSelect?.addEventListener("input", syncRoleSelectionUi);
  gsRoleRenameSelect?.addEventListener("change", syncRoleSelectionUi);
  gsRoleRenameSelect?.addEventListener("input", syncRoleSelectionUi);
  syncRoleSelectionUi();

  const roleColorFormAction = document.querySelector('form input[name="action"][value="guildstyle_set_role_color"]');
  if (roleColorFormAction && roleColorFormAction.form) {{
    const roleSelect = roleColorFormAction.form.querySelector('select[name="guildstyle_role_id"]');
    const colorInput = roleColorFormAction.form.querySelector('input[name="guildstyle_role_color"]');
    const liveColorDot = document.getElementById("gsRoleColorLiveDot");
    const liveColorName = document.getElementById("gsRoleColorLiveName");
    const liveColorHex = document.getElementById("gsRoleColorLiveHex");
    const syncRoleColorFromOption = () => {{
      if (!(roleSelect instanceof HTMLSelectElement) || !(colorInput instanceof HTMLInputElement)) return;
      const selectedOption = roleSelect.selectedOptions && roleSelect.selectedOptions.length > 0
        ? roleSelect.selectedOptions[0]
        : null;
      const colorFromRole = selectedOption ? String(selectedOption.getAttribute("data-role-color") || "").trim() : "";
      if (/^#[0-9a-fA-F]{{6}}$/.test(colorFromRole)) {{
        colorInput.value = colorFromRole;
      }}
      if (liveColorName) {{
        const roleNameFromData = selectedOption ? String(selectedOption.getAttribute("data-role-name") || "").trim() : "";
        liveColorName.textContent = roleNameFromData || (selectedOption ? String(selectedOption.textContent || "Selected role").trim() : "Select a role");
      }}
      const hexValue = String(colorInput.value || "#5865F2").trim().toUpperCase();
      if (liveColorHex) liveColorHex.textContent = hexValue;
      if (liveColorDot instanceof HTMLElement) {{
        liveColorDot.style.setProperty("--gs-color", hexValue);
      }}
    }};
    roleSelect?.addEventListener("change", syncRoleColorFromOption);
    colorInput?.addEventListener("input", syncRoleColorFromOption);
    syncRoleColorFromOption();

    roleColorFormAction.form.addEventListener("submit", (event) => {{
      const roleOk = roleSelect instanceof HTMLSelectElement && String(roleSelect.value || "").trim().length > 0;
      const colorOk = colorInput instanceof HTMLInputElement && /^#?[0-9a-fA-F]{{6}}$/.test(String(colorInput.value || "").trim());
      if (!roleOk || !colorOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Apply new color to selected role?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const roleRenameFormAction = document.querySelector('form input[name="action"][value="guildstyle_rename_role"]');
  if (roleRenameFormAction && roleRenameFormAction.form) {{
    const roleSelect = roleRenameFormAction.form.querySelector('select[name="guildstyle_role_id"]');
    const roleNameInput = roleRenameFormAction.form.querySelector('input[name="guildstyle_role_name"]');
    let hasManualEdit = false;

    const syncRoleNameFromOption = () => {{
      if (hasManualEdit) return;
      if (!(roleSelect instanceof HTMLSelectElement) || !(roleNameInput instanceof HTMLInputElement)) return;
      const selectedOption = roleSelect.selectedOptions && roleSelect.selectedOptions.length > 0
        ? roleSelect.selectedOptions[0]
        : null;
      const roleNameFromData = selectedOption ? String(selectedOption.getAttribute("data-role-name") || "").trim() : "";
      roleNameInput.value = roleNameFromData || (selectedOption ? String(selectedOption.textContent || "").trim() : "");
    }};

    roleSelect?.addEventListener("change", () => {{
      hasManualEdit = false;
      syncRoleNameFromOption();
    }});
    roleNameInput?.addEventListener("input", () => {{
      hasManualEdit = true;
    }});
    syncRoleNameFromOption();

    roleRenameFormAction.form.addEventListener("submit", (event) => {{
      const roleOk = roleSelect instanceof HTMLSelectElement && String(roleSelect.value || "").trim().length > 0;
      const roleName = roleNameInput instanceof HTMLInputElement ? String(roleNameInput.value || "").trim() : "";
      const nameOk = roleName.length > 0 && roleName.length <= 100;
      if (!roleOk || !nameOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm(`Rename selected role to "${{roleName}}"?`);
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const roleCreateFormAction = document.querySelector('form input[name="action"][value="guildstyle_create_role"]');
  if (roleCreateFormAction && roleCreateFormAction.form) {{
    const roleNameInput = roleCreateFormAction.form.querySelector('input[name="guildstyle_new_role_name"]');
    const colorInput = roleCreateFormAction.form.querySelector('input[name="guildstyle_new_role_color"]');

    roleCreateFormAction.form.addEventListener("submit", (event) => {{
      const roleName = roleNameInput instanceof HTMLInputElement ? String(roleNameInput.value || "").trim() : "";
      const roleNameOk = roleName.length > 0 && roleName.length <= 100;
      const colorValue = colorInput instanceof HTMLInputElement ? String(colorInput.value || "").trim() : "";
      const colorOk = colorValue.length === 0 || /^#?[0-9a-fA-F]{{6}}$/.test(colorValue);
      if (!roleNameOk || !colorOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm(`Create role "${{roleName}}" now?`);
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const themeEngineFormAction = document.querySelector('form input[name="action"][value="guildstyle_apply_theme_engine"]');
  if (themeEngineFormAction && themeEngineFormAction.form) {{
    const modeSelect = themeEngineFormAction.form.querySelector('select[name="guildstyle_name_mode"]');
    const templateInput = themeEngineFormAction.form.querySelector('input[name="guildstyle_name_template"]');

    const syncTemplateState = () => {{
      if (!(modeSelect instanceof HTMLSelectElement) || !(templateInput instanceof HTMLInputElement)) return;
      const isTemplateMode = String(modeSelect.value || "").trim().toLowerCase() === "template";
      templateInput.readOnly = !isTemplateMode;
      templateInput.setAttribute("aria-disabled", isTemplateMode ? "false" : "true");
      if (!isTemplateMode && !String(templateInput.value || "").trim()) {{
        templateInput.value = "{{emoji}} {{name}}";
      }}
    }};
    modeSelect?.addEventListener("change", syncTemplateState);
    syncTemplateState();

    themeEngineFormAction.form.addEventListener("submit", (event) => {{
      const selectedTargets = Array.from(
        themeEngineFormAction.form.querySelectorAll(
          'input[name="guildstyle_apply_categories"], input[name="guildstyle_apply_channels"], input[name="guildstyle_apply_roles"]'
        )
      ).filter((el) => el instanceof HTMLInputElement && el.checked);
      if (!selectedTargets.length) {{
        event.preventDefault();
        return;
      }}
      const templateValue = templateInput instanceof HTMLInputElement ? String(templateInput.value || "").trim() : "";
      const modeValue = modeSelect instanceof HTMLSelectElement ? String(modeSelect.value || "").trim().toLowerCase() : "fancy";
      if (modeValue === "template") {{
        const hasToken = (
          templateValue.includes("{{emoji}}")
          || templateValue.includes("{{name}}")
          || templateValue.includes("{{{{emoji}}}}")
          || templateValue.includes("{{{{name}}}}")
        );
        if (!hasToken) {{
          event.preventDefault();
          return;
        }}
      }}
      const ok = window.confirm("Apply selected GuildStyle theme to all selected targets now?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const categoryThemeFormAction = document.querySelector('form input[name="action"][value="guildstyle_set_category_theme"]');
  if (categoryThemeFormAction && categoryThemeFormAction.form) {{
    const categoryThemeForm = categoryThemeFormAction.form;
    const categorySelect = categoryThemeForm.querySelector('select[name="guildstyle_category_id"]');
    const categoryThemeSelect = categoryThemeForm.querySelector('select[name="guildstyle_category_theme"]');
    const mapRows = Array.from(document.querySelectorAll("#gsCategoryThemeMapBody .gs-category-map-row"));

    const syncActiveCategoryRow = () => {{
      if (!(categorySelect instanceof HTMLSelectElement)) return;
      const selectedCategoryId = String(categorySelect.value || "").trim();
      mapRows.forEach((row) => {{
        if (!(row instanceof HTMLElement)) return;
        const rowCatId = String(row.getAttribute("data-category-id") || "").trim();
        row.classList.toggle("is-active", Boolean(selectedCategoryId) && rowCatId === selectedCategoryId);
      }});
    }};

    if (categorySelect instanceof HTMLSelectElement && categoryThemeSelect instanceof HTMLSelectElement && mapRows.length) {{
      mapRows.forEach((row) => {{
        if (!(row instanceof HTMLElement)) return;
        row.tabIndex = 0;
        row.setAttribute("role", "button");
        row.setAttribute("aria-label", "Select this category");

        const applyRowSelection = () => {{
          const nextCategoryId = String(row.getAttribute("data-category-id") || "").trim();
          const mappedTheme = String(row.getAttribute("data-mapped-theme") || "inherit").trim().toLowerCase() || "inherit";
          if (nextCategoryId && hasOptionValue(categorySelect, nextCategoryId)) {{
            categorySelect.value = nextCategoryId;
          }}
          const nextTheme = hasOptionValue(categoryThemeSelect, mappedTheme) ? mappedTheme : "inherit";
          categoryThemeSelect.value = nextTheme;
          syncActiveCategoryRow();
          categorySelect.focus();
        }};

        row.addEventListener("click", (event) => {{
          const target = event.target;
          if (target instanceof HTMLElement && target.closest("a, button, input, select, textarea")) return;
          applyRowSelection();
        }});
        row.addEventListener("keydown", (event) => {{
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          applyRowSelection();
        }});
      }});

      categorySelect.addEventListener("change", syncActiveCategoryRow);
      categorySelect.addEventListener("input", syncActiveCategoryRow);
      syncActiveCategoryRow();
    }}

    categoryThemeFormAction.form.addEventListener("submit", (event) => {{
      const select = categoryThemeFormAction.form.querySelector('select[name="guildstyle_category_id"]');
      const okSelect = select instanceof HTMLSelectElement && String(select.value || "").trim().length > 0;
      if (!okSelect) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Save this category theme mapping?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const renameExclusionFormAction = document.querySelector('form input[name="action"][value="guildstyle_set_rename_excludes"]');
  if (renameExclusionFormAction && renameExclusionFormAction.form) {{
    const bindMultiToggleSelect = (selectEl) => {{
      if (!(selectEl instanceof HTMLSelectElement) || !selectEl.multiple) return;
      if (selectEl.getAttribute("data-gs-toggle-ready") === "1") return;

      const dispatchSelectionEvents = () => {{
        selectEl.dispatchEvent(new Event("input", {{ bubbles: true }}));
        selectEl.dispatchEvent(new Event("change", {{ bubbles: true }}));
      }};

      selectEl.addEventListener("mousedown", (event) => {{
        const target = event.target;
        const optionEl = target instanceof HTMLOptionElement
          ? target
          : (target instanceof HTMLElement ? target.closest("option") : null);
        if (!(optionEl instanceof HTMLOptionElement)) return;
        event.preventDefault();
        optionEl.selected = !optionEl.selected;
        dispatchSelectionEvents();
      }});

      selectEl.addEventListener("keydown", (event) => {{
        if (event.key !== " " && event.key !== "Enter") return;
        const active = selectEl.options[selectEl.selectedIndex];
        if (!(active instanceof HTMLOptionElement)) return;
        event.preventDefault();
        active.selected = !active.selected;
        dispatchSelectionEvents();
      }});

      selectEl.setAttribute("data-gs-toggle-ready", "1");
    }};

    const roleSelect = renameExclusionFormAction.form.querySelector('select[name="guildstyle_exclude_role_ids"]');
    const channelSelect = renameExclusionFormAction.form.querySelector('select[name="guildstyle_exclude_channel_ids"]');
    bindMultiToggleSelect(roleSelect);
    bindMultiToggleSelect(channelSelect);

    renameExclusionFormAction.form.addEventListener("submit", (event) => {{
      const selectedRoles = roleSelect instanceof HTMLSelectElement
        ? Array.from(roleSelect.selectedOptions).length
        : 0;
      const selectedChannels = channelSelect instanceof HTMLSelectElement
        ? Array.from(channelSelect.selectedOptions).length
        : 0;
      const ok = window.confirm(
        `Save rename exclusion list now?\\nRoles: ${{selectedRoles}}\\nRooms/Categories: ${{selectedChannels}}`
      );
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const categoryCreateFormAction = document.querySelector('form input[name="action"][value="guildstyle_create_category"]');
  if (categoryCreateFormAction && categoryCreateFormAction.form) {{
    categoryCreateFormAction.form.addEventListener("submit", (event) => {{
      const input = categoryCreateFormAction.form.querySelector('input[name="guildstyle_category_name"]');
      const value = input instanceof HTMLInputElement ? String(input.value || "").trim() : "";
      if (!value) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm(`Create category "${{value}}"?`);
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const collectVisibleDndIds = (listEl, selector = ".gs-dnd-item") => {{
    if (!(listEl instanceof HTMLElement)) return [];
    return Array.from(listEl.querySelectorAll(selector))
      .filter((item) => item instanceof HTMLElement && !item.hidden)
      .map((item) => String(item.getAttribute("data-dnd-id") || "").trim())
      .filter((id) => id.length > 0);
  }};

  const bindSimpleDndList = (listEl) => {{
    if (!(listEl instanceof HTMLElement)) return;
    let draggingItem = null;

    const getDndItem = (node) => (
      node instanceof HTMLElement ? node.closest(".gs-dnd-item") : null
    );

    listEl.querySelectorAll(".gs-dnd-item").forEach((item) => {{
      if (!(item instanceof HTMLElement)) return;
      item.addEventListener("dragstart", (event) => {{
        draggingItem = item;
        item.classList.add("is-dragging");
        if (event.dataTransfer) {{
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", item.getAttribute("data-dnd-id") || "drag");
        }}
      }});
      item.addEventListener("dragend", () => {{
        item.classList.remove("is-dragging");
        draggingItem = null;
      }});
    }});

    listEl.addEventListener("dragover", (event) => {{
      if (!draggingItem) return;
      const target = getDndItem(event.target);
      if (!target || target === draggingItem || target.hidden) return;
      event.preventDefault();
      const rect = target.getBoundingClientRect();
      const placeAfter = (event.clientY - rect.top) > rect.height / 2;
      if (placeAfter) {{
        listEl.insertBefore(draggingItem, target.nextElementSibling);
      }} else {{
        listEl.insertBefore(draggingItem, target);
      }}
    }});
  }};

  const categoryReorderFormAction = document.querySelector('form input[name="action"][value="guildstyle_reorder_category"]');
  if (categoryReorderFormAction && categoryReorderFormAction.form) {{
    const categoryList = categoryReorderFormAction.form.querySelector("#gsCategoryDndList");
    const orderInput = categoryReorderFormAction.form.querySelector('input[name="guildstyle_category_order_ids"]');
    const summary = categoryReorderFormAction.form.querySelector("#gsCategoryDndSummary");
    const categoryEditSelect = document.getElementById("gsCategoryEditSelect");
    const categoryDeleteSelect = document.getElementById("gsCategoryDeleteSelect");
    const categoryThemeSelect = document.getElementById("gsCategoryThemeSelect");

    bindSimpleDndList(categoryList);

    const syncActiveCategoryItem = () => {{
      if (!(categoryList instanceof HTMLElement)) return;
      const selectedCategoryId = (
        categoryEditSelect instanceof HTMLSelectElement
          ? String(categoryEditSelect.value || "").trim()
        : ""
      ) || (
        categoryDeleteSelect instanceof HTMLSelectElement
          ? String(categoryDeleteSelect.value || "").trim()
          : ""
      ) || (
        categoryThemeSelect instanceof HTMLSelectElement
          ? String(categoryThemeSelect.value || "").trim()
          : ""
      );
      Array.from(categoryList.querySelectorAll(".gs-dnd-item")).forEach((item) => {{
        if (!(item instanceof HTMLElement)) return;
        const itemCategoryId = String(
          item.getAttribute("data-category-id")
          || item.getAttribute("data-dnd-id")
          || ""
        ).trim();
        item.classList.toggle("is-active", Boolean(selectedCategoryId) && itemCategoryId === selectedCategoryId);
      }});
    }};

    const selectedCategoryIdFromForms = () => (
      (categoryEditSelect instanceof HTMLSelectElement ? String(categoryEditSelect.value || "").trim() : "")
      || (categoryDeleteSelect instanceof HTMLSelectElement ? String(categoryDeleteSelect.value || "").trim() : "")
      || (categoryThemeSelect instanceof HTMLSelectElement ? String(categoryThemeSelect.value || "").trim() : "")
    );

    const applyCategorySelection = (categoryId) => {{
      const nextCategoryId = String(categoryId || "").trim();
      if (!nextCategoryId) return;
      if (nextCategoryId === selectedCategoryIdFromForms()) {{
        clearSelectValueAndDispatch(categoryEditSelect, true);
        clearSelectValueAndDispatch(categoryDeleteSelect, false);
        clearSelectValueAndDispatch(categoryThemeSelect, false);
        syncActiveCategoryItem();
        return;
      }}
      setSelectValueAndDispatch(categoryEditSelect, nextCategoryId, true);
      setSelectValueAndDispatch(categoryDeleteSelect, nextCategoryId, false);
      setSelectValueAndDispatch(categoryThemeSelect, nextCategoryId, false);
      syncActiveCategoryItem();
    }};

    bindDndListQuickSelect(
      categoryList,
      (item) => String(item.getAttribute("data-category-id") || item.getAttribute("data-dnd-id") || "").trim(),
      applyCategorySelection,
      syncActiveCategoryItem
    );
    categoryEditSelect?.addEventListener("change", syncActiveCategoryItem);
    categoryDeleteSelect?.addEventListener("change", syncActiveCategoryItem);
    categoryThemeSelect?.addEventListener("change", syncActiveCategoryItem);

    const syncCategoryOrder = () => {{
      const orderedIds = collectVisibleDndIds(categoryList);
      if (orderInput instanceof HTMLInputElement) {{
        orderInput.value = orderedIds.join(",");
      }}
      if (summary instanceof HTMLElement) {{
        summary.textContent = orderedIds.length
          ? ("Ready to apply new order for " + String(orderedIds.length) + " categories.")
          : "No categories to reorder.";
      }}
    }};
    categoryList?.addEventListener("drop", syncCategoryOrder);
    categoryList?.addEventListener("dragend", syncCategoryOrder);
    syncCategoryOrder();
    syncActiveCategoryItem();

    categoryReorderFormAction.form.addEventListener("submit", (event) => {{
      syncCategoryOrder();
      const orderedIds = orderInput instanceof HTMLInputElement
        ? String(orderInput.value || "").split(",").map((v) => v.trim()).filter((v) => v.length > 0)
        : [];
      if (orderedIds.length < 2) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Apply drag-and-drop order for " + String(orderedIds.length) + " categories now?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const categoryEditFormAction = document.querySelector('form input[name="action"][value="guildstyle_edit_category"]');
  if (categoryEditFormAction && categoryEditFormAction.form) {{
    categoryEditFormAction.form.addEventListener("submit", (event) => {{
      const categorySelect = categoryEditFormAction.form.querySelector('select[name="guildstyle_category_id"]');
      const nameInput = categoryEditFormAction.form.querySelector('input[name="guildstyle_new_category_name"]');
      const categoryOk = categorySelect instanceof HTMLSelectElement && String(categorySelect.value || "").trim().length > 0;
      const nextName = nameInput instanceof HTMLInputElement ? String(nameInput.value || "").trim() : "";
      if (!categoryOk || !nextName) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm(`Rename selected category to "${{nextName}}"?`);
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const categoryDeleteFormAction = document.querySelector('form input[name="action"][value="guildstyle_delete_category"]');
  if (categoryDeleteFormAction && categoryDeleteFormAction.form) {{
    categoryDeleteFormAction.form.addEventListener("submit", (event) => {{
      const categorySelect = categoryDeleteFormAction.form.querySelector('select[name="guildstyle_category_id"]');
      const categoryOk = categorySelect instanceof HTMLSelectElement && String(categorySelect.value || "").trim().length > 0;
      if (!categoryOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Delete selected category now?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const channelCreateFormAction = document.querySelector('form input[name="action"][value="guildstyle_create_channel"]');
  if (channelCreateFormAction && channelCreateFormAction.form) {{
    channelCreateFormAction.form.addEventListener("submit", (event) => {{
      const input = channelCreateFormAction.form.querySelector('input[name="guildstyle_channel_name"]');
      const value = input instanceof HTMLInputElement ? String(input.value || "").trim() : "";
      if (!value) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm(`Create channel "${{value}}"?`);
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const channelEditFormAction = document.querySelector('form input[name="action"][value="guildstyle_edit_channel"]');
  if (channelEditFormAction && channelEditFormAction.form) {{
    const channelSelect = channelEditFormAction.form.querySelector('select[name="guildstyle_channel_id"]');
    const parentSelect = channelEditFormAction.form.querySelector('select[name="guildstyle_new_category_id"]');
    const syncEditParentSelect = () => {{
      if (!(channelSelect instanceof HTMLSelectElement) || !(parentSelect instanceof HTMLSelectElement)) return;
      const selectedOption = channelSelect.selectedOptions && channelSelect.selectedOptions.length > 0
        ? channelSelect.selectedOptions[0]
        : null;
      const categoryId = selectedOption ? String(selectedOption.getAttribute("data-category-id") || "").trim() : "";
      if (!categoryId) {{
        parentSelect.value = "__none__";
        return;
      }}
      const hasMatch = Array.from(parentSelect.options).some((option) => String(option.value || "").trim() === categoryId);
      parentSelect.value = hasMatch ? categoryId : "__keep__";
    }};
    channelSelect?.addEventListener("change", syncEditParentSelect);
    syncEditParentSelect();

    channelEditFormAction.form.addEventListener("submit", (event) => {{
      const channelOk = channelSelect instanceof HTMLSelectElement && String(channelSelect.value || "").trim().length > 0;
      if (!channelOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Update selected channel?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const channelReorderFormAction = document.querySelector('form input[name="action"][value="guildstyle_reorder_channel"]');
  if (channelReorderFormAction && channelReorderFormAction.form) {{
    const channelList = channelReorderFormAction.form.querySelector("#gsChannelDndList");
    const groupSelect = channelReorderFormAction.form.querySelector("#gsChannelDndGroupSelect");
    const groupInput = channelReorderFormAction.form.querySelector('input[name="guildstyle_channel_group"]');
    const orderInput = channelReorderFormAction.form.querySelector('input[name="guildstyle_channel_order_ids"]');
    const summary = channelReorderFormAction.form.querySelector("#gsChannelDndSummary");
    const channelManageSelect = document.getElementById("gsChannelManageSelect");
    const channelDeleteSelect = document.getElementById("gsChannelDeleteSelect");
    const visibilityChannelSelect = document.getElementById("gsVisibilityChannelSelect");
    bindSimpleDndList(channelList);

    const channelSelectTargets = [
      channelManageSelect,
      channelDeleteSelect,
      visibilityChannelSelect,
    ];

    const syncActiveChannelItem = () => {{
      if (!(channelList instanceof HTMLElement)) return;
      const selectedChannelId = (
        channelManageSelect instanceof HTMLSelectElement
          ? String(channelManageSelect.value || "").trim()
        : ""
      ) || (
        channelDeleteSelect instanceof HTMLSelectElement
          ? String(channelDeleteSelect.value || "").trim()
          : ""
      ) || (
        visibilityChannelSelect instanceof HTMLSelectElement
          ? String(visibilityChannelSelect.value || "").trim()
          : ""
      );
      Array.from(channelList.querySelectorAll(".gs-dnd-item")).forEach((item) => {{
        if (!(item instanceof HTMLElement)) return;
        const itemChannelId = String(
          item.getAttribute("data-channel-id")
          || item.getAttribute("data-dnd-id")
          || ""
        ).trim();
        item.classList.toggle("is-active", Boolean(selectedChannelId) && itemChannelId === selectedChannelId);
      }});
    }};

    const selectedChannelIdFromForms = () => (
      (channelManageSelect instanceof HTMLSelectElement ? String(channelManageSelect.value || "").trim() : "")
      || (channelDeleteSelect instanceof HTMLSelectElement ? String(channelDeleteSelect.value || "").trim() : "")
      || (visibilityChannelSelect instanceof HTMLSelectElement ? String(visibilityChannelSelect.value || "").trim() : "")
    );

    const filterChannelOptionsByGroup = (selectedGroup) => {{
      const groupKey = String(selectedGroup || "").trim();
      channelSelectTargets.forEach((selectEl) => {{
        if (!(selectEl instanceof HTMLSelectElement)) return;
        let hasVisibleSelected = false;
        Array.from(selectEl.options).forEach((optionEl) => {{
          const optionValue = String(optionEl.value || "").trim();
          if (!optionValue) {{
            optionEl.hidden = false;
            optionEl.disabled = false;
            return;
          }}
          const optionGroup = String(optionEl.getAttribute("data-channel-group") || "").trim();
          const visible = !groupKey || optionGroup === groupKey;
          optionEl.hidden = !visible;
          optionEl.disabled = !visible;
          if (visible && String(selectEl.value || "").trim() === optionValue) {{
            hasVisibleSelected = true;
          }}
        }});
        if (!hasVisibleSelected) {{
          const fallbackOption = Array.from(selectEl.options).find((optionEl) => (
            optionEl instanceof HTMLOptionElement
            && !optionEl.hidden
            && !optionEl.disabled
            && String(optionEl.value || "").trim().length > 0
          ));
          const fallbackValue = fallbackOption
            ? String(fallbackOption.value || "").trim()
            : "";
          if (fallbackValue) {{
            setSelectValueAndDispatch(selectEl, fallbackValue, false);
          }} else if (String(selectEl.value || "").trim()) {{
            selectEl.value = "";
            selectEl.dispatchEvent(new Event("input", {{ bubbles: true }}));
            selectEl.dispatchEvent(new Event("change", {{ bubbles: true }}));
          }}
        }}
      }});
      syncActiveChannelItem();
    }};

    const syncChannelVisibility = () => {{
      const selectedGroup = groupSelect instanceof HTMLSelectElement
        ? String(groupSelect.value || "").trim()
        : "";
      if (groupInput instanceof HTMLInputElement) {{
        groupInput.value = selectedGroup;
      }}
      if (!(channelList instanceof HTMLElement)) return;
      Array.from(channelList.querySelectorAll(".gs-dnd-item")).forEach((item) => {{
        if (!(item instanceof HTMLElement)) return;
        const itemGroup = String(item.getAttribute("data-channel-group") || "").trim();
        const visible = Boolean(selectedGroup) && itemGroup === selectedGroup;
        item.hidden = !visible;
      }});
      filterChannelOptionsByGroup(selectedGroup);
    }};

    const applyChannelSelection = (channelId, forceGroup = "") => {{
      const nextChannelId = String(channelId || "").trim();
      if (!nextChannelId) return;
      if (groupSelect instanceof HTMLSelectElement && forceGroup) {{
        setSelectValueAndDispatch(groupSelect, forceGroup, false);
      }}
      if (nextChannelId === selectedChannelIdFromForms()) {{
        clearSelectValueAndDispatch(channelManageSelect, true);
        clearSelectValueAndDispatch(channelDeleteSelect, false);
        clearSelectValueAndDispatch(visibilityChannelSelect, false);
        syncActiveChannelItem();
        return;
      }}
      syncChannelVisibility();
      setSelectValueAndDispatch(channelManageSelect, nextChannelId, true);
      setSelectValueAndDispatch(channelDeleteSelect, nextChannelId, false);
      setSelectValueAndDispatch(visibilityChannelSelect, nextChannelId, false);
      syncActiveChannelItem();
    }};

    const syncChannelOrder = () => {{
      syncChannelVisibility();
      const orderedIds = collectVisibleDndIds(channelList);
      if (orderInput instanceof HTMLInputElement) {{
        orderInput.value = orderedIds.join(",");
      }}
      if (summary instanceof HTMLElement) {{
        summary.textContent = orderedIds.length
          ? ("Ready to apply new order for " + String(orderedIds.length) + " channels in this group.")
          : "No channels in selected group.";
      }}
    }};

    bindDndListQuickSelect(
      channelList,
      (item) => String(item.getAttribute("data-channel-id") || item.getAttribute("data-dnd-id") || "").trim(),
      (channelId) => {{
        const forcedGroup = groupSelect instanceof HTMLSelectElement
          ? String(groupSelect.value || "").trim()
          : "";
        applyChannelSelection(channelId, forcedGroup);
      }},
      syncActiveChannelItem
    );

    channelManageSelect?.addEventListener("change", syncActiveChannelItem);
    channelDeleteSelect?.addEventListener("change", syncActiveChannelItem);
    visibilityChannelSelect?.addEventListener("change", syncActiveChannelItem);
    groupSelect?.addEventListener("change", syncChannelOrder);
    channelList?.addEventListener("drop", syncChannelOrder);
    channelList?.addEventListener("dragend", syncChannelOrder);
    syncChannelOrder();
    syncActiveChannelItem();

    channelReorderFormAction.form.addEventListener("submit", (event) => {{
      syncChannelOrder();
      const selectedGroup = groupInput instanceof HTMLInputElement ? String(groupInput.value || "").trim() : "";
      const orderedIds = orderInput instanceof HTMLInputElement
        ? String(orderInput.value || "").split(",").map((v) => v.trim()).filter((v) => v.length > 0)
        : [];
      if (!selectedGroup || orderedIds.length < 2) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Apply drag-and-drop order for " + String(orderedIds.length) + " channels now?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const roleReorderFormAction = document.querySelector('form input[name="action"][value="guildstyle_reorder_role"]');
  if (roleReorderFormAction && roleReorderFormAction.form) {{
    const roleList = roleReorderFormAction.form.querySelector("#gsRoleDndList");
    const orderInput = roleReorderFormAction.form.querySelector('input[name="guildstyle_role_order_ids"]');
    const summary = roleReorderFormAction.form.querySelector("#gsRoleDndSummary");
    bindSimpleDndList(roleList);

    bindDndListQuickSelect(
      roleList,
      (item) => String(item.getAttribute("data-role-id") || item.getAttribute("data-dnd-id") || "").trim(),
      (roleId) => {{
        selectGuildstyleRoleById(roleId, true);
      }},
      syncRoleSelectionUi
    );

    const syncRoleOrder = () => {{
      const orderedIds = collectVisibleDndIds(roleList);
      if (orderInput instanceof HTMLInputElement) {{
        orderInput.value = orderedIds.join(",");
      }}
      if (summary instanceof HTMLElement) {{
        summary.textContent = orderedIds.length
          ? ("Ready to apply new order for " + String(orderedIds.length) + " roles.")
          : "No roles to reorder.";
      }}
      syncRoleSelectionUi();
    }};
    roleList?.addEventListener("drop", syncRoleOrder);
    roleList?.addEventListener("dragend", syncRoleOrder);
    syncRoleOrder();

    roleReorderFormAction.form.addEventListener("submit", (event) => {{
      syncRoleOrder();
      const orderedIds = orderInput instanceof HTMLInputElement
        ? String(orderInput.value || "").split(",").map((v) => v.trim()).filter((v) => v.length > 0)
        : [];
      if (orderedIds.length < 2) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Apply drag-and-drop order for " + String(orderedIds.length) + " roles now?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const channelDeleteFormAction = document.querySelector('form input[name="action"][value="guildstyle_delete_channel"]');
  if (channelDeleteFormAction && channelDeleteFormAction.form) {{
    channelDeleteFormAction.form.addEventListener("submit", (event) => {{
      const channelSelect = channelDeleteFormAction.form.querySelector('select[name="guildstyle_channel_id"]');
      const channelOk = channelSelect instanceof HTMLSelectElement && String(channelSelect.value || "").trim().length > 0;
      if (!channelOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Delete selected channel now?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const visibilityCategoryFormAction = document.querySelector('form input[name="action"][value="guildstyle_visibility_category_simple"]');
  if (visibilityCategoryFormAction && visibilityCategoryFormAction.form) {{
    visibilityCategoryFormAction.form.addEventListener("submit", (event) => {{
      const roleSelect = visibilityCategoryFormAction.form.querySelector('select[name="guildstyle_role_id"]');
      const categorySelect = visibilityCategoryFormAction.form.querySelector('select[name="guildstyle_category_id"]');
      const roleOk = roleSelect instanceof HTMLSelectElement && String(roleSelect.value || "").trim().length > 0;
      const categoryOk = categorySelect instanceof HTMLSelectElement && String(categorySelect.value || "").trim().length > 0;
      if (!roleOk || !categoryOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Apply visibility for this role on selected category?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const visibilityChannelFormAction = document.querySelector('form input[name="action"][value="guildstyle_visibility_channel_simple"]');
  if (visibilityChannelFormAction && visibilityChannelFormAction.form) {{
    visibilityChannelFormAction.form.addEventListener("submit", (event) => {{
      const roleSelect = visibilityChannelFormAction.form.querySelector('select[name="guildstyle_role_id"]');
      const channelSelect = visibilityChannelFormAction.form.querySelector('select[name="guildstyle_channel_id"]');
      const roleOk = roleSelect instanceof HTMLSelectElement && String(roleSelect.value || "").trim().length > 0;
      const channelOk = channelSelect instanceof HTMLSelectElement && String(channelSelect.value || "").trim().length > 0;
      if (!roleOk || !channelOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Apply visibility for this role on selected channel?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const aclFormAction = document.querySelector('form input[name="action"][value="guildstyle_set_channel_acl"]');
  if (aclFormAction && aclFormAction.form) {{
    aclFormAction.form.addEventListener("submit", (event) => {{
      const roleSelect = aclFormAction.form.querySelector('select[name="guildstyle_role_id"]');
      const roomSelect = aclFormAction.form.querySelector('select[name="guildstyle_channel_id"]');
      const roleOk = roleSelect instanceof HTMLSelectElement && String(roleSelect.value || "").trim().length > 0;
      const roomOk = roomSelect instanceof HTMLSelectElement && String(roomSelect.value || "").trim().length > 0;
      if (!roleOk || !roomOk) {{
        event.preventDefault();
        return;
      }}
      const ok = window.confirm("Save room permission overwrite for selected role?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}

  const gsTable = document.getElementById("gsPermissionTable");
  const gsRows = gsTable ? Array.from(gsTable.querySelectorAll(".gs-acl-row")) : [];
  const gsRoleFilterWrap = document.getElementById("gsRoleFilterWrap");
  const gsRoleCheckboxes = gsRoleFilterWrap ? Array.from(gsRoleFilterWrap.querySelectorAll(".gsRoleFilterCheckbox")) : [];
  const gsFilterSummary = document.getElementById("gsRoleFilterSummary");
  const gsRoomSearchInput = document.getElementById("gsRoomSearchInput");
  const gsChannelTypeFilter = document.getElementById("gsChannelTypeFilter");
  const gsClearRoleFiltersButton = document.getElementById("gsClearRoleFiltersButton");

  const parseCsvSet = (raw) => {{
    const set = new Set();
    String(raw || "")
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .forEach((item) => set.add(item));
    return set;
  }};

  const intersects = (sourceSet, selectedSet) => {{
    for (const value of sourceSet) {{
      if (selectedSet.has(value)) return true;
    }}
    return false;
  }};

  const refreshGsRoleFilter = () => {{
    if (!gsRows.length) return;
    const selected = new Set(
      gsRoleCheckboxes
        .filter((input) => input instanceof HTMLInputElement && input.checked)
        .map((input) => String(input.value || "").trim())
        .filter((value) => value.length > 0)
    );
    const searchTerm = String(
      gsRoomSearchInput instanceof HTMLInputElement ? gsRoomSearchInput.value : ""
    ).trim().toLowerCase();
    const typeFilter = String(
      gsChannelTypeFilter instanceof HTMLSelectElement ? gsChannelTypeFilter.value : "all"
    ).trim().toLowerCase();

    let visibleRooms = 0;
    let sendRooms = 0;
    let connectRooms = 0;

    gsRows.forEach((row) => {{
      const viewSet = parseCsvSet(row.getAttribute("data-gs-view-role-ids"));
      const sendSet = parseCsvSet(row.getAttribute("data-gs-send-role-ids"));
      const connectSet = parseCsvSet(row.getAttribute("data-gs-connect-role-ids"));

      const matchesAny =
        selected.size === 0 ||
        intersects(viewSet, selected) ||
        intersects(sendSet, selected) ||
        intersects(connectSet, selected);
      const rowName = String(row.getAttribute("data-gs-channel-name") || "").toLowerCase();
      const rowCategory = String(row.getAttribute("data-gs-category-name") || "").toLowerCase();
      const rowType = String(row.getAttribute("data-gs-channel-type") || "").toLowerCase();
      const matchesSearch = !searchTerm || rowName.includes(searchTerm) || rowCategory.includes(searchTerm);
      const matchesType = typeFilter === "all" || rowType === typeFilter;
      const isVisible = matchesAny && matchesSearch && matchesType;

      row.hidden = !isVisible;
      if (isVisible) {{
        visibleRooms += 1;
        if (intersects(sendSet, selected) || selected.size === 0) sendRooms += 1;
        if (intersects(connectSet, selected) || selected.size === 0) connectRooms += 1;
      }}
    }});

    if (gsFilterSummary) {{
      if (selected.size === 0 && !searchTerm && typeFilter === "all") {{
        gsFilterSummary.textContent = `Showing all rooms (${{visibleRooms}}). Select roles to simulate combined access.`;
      }} else {{
        gsFilterSummary.textContent = `Selected roles: ${{selected.size}} | Visible rooms: ${{visibleRooms}} | Send: ${{sendRooms}} | Connect: ${{connectRooms}}`;
      }}
    }}
  }};

  gsRoleCheckboxes.forEach((input) => {{
    input.addEventListener("change", refreshGsRoleFilter);
  }});
  gsRoomSearchInput?.addEventListener("input", refreshGsRoleFilter);
  gsChannelTypeFilter?.addEventListener("change", refreshGsRoleFilter);
  gsClearRoleFiltersButton?.addEventListener("click", () => {{
    gsRoleCheckboxes.forEach((input) => {{
      if (input instanceof HTMLInputElement) input.checked = false;
    }});
    if (gsRoomSearchInput instanceof HTMLInputElement) {{
      gsRoomSearchInput.value = "";
    }}
    if (gsChannelTypeFilter instanceof HTMLSelectElement) {{
      gsChannelTypeFilter.value = "all";
    }}
    refreshGsRoleFilter();
  }});
  refreshGsRoleFilter();
}})();

