(() => {
  const form = document.getElementById("reactionRolesForm");
  const list = document.getElementById("rrList");
  const input = document.getElementById("rrItemsJson");
  const addBtn = document.getElementById("rrAddBtn");
  const usageCounter = document.getElementById("rrUsageCounter");
  const rootSelectionMode = document.getElementById("rrRootSelectionMode");

  if (!form || !list || !input || !addBtn) return;
  if (form.dataset.rrBound === "1") return;
  form.dataset.rrBound = "1";

  const parseSeed = (id, fallback) => {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try {
      const parsed = JSON.parse(String(node.textContent || "").trim() || "null");
      return parsed ?? fallback;
    } catch (_error) {
      return fallback;
    }
  };

  const roleSeed = parseSeed("rrRoleOptionsSeed", []);
  const channelSeed = parseSeed("rrChannelOptionsSeed", []);
  const roleOptions = Array.isArray(roleSeed) ? roleSeed : [];
  const channelOptions = Array.isArray(channelSeed) ? channelSeed : [];

  const roleNameById = new Map();
  for (const role of roleOptions) {
    const id = String(role?.id || "");
    if (!id) continue;
    roleNameById.set(id, String(role?.name || role?.id || id));
  }

  const channelNameById = new Map();
  for (const channel of channelOptions) {
    const id = String(channel?.id || "");
    if (!id) continue;
    const type = String(channel?.type || "").toLowerCase();
    const prefix = type === "forum" ? "[forum]" : "#";
    channelNameById.set(id, `${prefix} ${String(channel?.name || channel?.id || id)}`);
  }

  const reactionRolesLimit = Math.max(
    1,
    Math.min(100, Number.parseInt(String(form.dataset.rrLimit || "10"), 10) || 10)
  );

  const notify = (message, type = "warn") => {
    if (typeof window.showToast === "function") {
      window.showToast(message, type);
      return;
    }
    if (type === "error") {
      window.alert(message);
    }
  };

  const uid = (prefix) =>
    `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2, 10)}`;

  const escapeHtml = (value) =>
    String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");

  const asText = (value, maxLength = 0) => {
    const text = String(value ?? "").trim();
    if (maxLength > 0) return text.slice(0, maxLength);
    return text;
  };

  const makeOption = () => ({
    id: uid("rr_opt"),
    emoji: "",
    role_id: "",
    label: "",
    description: "",
    active: true,
  });

  const normalizeOption = (raw) => {
    const row = raw && typeof raw === "object" ? raw : {};
    const roleId = asText(row.role_id, 32);
    return {
      id: asText(row.id, 64) || uid("rr_opt"),
      emoji: asText(row.emoji || "", 64),
      role_id: /^\d+$/.test(roleId) ? roleId : "",
      label: asText(row.label, 80),
      description: asText(row.description, 160),
      active: Boolean(row.active ?? true),
    };
  };

  const normalizeItem = (raw, fallbackSelectionMode = "single") => {
    const row = raw && typeof raw === "object" ? raw : {};
    const rowSelectionRaw = asText(row.selection_mode || fallbackSelectionMode, 16).toLowerCase();
    const rowSelectionMode = rowSelectionRaw === "multiple" ? "multiple" : "single";

    let options = [];
    if (Array.isArray(row.options)) {
      options = row.options.map(normalizeOption).filter((option) => option.role_id);
    } else {
      const legacy = normalizeOption({
        id: row.option_id || row.id,
        emoji: row.emoji,
        role_id: row.role_id,
        label: row.label || row.title,
        description: row.description,
        active: row.active,
      });
      if (legacy.role_id) options = [legacy];
    }

    const channelId = asText(row.channel_id, 32);
    const modeRaw = asText(row.mode || "toggle", 16).toLowerCase();
    const styleRaw = asText(row.style || "button", 16).toLowerCase();

    let maxSelect = Number.parseInt(String(row.max_select ?? ""), 10);
    if (!Number.isFinite(maxSelect)) {
      maxSelect = rowSelectionMode === "single" ? 1 : 2;
    }
    maxSelect = Math.max(1, Math.min(25, maxSelect));
    if (rowSelectionMode === "single") maxSelect = 1;

    return {
      id: asText(row.id, 64) || uid("rr_item"),
      title: asText(row.title || "Reaction Role", 80) || "Reaction Role",
      description: asText(row.description, 400),
      channel_id: /^\d+$/.test(channelId) ? channelId : "",
      style: styleRaw === "select" ? "select" : "button",
      mode: modeRaw === "give" || modeRaw === "remove" ? modeRaw : "toggle",
      selection_mode: rowSelectionMode,
      max_select: maxSelect,
      options,
      active: Boolean(row.active ?? true),
    };
  };

  const countTotalOptions = (rows) =>
    rows.reduce((sum, row) => sum + (Array.isArray(row.options) ? row.options.length : 0), 0);

  const selectHtml = (items, selectedValue, placeholder, formatter) => {
    const selected = String(selectedValue || "");
    const options = [`<option value="">${escapeHtml(placeholder)}</option>`];
    let foundSelected = selected === "";
    for (const item of items) {
      const value = String(item?.id || "");
      if (!value) continue;
      const isSelected = value === selected;
      if (isSelected) foundSelected = true;
      options.push(
        `<option value="${escapeHtml(value)}"${isSelected ? " selected" : ""}>${escapeHtml(
          formatter(item)
        )}</option>`
      );
    }
    if (!foundSelected && selected) {
      options.push(
        `<option value="${escapeHtml(selected)}" selected>Missing (${escapeHtml(selected)})</option>`
      );
    }
    return options.join("");
  };

  const buildRoleSelect = (selectedValue) =>
    selectHtml(roleOptions, selectedValue, "Select role...", (role) => `@ ${role?.name || role?.id || "-"}`);

  const buildChannelSelect = (selectedValue) =>
    selectHtml(channelOptions, selectedValue, "Select channel...", (channel) => {
      const type = String(channel?.type || "").toLowerCase();
      const prefix = type === "forum" ? "[forum]" : "#";
      return `${prefix} ${channel?.name || channel?.id || "-"}`;
    });

  const rootSelectionValue = () =>
    String(rootSelectionMode?.value || "single").trim().toLowerCase() === "multiple"
      ? "multiple"
      : "single";

  const makeItem = () => {
    const selectionMode = rootSelectionValue();
    return {
      id: uid("rr_item"),
      title: "Reaction Role",
      description: "",
      channel_id: "",
      style: "button",
      mode: "toggle",
      selection_mode: selectionMode,
      max_select: selectionMode === "single" ? 1 : 2,
      options: [makeOption()],
      active: true,
    };
  };

  const rowKey = (row, rowIndex) => String(row?.id || `row_${rowIndex}`);
  const optionKey = (row, rowIndex, option, optionIndex) =>
    `${rowKey(row, rowIndex)}:${String(option?.id || `opt_${optionIndex}`)}`;

  const collapsedRows = new Set();
  const collapsedMappings = new Set();

  let rows = [];
  try {
    const parsed = JSON.parse(String(input.value || "[]"));
    if (Array.isArray(parsed)) {
      rows = parsed.map((row) => normalizeItem(row, rootSelectionValue()));
    }
  } catch (_error) {
    rows = [];
  }

  const sync = () => {
    input.value = JSON.stringify(rows);
  };

  const refreshUsage = () => {
    const used = countTotalOptions(rows);
    if (usageCounter) {
      usageCounter.textContent = `${used}/${reactionRolesLimit}`;
      usageCounter.style.color = used >= reactionRolesLimit ? "#fecaca" : "";
    }
    addBtn.disabled = used >= reactionRolesLimit;
  };

  const clampRowMaxSelect = (row) => {
    if (!row || typeof row !== "object") return;
    const optionsLength = Array.isArray(row.options) ? row.options.length : 0;
    if (row.selection_mode !== "multiple") {
      row.selection_mode = "single";
      row.max_select = 1;
      return;
    }
    let value = Number.parseInt(String(row.max_select || "1"), 10);
    if (!Number.isFinite(value)) value = 1;
    row.max_select = Math.max(1, Math.min(25, Math.max(1, optionsLength), value));
  };

  const getRoleName = (roleId) => {
    const id = String(roleId || "").trim();
    if (!id) return "No role";
    return roleNameById.get(id) || `Role ${id}`;
  };

  const getChannelName = (channelId) => {
    const id = String(channelId || "").trim();
    if (!id) return "No channel";
    return channelNameById.get(id) || `Channel ${id}`;
  };

  const ensureToolbarTools = () => {
    const toolbar = form.querySelector(".rr-toolbar");
    if (!toolbar || toolbar.querySelector(".rr-toolbar-tools")) return;
    const tools = document.createElement("div");
    tools.className = "rr-toolbar-tools";
    tools.innerHTML = `
      <button type="button" class="ghost-btn" data-action="apply-first-channel">Apply first channel to all</button>
      <button type="button" class="ghost-btn" data-action="expand-all">Expand all</button>
      <button type="button" class="ghost-btn" data-action="collapse-all">Collapse all</button>
    `;
    toolbar.appendChild(tools);
  };

  const render = () => {
    ensureToolbarTools();
    list.innerHTML = rows
      .map((row, rowIndex) => {
        const options = Array.isArray(row.options) ? row.options : [];
        const usagePill = `<span class="rr-pill-counter">${options.length} role${
          options.length === 1 ? "" : "s"
        }</span>`;
        const maxSelectDisabled = row.selection_mode !== "multiple";
        const thisRowKey = rowKey(row, rowIndex);
        const isRowCollapsed = collapsedRows.has(thisRowKey);
        const rowTitle = asText(row.title || `Item ${rowIndex + 1}`, 80) || `Item ${rowIndex + 1}`;

        return `
          <article class="rr-item">
            <div class="rr-item-head">
              <div class="rr-item-head-main">
                <div class="rr-item-title">Item ${rowIndex + 1}: ${escapeHtml(rowTitle)}</div>
                <div class="rr-item-meta">${escapeHtml(getChannelName(row.channel_id))}</div>
                ${usagePill}
              </div>
              <div class="rr-item-actions">
                <button type="button" class="ghost-btn rr-icon-btn" data-action="toggle-row" data-row="${rowIndex}" title="${
          isRowCollapsed ? "Expand" : "Collapse"
        }" aria-label="${isRowCollapsed ? "Expand" : "Collapse"}">
                  <i class="bi ${isRowCollapsed ? "bi-chevron-down" : "bi-chevron-up"}" aria-hidden="true"></i>
                </button>
                <button type="button" class="ghost-btn rr-icon-btn" data-action="duplicate-row" data-row="${rowIndex}" title="Duplicate" aria-label="Duplicate">
                  <i class="bi bi-copy" aria-hidden="true"></i>
                </button>
                <button type="button" class="ghost-btn rr-icon-btn rr-icon-btn-danger" data-action="remove-row" data-row="${rowIndex}" title="Delete" aria-label="Delete">
                  <i class="bi bi-trash" aria-hidden="true"></i>
                </button>
              </div>
            </div>

            <div class="rr-item-body ${isRowCollapsed ? "is-collapsed" : ""}">
              <div class="rr-item-row">
                <div class="field-item">
                  <label>Title</label>
                  <input type="text" maxlength="80" data-row-field="title" data-row="${rowIndex}" value="${escapeHtml(
          row.title
        )}">
                </div>
                <div class="field-item">
                  <label>Channel</label>
                  <select data-row-field="channel_id" data-row="${rowIndex}">
                    ${buildChannelSelect(row.channel_id)}
                  </select>
                </div>
              </div>

              <div class="rr-item-row three">
                <div class="field-item">
                  <label>Style</label>
                  <select data-row-field="style" data-row="${rowIndex}">
                    <option value="button"${row.style === "button" ? " selected" : ""}>Button</option>
                    <option value="select"${row.style === "select" ? " selected" : ""}>Dropdown</option>
                  </select>
                </div>
                <div class="field-item">
                  <label>Mode</label>
                  <select data-row-field="mode" data-row="${rowIndex}">
                    <option value="toggle"${row.mode === "toggle" ? " selected" : ""}>Toggle</option>
                    <option value="give"${row.mode === "give" ? " selected" : ""}>Give only</option>
                    <option value="remove"${row.mode === "remove" ? " selected" : ""}>Remove only</option>
                  </select>
                </div>
                <div class="field-item">
                  <label>Selection Mode</label>
                  <select data-row-field="selection_mode" data-row="${rowIndex}">
                    <option value="single"${row.selection_mode !== "multiple" ? " selected" : ""}>Single role</option>
                    <option value="multiple"${row.selection_mode === "multiple" ? " selected" : ""}>Multiple roles</option>
                  </select>
                </div>
              </div>

              <div class="rr-item-row three">
                <div class="field-item">
                  <label>Max Select</label>
                  <input
                    type="number"
                    min="1"
                    max="25"
                    data-row-field="max_select"
                    data-row="${rowIndex}"
                    value="${Number(row.max_select || 1)}"
                    ${maxSelectDisabled ? "disabled" : ""}
                  >
                </div>
                <div class="field-item">
                  <label>Active</label>
                  <label class="ux-toggle">
                    <span class="ux-toggle-label">Enable this item</span>
                    <input type="checkbox" data-row-field="active" data-row="${rowIndex}" ${
          row.active ? "checked" : ""
        }>
                    <span class="ux-switch"></span>
                  </label>
                </div>
                <div class="field-item">
                  <label>Item ID</label>
                  <input type="text" value="${escapeHtml(row.id)}" readonly>
                </div>
              </div>

              <div class="field-item">
                <label>Description</label>
                <textarea data-row-field="description" data-row="${rowIndex}" style="min-height:72px;">${escapeHtml(
          row.description
        )}</textarea>
              </div>

              <div class="rr-option-wrap">
                <div class="rr-option-toolbar">
                  <strong>Emoji -> Role mappings</strong>
                  <button type="button" class="ghost-btn" data-action="add-option" data-row="${rowIndex}">+ Add mapping</button>
                </div>
                <div class="rr-option-list">
                  ${
                    options.length
                      ? options
                          .map((option, optionIndex) => {
                            const thisOptionKey = optionKey(row, rowIndex, option, optionIndex);
                            const isOptionCollapsed = collapsedMappings.has(thisOptionKey);
                            const optionEmoji = asText(option.emoji || "", 64);
                            const optionSummary = optionEmoji
                              ? `${optionEmoji} ${getRoleName(option.role_id)}`
                              : getRoleName(option.role_id);

                            return `
                              <div class="rr-option-row">
                                <div class="rr-option-head">
                                  <span class="rr-option-title">Mapping ${optionIndex + 1}: ${escapeHtml(optionSummary)}</span>
                                  <div class="rr-option-actions">
                                    <button type="button" class="ghost-btn rr-icon-btn" data-action="toggle-option" data-row="${rowIndex}" data-opt="${optionIndex}" title="${
                              isOptionCollapsed ? "Expand" : "Collapse"
                            }" aria-label="${isOptionCollapsed ? "Expand" : "Collapse"}">
                                      <i class="bi ${isOptionCollapsed ? "bi-chevron-down" : "bi-chevron-up"}" aria-hidden="true"></i>
                                    </button>
                                    <button type="button" class="ghost-btn rr-icon-btn rr-icon-btn-danger" data-action="remove-option" data-row="${rowIndex}" data-opt="${optionIndex}" title="Remove" aria-label="Remove">
                                      <i class="bi bi-trash" aria-hidden="true"></i>
                                    </button>
                                  </div>
                                </div>
                                <div class="rr-option-body ${isOptionCollapsed ? "is-collapsed" : ""}">
                                  <div class="rr-item-row three">
                                    <div class="field-item">
                                      <label>Emoji</label>
                                      <input type="text" maxlength="64" data-opt-field="emoji" data-row="${rowIndex}" data-opt="${optionIndex}" value="${escapeHtml(
                              option.emoji
                            )}">
                                    </div>
                                    <div class="field-item">
                                      <label>Role</label>
                                      <select data-opt-field="role_id" data-row="${rowIndex}" data-opt="${optionIndex}">
                                        ${buildRoleSelect(option.role_id)}
                                      </select>
                                    </div>
                                    <div class="field-item">
                                      <label>Enable</label>
                                      <label class="ux-toggle">
                                        <span class="ux-toggle-label">Active</span>
                                        <input type="checkbox" data-opt-field="active" data-row="${rowIndex}" data-opt="${optionIndex}" ${
                              option.active ? "checked" : ""
                            }>
                                        <span class="ux-switch"></span>
                                      </label>
                                    </div>
                                  </div>
                                  <div class="rr-item-row">
                                    <div class="field-item">
                                      <label>Label (for dropdown)</label>
                                      <input type="text" maxlength="80" data-opt-field="label" data-row="${rowIndex}" data-opt="${optionIndex}" value="${escapeHtml(
                              option.label
                            )}">
                                    </div>
                                    <div class="field-item">
                                      <label>Description (optional)</label>
                                      <input type="text" maxlength="160" data-opt-field="description" data-row="${rowIndex}" data-opt="${optionIndex}" value="${escapeHtml(
                              option.description
                            )}">
                                    </div>
                                  </div>
                                </div>
                              </div>
                            `;
                          })
                          .join("")
                      : `<p class="rr-hint">No mappings yet. Add at least one emoji-role mapping.</p>`
                  }
                </div>
              </div>
            </div>
          </article>
        `;
      })
      .join("");

    refreshUsage();
  };

  const cleanCollapseForDeletedRows = () => {
    const existingRowKeys = new Set(rows.map((row, rowIndex) => rowKey(row, rowIndex)));
    for (const key of Array.from(collapsedRows)) {
      if (!existingRowKeys.has(key)) {
        collapsedRows.delete(key);
      }
    }

    const existingOptionKeys = new Set();
    rows.forEach((row, rowIndex) => {
      const options = Array.isArray(row.options) ? row.options : [];
      options.forEach((option, optionIndex) => {
        existingOptionKeys.add(optionKey(row, rowIndex, option, optionIndex));
      });
    });
    for (const key of Array.from(collapsedMappings)) {
      if (!existingOptionKeys.has(key)) {
        collapsedMappings.delete(key);
      }
    }
  };

  addBtn.addEventListener("click", () => {
    const currentUsage = countTotalOptions(rows);
    if (currentUsage >= reactionRolesLimit) {
      notify(`Your plan limit is ${reactionRolesLimit} role mappings.`, "error");
      return;
    }
    rows.push(makeItem());
    sync();
    render();
  });

  form.addEventListener("click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    const button = target?.closest("button[data-action]");
    if (!button) return;

    const action = String(button.dataset.action || "");
    if (action === "expand-all") {
      collapsedRows.clear();
      collapsedMappings.clear();
      render();
      return;
    }

    if (action === "collapse-all") {
      collapsedRows.clear();
      collapsedMappings.clear();
      rows.forEach((row, rowIndex) => {
        collapsedRows.add(rowKey(row, rowIndex));
        const options = Array.isArray(row.options) ? row.options : [];
        options.forEach((option, optionIndex) => {
          collapsedMappings.add(optionKey(row, rowIndex, option, optionIndex));
        });
      });
      render();
      return;
    }

    if (action === "apply-first-channel") {
      if (!rows.length) {
        notify("Add at least one item first.", "error");
        return;
      }
      const channelId = String(rows[0]?.channel_id || "").trim();
      if (!channelId) {
        notify("Please select channel on Item 1 first.", "error");
        return;
      }
      rows = rows.map((row) => ({ ...row, channel_id: channelId }));
      sync();
      render();
      notify("Applied Item 1 channel to all items.", "success");
    }
  });

  list.addEventListener("click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    const button = target?.closest("button[data-action]");
    if (!button) return;

    const action = String(button.dataset.action || "");
    const rowIndex = Number.parseInt(String(button.dataset.row || "-1"), 10);
    const optionIndex = Number.parseInt(String(button.dataset.opt || "-1"), 10);

    if (action === "toggle-row") {
      if (!Number.isFinite(rowIndex) || rowIndex < 0 || rowIndex >= rows.length) return;
      const key = rowKey(rows[rowIndex], rowIndex);
      if (collapsedRows.has(key)) {
        collapsedRows.delete(key);
      } else {
        collapsedRows.add(key);
      }
      render();
      return;
    }

    if (action === "duplicate-row") {
      if (!Number.isFinite(rowIndex) || rowIndex < 0 || rowIndex >= rows.length) return;
      const source = rows[rowIndex];
      const sourceOptionsCount = Array.isArray(source.options) ? source.options.length : 0;
      const usage = countTotalOptions(rows);
      if (usage + sourceOptionsCount > reactionRolesLimit) {
        notify(`Cannot duplicate: plan limit is ${reactionRolesLimit} role mappings.`, "error");
        return;
      }
      const cloned = normalizeItem(
        {
          ...source,
          id: uid("rr_item"),
          options: (source.options || []).map((option) => ({
            ...option,
            id: uid("rr_opt"),
          })),
        },
        rootSelectionValue()
      );
      rows.splice(rowIndex + 1, 0, cloned);
      sync();
      render();
      return;
    }

    if (action === "remove-row") {
      if (Number.isFinite(rowIndex) && rowIndex >= 0 && rowIndex < rows.length) {
        rows.splice(rowIndex, 1);
        cleanCollapseForDeletedRows();
        sync();
        render();
      }
      return;
    }

    if (action === "add-option") {
      if (!Number.isFinite(rowIndex) || rowIndex < 0 || rowIndex >= rows.length) return;
      const usage = countTotalOptions(rows);
      if (usage >= reactionRolesLimit) {
        notify(`Your plan limit is ${reactionRolesLimit} role mappings.`, "error");
        return;
      }
      if (!Array.isArray(rows[rowIndex].options)) rows[rowIndex].options = [];
      rows[rowIndex].options.push(makeOption());
      clampRowMaxSelect(rows[rowIndex]);
      sync();
      render();
      return;
    }

    if (action === "toggle-option") {
      if (
        !Number.isFinite(rowIndex) ||
        rowIndex < 0 ||
        rowIndex >= rows.length ||
        !Number.isFinite(optionIndex) ||
        optionIndex < 0
      ) {
        return;
      }
      const options = Array.isArray(rows[rowIndex].options) ? rows[rowIndex].options : [];
      if (optionIndex >= options.length) return;
      const key = optionKey(rows[rowIndex], rowIndex, options[optionIndex], optionIndex);
      if (collapsedMappings.has(key)) {
        collapsedMappings.delete(key);
      } else {
        collapsedMappings.add(key);
      }
      render();
      return;
    }

    if (action === "remove-option") {
      if (
        !Number.isFinite(rowIndex) ||
        rowIndex < 0 ||
        rowIndex >= rows.length ||
        !Number.isFinite(optionIndex) ||
        optionIndex < 0
      ) {
        return;
      }
      const options = Array.isArray(rows[rowIndex].options) ? rows[rowIndex].options : [];
      if (optionIndex >= options.length) return;
      options.splice(optionIndex, 1);
      rows[rowIndex].options = options;
      clampRowMaxSelect(rows[rowIndex]);
      cleanCollapseForDeletedRows();
      sync();
      render();
    }
  });

  const applyFieldChange = (element) => {
    const rowIndex = Number.parseInt(String(element.dataset.row || "-1"), 10);
    if (!Number.isFinite(rowIndex) || rowIndex < 0 || rowIndex >= rows.length) return false;

    const rowField = String(element.dataset.rowField || "");
    const optionField = String(element.dataset.optField || "");
    if (rowField) {
      if (element instanceof HTMLInputElement && element.type === "checkbox") {
        rows[rowIndex][rowField] = Boolean(element.checked);
      } else if (rowField === "max_select") {
        rows[rowIndex][rowField] = Number.parseInt(String(element.value || "1"), 10) || 1;
      } else {
        rows[rowIndex][rowField] = String(element.value || "");
      }
      if (rowField === "selection_mode" || rowField === "max_select") {
        clampRowMaxSelect(rows[rowIndex]);
        sync();
        render();
        return true;
      }
      sync();
      return true;
    }

    if (!optionField) return false;
    const optionIndex = Number.parseInt(String(element.dataset.opt || "-1"), 10);
    if (!Number.isFinite(optionIndex) || optionIndex < 0) return false;
    const options = Array.isArray(rows[rowIndex].options) ? rows[rowIndex].options : [];
    if (optionIndex >= options.length) return false;

    if (element instanceof HTMLInputElement && element.type === "checkbox") {
      options[optionIndex][optionField] = Boolean(element.checked);
    } else {
      options[optionIndex][optionField] = String(element.value || "");
    }
    rows[rowIndex].options = options;
    sync();
    return true;
  };

  list.addEventListener("input", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (!target) return;
    applyFieldChange(target);
  });

  list.addEventListener("change", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (!target) return;
    applyFieldChange(target);
  });

  form.addEventListener("submit", () => {
    const sanitized = rows.map((row) => normalizeItem(row, rootSelectionValue()));
    rows = sanitized;
    sync();
  });

  render();
  sync();
})();
