(() => {{
  const form = document.getElementById("embedMessagesForm");
  if (!form) return;

  const itemsJsonInput = document.getElementById("embedItemsJsonInput");
  const selectedIdInput = document.getElementById("embedSelectedIdInput");
  const picker = document.getElementById("embedPicker");
  const searchInput = document.getElementById("embedSearchInput");
  const emptyState = document.getElementById("embedEmptyState");
  const editorWrap = document.getElementById("embedEditorWrap");
  const createFirstBtn = document.getElementById("createFirstEmbedBtn");
  const createHeroBtn = document.getElementById("createHeroEmbedBtn");
  const templateCountEl = document.getElementById("embedTemplateCount");
  const selectedFieldCountEl = document.getElementById("embedSelectedFieldCount");
  const selectedResponseCountEl = document.getElementById("embedSelectedResponseCount");
  const selectedLabelEl = document.getElementById("embedSelectedLabel");
  const summaryModeEl = document.getElementById("embedSummaryMode");
  const summaryFieldsEl = document.getElementById("embedSummaryFields");
  const summaryResponsesEl = document.getElementById("embedSummaryResponses");
  const summaryChannelEl = document.getElementById("embedSummaryChannel");

  const addFieldBtn = document.getElementById("embedAddFieldBtn");
  const addResponseBtn = document.getElementById("embedAddResponseBtn");
  const responsesList = document.getElementById("embedResponsesList");
  const responsesEmpty = document.getElementById("embedResponsesEmpty");
  const fieldsWrap = document.getElementById("embedFieldsWrap");
  const moreBtn = document.getElementById("embedMoreBtn");
  const moreMenu = document.getElementById("embedMoreMenu");
  const duplicateBtn = document.getElementById("embedDuplicateBtn");
  const deleteBtn = document.getElementById("embedDeleteBtn");
  const duplicateInlineBtn = document.getElementById("embedDuplicateInlineBtn");
  const deleteInlineBtn = document.getElementById("embedDeleteInlineBtn");
  const sendBtn = document.getElementById("embedSendBtn");
  const sendStatusEl = document.getElementById("embedSendStatus");
  const saveStateEl = document.getElementById("embedSaveState");
  const tabTextBtn = document.getElementById("embedTabTextBtn");
  const tabEmbedBtn = document.getElementById("embedTabEmbedBtn");
  const textComposer = document.getElementById("embedTextComposer");
  const embedComposerArea = document.getElementById("embedComposerArea");
  const colorDots = Array.from(document.querySelectorAll(".embed-color-dot"));

  const channelTemplate = document.querySelector("#embedChannelTemplateHolder select");
  const channelSelect = document.getElementById("embedChannelSelect");
  const sendChannelSelect = document.getElementById("embedSendChannelSelect");

  const authorIconPicker = document.getElementById("embedAuthorIconPicker");
  const thumbPicker = document.getElementById("embedThumbPicker");
  const imagePicker = document.getElementById("embedImagePicker");
  const footerIconPicker = document.getElementById("embedFooterIconPicker");
  const authorIconFileInput = document.getElementById("embedAuthorIconFileInput");
  const thumbnailFileInput = document.getElementById("embedThumbnailFileInput");
  const imageFileInput = document.getElementById("embedImageFileInput");
  const footerIconFileInput = document.getElementById("embedFooterIconFileInput");

  if (channelTemplate && channelSelect) {{
    channelSelect.innerHTML = channelTemplate.innerHTML;
  }}
  if (channelTemplate && sendChannelSelect) {{
    sendChannelSelect.innerHTML = channelTemplate.innerHTML;
  }}

  const inputs = {{
    name: document.getElementById("embedNameInput"),
    content: document.getElementById("embedContentInput"),
    color: document.getElementById("embedColorInput"),
    author_name: document.getElementById("embedAuthorNameInput"),
    author_url: document.getElementById("embedAuthorUrlInput"),
    author_icon_url: document.getElementById("embedAuthorIconInput"),
    title: document.getElementById("embedTitleInput"),
    description: document.getElementById("embedDescriptionInput"),
    thumbnail_url: document.getElementById("embedThumbnailInput"),
    image_url: document.getElementById("embedImageInput"),
    footer_text: document.getElementById("embedFooterTextInput"),
    footer_icon_url: document.getElementById("embedFooterIconInput"),
    channel_id: document.getElementById("embedChannelSelect"),
  }};

  const preview = {{
    card: document.getElementById("embedPreviewCard"),
    content: document.getElementById("embedPreviewContent"),
    authorIcon: document.getElementById("embedPreviewAuthorIcon"),
    author: document.getElementById("embedPreviewAuthor"),
    thumbnail: document.getElementById("embedPreviewThumbnail"),
    title: document.getElementById("embedPreviewTitle"),
    desc: document.getElementById("embedPreviewDesc"),
    fields: document.getElementById("embedPreviewFields"),
    image: document.getElementById("embedPreviewImage"),
    footerWrap: document.getElementById("embedPreviewFooterWrap"),
    footerIcon: document.getElementById("embedPreviewFooterIcon"),
    footer: document.getElementById("embedPreviewFooter"),
  }};

  const responseModal = document.getElementById("embedResponseModal");
  const responseTypeInput = document.getElementById("responseTypeInput");
  const responseLabelInput = document.getElementById("responseLabelInput");
  const responseStyleInput = document.getElementById("responseStyleInput");
  const responseEmojiInput = document.getElementById("responseEmojiInput");
  const responseOptionsInput = document.getElementById("responseOptionsInput");
  const responseCancelBtn = document.getElementById("responseCancelBtn");
  const responseSaveBtn = document.getElementById("responseSaveBtn");
  const responseOptionsWrap = responseOptionsInput ? responseOptionsInput.closest(".field-item") : null;

  const counters = [
    {{ input: inputs.name, el: document.getElementById("embedNameCounter"), max: 90 }},
    {{ input: inputs.content, el: document.getElementById("embedContentCounter"), max: null }},
    {{ input: inputs.title, el: document.getElementById("embedTitleCounter"), max: 256 }},
    {{ input: inputs.description, el: document.getElementById("embedDescriptionCounter"), max: 4000 }},
    {{ input: inputs.footer_text, el: document.getElementById("embedFooterCounter"), max: 2048 }},
  ];

  if (moreMenu && moreMenu.parentElement !== document.body) {{
    document.body.appendChild(moreMenu);
  }}
  if (responseModal && responseModal.parentElement !== document.body) {{
    document.body.appendChild(responseModal);
  }}

  const escapeHtml = (value) =>
    String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  let items = [];
  try {{
    const decoded = JSON.parse(itemsJsonInput?.value || "[]");
    items = Array.isArray(decoded) ? decoded : [];
  }} catch (_error) {{
    items = [];
  }}

  let selectedId = String(selectedIdInput?.value || "");
  let mode = "embed";
  let hasInitialized = false;
  let isDirty = false;

  const setSaveState = (state, text) => {{
    if (!saveStateEl) return;
    saveStateEl.classList.remove("state-dirty", "state-saving", "state-saved");
    if (state === "dirty") saveStateEl.classList.add("state-dirty");
    if (state === "saving") saveStateEl.classList.add("state-saving");
    if (state === "saved") saveStateEl.classList.add("state-saved");
    saveStateEl.textContent = String(text || "");
  }};

  const markDirty = () => {{
    if (!hasInitialized) return;
    isDirty = true;
    setSaveState("dirty", "มีการเปลี่ยนแปลงที่ยังไม่บันทึก");
  }};

  const markSaved = () => {{
    isDirty = false;
    setSaveState("saved", "ข้อมูลล่าสุดถูกบันทึกแล้ว");
  }};

  const showSendStatus = (type, message) => {{
    if (!sendStatusEl) return;
    sendStatusEl.classList.remove("ok", "error", "show");
    if (type === "ok") sendStatusEl.classList.add("ok");
    if (type === "error") sendStatusEl.classList.add("error");
    if (message) {{
      sendStatusEl.textContent = String(message);
      sendStatusEl.classList.add("show");
    }} else {{
      sendStatusEl.textContent = "";
    }}
  }};

  const newEmbed = () => ({{
    id: `embed_${{Date.now()}}_${{Math.floor(Math.random() * 1000)}}`,
    name: "new embed",
    content: "",
    color: "#5865F2",
    author_name: "",
    author_url: "",
    author_icon_url: "",
    title: "",
    description: "",
    thumbnail_url: "",
    image_url: "",
    footer_text: "",
    footer_icon_url: "",
    channel_id: "",
    enabled: true,
    fields: [],
    responses: [],
  }});

  const cleanSelected = () => {{
    const ids = new Set(items.map((x) => String(x?.id || "")));
    if (!selectedId || !ids.has(selectedId)) {{
      selectedId = items.length ? String(items[0]?.id || "") : "";
    }}
    if (selectedIdInput) selectedIdInput.value = selectedId;
  }};

  const currentItem = () => items.find((x) => String(x?.id || "") === selectedId) || null;

  const saveHidden = () => {{
    if (itemsJsonInput) itemsJsonInput.value = JSON.stringify(items);
    if (selectedIdInput) selectedIdInput.value = selectedId;
  }};

  const updateCounters = () => {{
    counters.forEach((row) => {{
      const inputEl = row?.input;
      const counterEl = row?.el;
      if (!inputEl || !counterEl) return;
      const valueLength = String(inputEl.value || "").length;
      if (typeof row.max === "number" && row.max > 0) {{
        counterEl.textContent = `${{valueLength}}/${{row.max}}`;
      }} else {{
        counterEl.textContent = `${{valueLength}}/2000+`;
      }}
    }});
  }};

  const channelNameFromValue = (value) => {{
    const target = String(value || "").trim();
    if (!target || !channelSelect || !channelSelect.options) return "-";
    const options = Array.from(channelSelect.options);
    const matched = options.find((opt) => String(opt.value || "") === target);
    if (!matched) return "-";
    return String(matched.textContent || "-").trim() || "-";
  }};

  const updateSummary = (item) => {{
    if (summaryModeEl) summaryModeEl.textContent = mode;
    if (summaryFieldsEl) summaryFieldsEl.textContent = String(Array.isArray(item?.fields) ? item.fields.length : 0);
    if (summaryResponsesEl) summaryResponsesEl.textContent = String(Array.isArray(item?.responses) ? item.responses.length : 0);
    if (summaryChannelEl) summaryChannelEl.textContent = item ? channelNameFromValue(item.channel_id) : "-";
  }};

  const updateHeroMeta = (item) => {{
    if (templateCountEl) templateCountEl.textContent = String(items.length);
    if (selectedFieldCountEl) selectedFieldCountEl.textContent = String(Array.isArray(item?.fields) ? item.fields.length : 0);
    if (selectedResponseCountEl) selectedResponseCountEl.textContent = String(Array.isArray(item?.responses) ? item.responses.length : 0);
    if (selectedLabelEl) {{
      selectedLabelEl.textContent = item ? `กำลังแก้ไข: ${{String(item?.name || "new embed")}}` : "ยังไม่มีรายการ Embed";
    }}
    updateSummary(item);
  }};

  const highlightColor = (colorHex) => {{
    const normalized = String(colorHex || "").toLowerCase();
    colorDots.forEach((dot) => {{
      const dotColor = String(dot.getAttribute("data-color") || "").toLowerCase();
      dot.classList.toggle("is-active", dotColor === normalized);
    }});
  }};

  const renderPicker = () => {{
    const q = String(searchInput?.value || "").trim().toLowerCase();
    const visible = items.filter((x) => !q || String(x?.name || "").toLowerCase().includes(q));
    if (!picker) return;

    if (!visible.length) {{
      picker.innerHTML = '<option value="">ไม่พบรายการที่ค้นหา</option>';
      picker.disabled = true;
      return;
    }}

    picker.disabled = false;
    picker.innerHTML = visible
      .map((x) => `<option value="${{escapeHtml(String(x?.id || ""))}}">${{escapeHtml(String(x?.name || "new embed"))}}</option>`)
      .join("");

    if (!visible.some((x) => String(x?.id || "") === selectedId)) {{
      selectedId = String(visible[0]?.id || "");
    }}
    picker.value = selectedId;
  }};

  const renderFields = (item) => {{
    if (!fieldsWrap) return;
    const fields = Array.isArray(item?.fields) ? item.fields : [];

    fieldsWrap.innerHTML = fields
      .map((field, index) => {{
        const isInline = Boolean(field?.inline);
        return `
          <article class="embed-field-row">
            <div style="display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;">
              <input data-field-name="${{index}}" type="text" maxlength="256" value="${{escapeHtml(String(field?.name || ""))}}" placeholder="หัวข้อ">
              <div style="display:flex;gap:8px;align-items:center;">
                <button type="button" class="embed-field-ctrl ${{isInline ? "active" : ""}}" data-field-inline-btn="${{index}}" title="จัดบรรทัด (Inline)">
                  <i class="fa-solid fa-table-columns" aria-hidden="true"></i>
                </button>
                <button type="button" class="embed-field-ctrl" data-field-remove="${{index}}" title="ลบ" style="color:#ef4444;">
                  <i class="fa-solid fa-trash" aria-hidden="true"></i>
                </button>
              </div>
            </div>
            <textarea data-field-value="${{index}}" style="min-height:78px;margin-top:8px;" placeholder="คำอธิบาย">${{escapeHtml(String(field?.value || ""))}}</textarea>
          </article>
        `;
      }})
      .join("");

    fieldsWrap.querySelectorAll("[data-field-name],[data-field-value]").forEach((el) => {{
      const update = () => {{
        const cur = currentItem();
        if (!cur) return;
        const idx = Number(el.getAttribute("data-field-name") || el.getAttribute("data-field-value"));
        if (!Number.isFinite(idx) || !Array.isArray(cur.fields) || !cur.fields[idx]) return;
        if (el.hasAttribute("data-field-name")) cur.fields[idx].name = String(el.value || "").slice(0, 256);
        if (el.hasAttribute("data-field-value")) cur.fields[idx].value = String(el.value || "").slice(0, 1024);
        renderPreview(cur);
        updateHeroMeta(cur);
        saveHidden();
        markDirty();
      }};
      el.addEventListener("input", update);
      el.addEventListener("change", update);
    }});

    fieldsWrap.querySelectorAll("[data-field-inline-btn]").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        const cur = currentItem();
        if (!cur || !Array.isArray(cur.fields)) return;
        const idx = Number(btn.getAttribute("data-field-inline-btn"));
        if (!Number.isFinite(idx) || !cur.fields[idx]) return;
        cur.fields[idx].inline = !Boolean(cur.fields[idx].inline);
        renderFields(cur);
        renderPreview(cur);
        updateHeroMeta(cur);
        saveHidden();
        markDirty();
      }});
    }});

    fieldsWrap.querySelectorAll("[data-field-remove]").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        const cur = currentItem();
        if (!cur || !Array.isArray(cur.fields)) return;
        const idx = Number(btn.getAttribute("data-field-remove"));
        if (!Number.isFinite(idx)) return;
        cur.fields.splice(idx, 1);
        renderFields(cur);
        renderPreview(cur);
        updateHeroMeta(cur);
        saveHidden();
        markDirty();
      }});
    }});
  }};

  const renderResponses = (item) => {{
    const responses = Array.isArray(item?.responses) ? item.responses : [];
    if (responsesList) {{
      responsesList.innerHTML = responses
        .map((resp, index) => {{
          const responseType = String(resp?.type || "button");
          const responseStyle = String(resp?.style || "primary");
          const responseEmoji = String(resp?.emoji || "");
          return `
            <article class="embed-field-row">
              <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap;">
                <strong>${{escapeHtml(String(resp?.label || "ไม่มีชื่อ"))}}</strong>
                <button type="button" class="danger-btn" data-response-remove="${{index}}">
                  <i class="fa-solid fa-trash" aria-hidden="true"></i>
                  ลบ
                </button>
              </div>
              <div class="muted" style="font-size:12px;margin-top:4px;">
                ประเภท: ${{escapeHtml(responseType)}} | สไตล์: ${{escapeHtml(responseStyle)}}${{responseEmoji ? ` | Emoji: ${{escapeHtml(responseEmoji)}}` : ""}}
              </div>
            </article>
          `;
        }})
        .join("");

      responsesList.querySelectorAll("[data-response-remove]").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          const cur = currentItem();
          if (!cur || !Array.isArray(cur.responses)) return;
          const idx = Number(btn.getAttribute("data-response-remove"));
          if (!Number.isFinite(idx)) return;
          cur.responses.splice(idx, 1);
          renderResponses(cur);
          updateHeroMeta(cur);
          saveHidden();
          markDirty();
        }});
      }});
    }}
    if (responsesEmpty) {{
      responsesEmpty.style.display = responses.length ? "none" : "";
    }}
  }};

  const renderPreview = (item) => {{
    if (!item || !preview.card) return;

    const getResolvedUrl = (pickerEl, value) => {{
      const local = String(pickerEl?.getAttribute("data-local-preview") || "").trim();
      return String(local || value || "").trim();
    }};

    const setImage = (imgEl, url) => {{
      if (!imgEl) return;
      const next = String(url || "").trim();
      if (next) {{
        imgEl.src = next;
        imgEl.style.display = "block";
      }} else {{
        imgEl.removeAttribute("src");
        imgEl.style.display = "none";
      }}
    }};

    const color = String(item.color || "#5865F2");
    preview.card.style.borderLeftColor = color;

    if (preview.content) {{
      preview.content.textContent = String(item.content || "");
      preview.content.style.display = String(item.content || "").trim() ? "" : "none";
    }}

    const authorIcon = getResolvedUrl(authorIconPicker, item.author_icon_url);
    const thumbnailUrl = getResolvedUrl(thumbPicker, item.thumbnail_url);
    const imageUrl = getResolvedUrl(imagePicker, item.image_url);
    const footerIconUrl = getResolvedUrl(footerIconPicker, item.footer_icon_url);

    if (preview.author) preview.author.textContent = String(item.author_name || "");
    if (preview.title) preview.title.textContent = String(item.title || "หัวข้อ");
    if (preview.desc) preview.desc.textContent = String(item.description || "คำอธิบาย");
    if (preview.footer) preview.footer.textContent = String(item.footer_text || "");

    setImage(preview.authorIcon, authorIcon);
    setImage(preview.thumbnail, thumbnailUrl);
    setImage(preview.image, imageUrl);
    setImage(preview.footerIcon, footerIconUrl);

    if (preview.footerWrap) {{
      const hasFooter = String(item.footer_text || "").trim() || footerIconUrl;
      preview.footerWrap.style.display = hasFooter ? "" : "none";
    }}

    if (preview.fields) {{
      const fields = Array.isArray(item.fields) ? item.fields : [];
      preview.fields.innerHTML = fields
        .map((field) => {{
          return `
            <div class="panel-sub" style="padding:8px;${{field?.inline ? "display:inline-block;min-width:40%;" : ""}}">
              <strong>${{escapeHtml(String(field?.name || ""))}}</strong>
              <div class="muted embed-preview-field-value" style="font-size:12px;">${{escapeHtml(String(field?.value || ""))}}</div>
            </div>
          `;
        }})
        .join("");
    }}
  }};

  const paintImageButtons = () => {{
    const item = currentItem();
    if (!item) return;
    const setBackground = (el, url) => {{
      if (!el) return;
      const localPreview = String(el.getAttribute("data-local-preview") || "").trim();
      const finalUrl = String(localPreview || url || "").trim();
      if (finalUrl) {{
        el.style.backgroundImage = `linear-gradient(rgba(0,0,0,.35), rgba(0,0,0,.35)), url(${{finalUrl}})`;
        el.style.backgroundSize = "cover";
        el.style.backgroundPosition = "center";
        el.style.color = "#fff";
      }} else {{
        el.style.backgroundImage = "";
        el.style.color = "";
      }}
    }};
    setBackground(authorIconPicker, String(item.author_icon_url || ""));
    setBackground(thumbPicker, String(item.thumbnail_url || ""));
    setBackground(imagePicker, String(item.image_url || ""));
    setBackground(footerIconPicker, String(item.footer_icon_url || ""));
  }};

  const bindFilePreview = (pickerEl, fileInputEl, valueInputEl, keyName) => {{
    if (!pickerEl || !fileInputEl || !valueInputEl) return;
    fileInputEl.addEventListener("change", () => {{
      const item = currentItem();
      const file = fileInputEl.files && fileInputEl.files[0] ? fileInputEl.files[0] : null;
      if (!file) {{
        pickerEl.removeAttribute("data-local-preview");
        paintImageButtons();
        renderPreview(currentItem());
        return;
      }}
      valueInputEl.value = "";
      if (item) item[keyName] = "";
      const reader = new FileReader();
      reader.onload = () => {{
        pickerEl.setAttribute("data-local-preview", String(reader.result || ""));
        paintImageButtons();
        renderPreview(currentItem());
        saveHidden();
        markDirty();
      }};
      reader.readAsDataURL(file);
    }});
  }};

  const setMode = (nextMode) => {{
    mode = nextMode === "text" ? "text" : "embed";
    if (tabTextBtn) tabTextBtn.className = mode === "text" ? "primary-btn" : "ghost-btn";
    if (tabEmbedBtn) tabEmbedBtn.className = mode === "embed" ? "primary-btn" : "ghost-btn";
    if (textComposer) textComposer.style.display = mode === "text" ? "" : "none";
    if (embedComposerArea) embedComposerArea.style.display = mode === "embed" ? "" : "none";
    updateSummary(currentItem());
    try {{
      window.localStorage.setItem("embed_messages_mode", mode);
    }} catch (_error) {{}}
  }};

  const renderEditor = () => {{
    cleanSelected();
    const item = currentItem();
    const hasItems = items.length > 0;

    if (emptyState) emptyState.style.display = hasItems ? "none" : "flex";
    if (editorWrap) editorWrap.style.display = hasItems ? "" : "none";
    if (sendBtn) sendBtn.disabled = !hasItems;
    if (!hasItems) showSendStatus("", "");

    renderPicker();
    updateHeroMeta(item);

    if (!item) {{
      updateCounters();
      saveHidden();
      return;
    }}

    Object.entries(inputs).forEach(([key, el]) => {{
      if (!el) return;
      const value = item[key];
      if (el.type === "color") {{
        el.value = String(value || "#5865F2");
      }} else {{
        el.value = String(value || "");
      }}
    }});

    highlightColor(String(item.color || "#5865F2"));
    renderFields(item);
    renderResponses(item);
    renderPreview(item);
    paintImageButtons();

    if (sendChannelSelect) {{
      sendChannelSelect.value = String(item.channel_id || "");
    }}

    updateCounters();
    updateHeroMeta(item);
    saveHidden();
  }};

  const updateCurrent = (key, value) => {{
    const item = currentItem();
    if (!item) return;
    item[key] = value;
    if (key === "name") renderPicker();
    if (key === "channel_id" && sendChannelSelect) {{
      sendChannelSelect.value = String(value || "");
    }}
    if (key === "color") {{
      highlightColor(String(value || "#5865F2"));
    }}
    renderPreview(item);
    updateCounters();
    updateHeroMeta(item);
    saveHidden();
    markDirty();
  }};

  const createNewEmbed = () => {{
    const item = newEmbed();
    items.push(item);
    selectedId = String(item.id);
    renderEditor();
    markDirty();
  }};

  const updateResponseOptionsVisibility = () => {{
    if (!responseTypeInput || !responseOptionsWrap || !responseOptionsInput) return;
    const isSelect = String(responseTypeInput.value || "button") === "select";
    responseOptionsWrap.style.display = isSelect ? "" : "none";
    responseOptionsInput.disabled = !isSelect;
  }};

  searchInput?.addEventListener("input", renderPicker);
  picker?.addEventListener("change", () => {{
    selectedId = String(picker.value || "");
    renderEditor();
  }});

  createFirstBtn?.addEventListener("click", createNewEmbed);
  createHeroBtn?.addEventListener("click", createNewEmbed);

  tabTextBtn?.addEventListener("click", () => setMode("text"));
  tabEmbedBtn?.addEventListener("click", () => setMode("embed"));

  Object.entries(inputs).forEach(([key, el]) => {{
    if (!el) return;
    const handler = () => {{
      updateCurrent(key, String(el.value || ""));
    }};
    el.addEventListener("input", handler);
    el.addEventListener("change", handler);
  }});

  sendChannelSelect?.addEventListener("change", () => {{
    const nextChannelId = String(sendChannelSelect.value || "");
    if (inputs.channel_id) inputs.channel_id.value = nextChannelId;
    updateCurrent("channel_id", nextChannelId);
  }});

  colorDots.forEach((dot) => {{
    dot.addEventListener("click", () => {{
      const c = String(dot.getAttribute("data-color") || "#5865F2");
      if (inputs.color) inputs.color.value = c;
      updateCurrent("color", c);
    }});
  }});

  authorIconPicker?.addEventListener("click", () => authorIconFileInput?.click());
  thumbPicker?.addEventListener("click", () => thumbnailFileInput?.click());
  imagePicker?.addEventListener("click", () => imageFileInput?.click());
  footerIconPicker?.addEventListener("click", () => footerIconFileInput?.click());

  bindFilePreview(authorIconPicker, authorIconFileInput, inputs.author_icon_url, "author_icon_url");
  bindFilePreview(thumbPicker, thumbnailFileInput, inputs.thumbnail_url, "thumbnail_url");
  bindFilePreview(imagePicker, imageFileInput, inputs.image_url, "image_url");
  bindFilePreview(footerIconPicker, footerIconFileInput, inputs.footer_icon_url, "footer_icon_url");

  addFieldBtn?.addEventListener("click", () => {{
    const item = currentItem();
    if (!item) return;
    if (!Array.isArray(item.fields)) item.fields = [];
    item.fields.push({{
      id: `field_${{Date.now()}}_${{Math.floor(Math.random() * 1000)}}`,
      name: "หัวข้อ",
      value: "คำอธิบาย",
      inline: false,
      align: "left",
    }});
    renderFields(item);
    renderPreview(item);
    updateHeroMeta(item);
    saveHidden();
    markDirty();
  }});

  const setResponseModalOpen = (open) => {{
    if (!responseModal) return;
    responseModal.classList.toggle("open", Boolean(open));
    responseModal.setAttribute("aria-hidden", open ? "false" : "true");
    document.body.classList.toggle("modal-open", Boolean(open));
  }};

  addResponseBtn?.addEventListener("click", () => {{
    updateResponseOptionsVisibility();
    setResponseModalOpen(true);
  }});

  responseTypeInput?.addEventListener("change", updateResponseOptionsVisibility);

  responseCancelBtn?.addEventListener("click", () => {{
    setResponseModalOpen(false);
  }});

  responseSaveBtn?.addEventListener("click", () => {{
    const item = currentItem();
    if (!item) return;
    if (!Array.isArray(item.responses)) item.responses = [];

    const responseType = String(responseTypeInput?.value || "button");
    const optionsRaw = String(responseOptionsInput?.value || "").split(/\r?\n/);
    const options = optionsRaw.map((x) => String(x || "").trim()).filter(Boolean).slice(0, 25);

    item.responses.push({{
      id: `resp_${{Date.now()}}_${{Math.floor(Math.random() * 1000)}}`,
      type: responseType,
      label: String(responseLabelInput?.value || "").slice(0, 80) || "ตัวเลือก",
      style: String(responseStyleInput?.value || "primary"),
      emoji: String(responseEmojiInput?.value || "").slice(0, 64),
      options: responseType === "select" ? options : [],
    }});

    setResponseModalOpen(false);
    if (responseLabelInput) responseLabelInput.value = "";
    if (responseEmojiInput) responseEmojiInput.value = "";
    if (responseOptionsInput) responseOptionsInput.value = "";
    if (responseTypeInput) responseTypeInput.value = "button";
    updateResponseOptionsVisibility();
    renderResponses(item);
    updateHeroMeta(item);
    saveHidden();
    markDirty();
  }});

  const closeMoreMenu = () => {{
    if (!moreMenu) return;
    moreMenu.classList.remove("is-open");
  }};

  const openMoreMenu = () => {{
    if (!moreMenu || !moreBtn) return;
    const rect = moreBtn.getBoundingClientRect();
    const menuWidth = Math.max(220, rect.width + 120);
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const topRaw = Math.round(rect.bottom + 8);
    const leftRaw = Math.round(rect.right - menuWidth);
    const left = Math.max(8, Math.min(leftRaw, Math.max(8, viewportWidth - menuWidth - 8)));

    moreMenu.style.minWidth = `${{menuWidth}}px`;
    moreMenu.style.left = `${{left}}px`;
    moreMenu.style.top = `${{Math.max(8, topRaw)}}px`;
    moreMenu.classList.add("is-open");

    const menuRect = moreMenu.getBoundingClientRect();
    if (menuRect.bottom > viewportHeight - 8) {{
      const upTop = Math.max(8, Math.round(rect.top - menuRect.height - 8));
      moreMenu.style.top = `${{upTop}}px`;
    }}
  }};

  const duplicateSelected = () => {{
    const item = currentItem();
    if (!item) return;
    const clone = JSON.parse(JSON.stringify(item));
    clone.id = `embed_${{Date.now()}}_${{Math.floor(Math.random() * 1000)}}`;
    clone.name = `${{String(item.name || "new embed")}} copy`;
    items.push(clone);
    selectedId = String(clone.id);
    closeMoreMenu();
    renderEditor();
    markDirty();
  }};

  const deleteSelected = () => {{
    if (!selectedId) return;
    if (!window.confirm("ต้องการลบ Embed นี้ใช่หรือไม่?")) return;
    items = items.filter((x) => String(x?.id || "") !== selectedId);
    closeMoreMenu();
    cleanSelected();
    renderEditor();
    markDirty();
  }};

  moreBtn?.addEventListener("click", () => {{
    if (!moreMenu) return;
    if (moreMenu.classList.contains("is-open")) {{
      closeMoreMenu();
    }} else {{
      openMoreMenu();
    }}
  }});

  duplicateBtn?.addEventListener("click", duplicateSelected);
  duplicateInlineBtn?.addEventListener("click", duplicateSelected);
  deleteBtn?.addEventListener("click", deleteSelected);
  deleteInlineBtn?.addEventListener("click", deleteSelected);

  document.addEventListener("click", (event) => {{
    if (!moreMenu || !moreBtn) return;
    if (!moreMenu.classList.contains("is-open")) return;
    if (moreMenu.contains(event.target) || moreBtn.contains(event.target)) return;
    closeMoreMenu();
  }});

  window.addEventListener("resize", closeMoreMenu);
  window.addEventListener("scroll", closeMoreMenu, true);

  responseModal?.addEventListener("click", (event) => {{
    if (event.target === responseModal) setResponseModalOpen(false);
  }});

  document.addEventListener("keydown", (event) => {{
    if (event.key === "Escape") {{
      closeMoreMenu();
      setResponseModalOpen(false);
    }}
  }});

  const sendBtnDefaultHtml = sendBtn ? sendBtn.innerHTML : "";

  sendBtn?.addEventListener("click", async () => {{
    if (!sendBtn) return;
    saveHidden();
    try {{
      sendBtn.disabled = true;
      showSendStatus("", "");
      sendBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> กำลังส่ง...';

      const response = await fetch(`/dashboard/guild/{current_guild['id']}/embed_messages/send`, {{
        method: "POST",
        headers: {{
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          "X-Requested-With": "fetch",
        }},
        credentials: "same-origin",
        body: new URLSearchParams({{
          selected_id: selectedIdInput?.value || "",
          items_json: itemsJsonInput?.value || "[]",
          send_channel_id: sendChannelSelect?.value || "",
        }}),
      }});

      const payload = await response.json().catch(() => ({{ ok: false, message: "ส่งข้อความไม่สำเร็จ" }}));
      const message = String(payload?.message || (response.ok ? "ส่ง Embed สำเร็จ" : "ส่ง Embed ไม่สำเร็จ"));
      showSendStatus(response.ok && payload?.ok !== false ? "ok" : "error", message);
    }} catch (_error) {{
      showSendStatus("error", "ไม่สามารถเชื่อมต่อเพื่อส่ง Embed ได้");
    }} finally {{
      sendBtn.disabled = false;
      sendBtn.innerHTML = sendBtnDefaultHtml;
    }}
  }});

  form.addEventListener("submit", () => {{
    saveHidden();
    setSaveState("saving", "กำลังบันทึก...");
  }});

  try {{
    const savedMode = String(window.localStorage.getItem("embed_messages_mode") || "").toLowerCase();
    if (savedMode === "text" || savedMode === "embed") {{
      mode = savedMode;
    }}
  }} catch (_error) {{}}

  setMode(mode);
  updateResponseOptionsVisibility();
  renderEditor();
  hasInitialized = true;
  if (!isDirty) markSaved();
}})();
