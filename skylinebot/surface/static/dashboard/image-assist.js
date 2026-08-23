(() => {
  const IMAGE_KEYWORDS = ["image", "thumbnail", "thumb", "icon", "avatar", "banner", "logo"];
  const EXCLUDE_KEYS = [
    "author_url",
    "webhook_url",
    "back_to_server_url",
    "callback_url",
    "public_donate_url",
    "invite_url",
  ];
  const MAX_HINT_CHANNELS = 24;
  const seen = new WeakSet();
  const proxyBindings = [];
  let bindingLoopTimer = 0;

  const ensureStyles = () => {
    if (document.getElementById("dashboard-image-assist-style")) return;
    const style = document.createElement("style");
    style.id = "dashboard-image-assist-style";
    style.textContent = `
      .dashboard-image-assist-wrap {
        margin-top: 8px;
        display: grid;
        gap: 8px;
      }
      .dashboard-image-assist-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
      }
      .dashboard-image-assist-btn {
        border: 1px dashed rgba(145, 168, 255, 0.55);
        background: rgba(30, 38, 66, 0.45);
        color: #dfe8ff;
        border-radius: 10px;
        padding: 7px 10px;
        font-size: 12px;
        cursor: pointer;
      }
      .dashboard-image-assist-btn:hover {
        background: rgba(52, 68, 118, 0.6);
      }
      .dashboard-image-assist-status {
        font-size: 12px;
        color: var(--muted, #a8b6d9);
      }
      .dashboard-image-assist-preview {
        width: 84px;
        height: 84px;
        object-fit: cover;
        border-radius: 10px;
        border: 1px solid rgba(155, 177, 238, 0.35);
        background: rgba(15, 22, 44, 0.65);
        display: none;
      }
      .dashboard-image-assist-proxy-label {
        display: block;
        margin-bottom: 6px;
        font-size: 12px;
        color: var(--muted, #a8b6d9);
      }
    `;
    document.head.appendChild(style);
  };

  const normalize = (value) => String(value || "").trim();

  const isImageField = (input) => {
    if (!(input instanceof HTMLInputElement)) return false;
    const type = normalize(input.type).toLowerCase();
    if (!["hidden", "text", "url"].includes(type)) return false;
    const key = `${normalize(input.name)} ${normalize(input.id)}`.toLowerCase();
    if (!key) return false;
    if (!key.includes("url")) return false;
    if (!IMAGE_KEYWORDS.some((word) => key.includes(word))) return false;
    if (EXCLUDE_KEYS.some((word) => key.includes(word))) return false;
    return true;
  };

  const extractGuildId = (form) => {
    if (!(form instanceof HTMLFormElement)) return "";
    const action = normalize(form.getAttribute("action"));
    if (!action) return "";
    const match = action.match(/\/dashboard\/guild\/(\d+)\//i);
    return match ? String(match[1] || "") : "";
  };

  const detectUploadTarget = (form) => {
    if (!(form instanceof HTMLFormElement)) return "embed_messages";
    const action = normalize(form.getAttribute("action")).toLowerCase();
    const path = action.split("?")[0];
    if (path.includes("/donate")) return "donate";
    if (path.includes("/verify")) return "verify";
    if (path.includes("/colors")) return "colors";
    if (path.includes("/starboard")) return "starboard";
    if (path.includes("/tickets")) return "tickets";
    if (path.includes("/welcome") || path.includes("/welcomer") || path.includes("/leaver")) return "welcome";
    if (path.includes("/promote")) return "promote";
    if (path.includes("/shop")) return "shop";
    if (path.includes("/ocr")) return "ocr";
    if (path.includes("/temp_channels")) return "temp_channels";
    if (path.includes("/voice_randomizer")) return "voice_randomizer";
    return "embed_messages";
  };

  const detectAssetKind = (input) => {
    const key = `${normalize(input?.name)} ${normalize(input?.id)}`.toLowerCase();
    if (key.includes("icon") || key.includes("avatar")) return "icon";
    if (key.includes("thumbnail") || key.includes("thumb")) return "thumbnail";
    if (key.includes("banner") || key.includes("background") || key.includes("cover") || key.includes("header")) {
      return "banner";
    }
    return "image";
  };

  const collectChannelHints = (form) => {
    if (!(form instanceof HTMLFormElement)) return [];
    const out = [];
    const pushIfDigit = (value) => {
      const text = normalize(value);
      if (!/^\d+$/.test(text)) return;
      if (out.includes(text)) return;
      out.push(text);
    };
    const fields = form.querySelectorAll("input[name], select[name]");
    fields.forEach((field) => {
      if (!(field instanceof HTMLInputElement) && !(field instanceof HTMLSelectElement)) return;
      const key = `${normalize(field.name)} ${normalize(field.id)}`.toLowerCase();
      if (!key.includes("channel")) return;
      pushIfDigit(field.value);
    });
    return out.slice(0, MAX_HINT_CHANNELS);
  };

  const prettyLabel = (raw) => {
    const text = normalize(raw) || "image_url";
    return text
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const cssEscape = (value) => {
    const text = normalize(value);
    if (!text) return "";
    try {
      if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
        return CSS.escape(text);
      }
    } catch (_error) {
      // fall through
    }
    return text.replace(/["\\]/g, "\\$&");
  };

  const dispatchValueEvents = (input) => {
    if (!(input instanceof HTMLInputElement)) return;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  };

  const setValue = (input, value) => {
    if (!(input instanceof HTMLInputElement)) return;
    input.value = normalize(value);
    dispatchValueEvents(input);
  };

  const buildProxyUrlInput = (hiddenInput) => {
    const fieldItem = document.createElement("div");
    fieldItem.className = "field-item dashboard-image-assist-proxy";
    const label = document.createElement("label");
    label.className = "dashboard-image-assist-proxy-label";
    label.textContent = prettyLabel(hiddenInput.name || hiddenInput.id || "image_url");
    const input = document.createElement("input");
    input.type = "url";
    input.placeholder = "https://.../image.png";
    input.value = normalize(hiddenInput.value);
    fieldItem.append(label, input);
    hiddenInput.insertAdjacentElement("afterend", fieldItem);
    return { input, container: fieldItem };
  };

  const findCompanionFileInput = (form, input) => {
    if (!(form instanceof HTMLFormElement) || !(input instanceof HTMLInputElement)) return null;
    const keyName = normalize(input.name);
    const keyId = normalize(input.id);

    const candidateSelectors = [];
    if (keyName.endsWith("_url")) {
      candidateSelectors.push(`input[name="${keyName.slice(0, -4)}_file"]`);
    }
    if (keyId.toLowerCase().endsWith("urlinput")) {
      candidateSelectors.push(`#${cssEscape(`${keyId.slice(0, -8)}FileInput`)}`);
    }
    if (keyId.toLowerCase().endsWith("url")) {
      candidateSelectors.push(`#${cssEscape(`${keyId.slice(0, -3)}FileInput`)}`);
    }
    for (const selector of candidateSelectors) {
      const found = form.querySelector(selector);
      if (found instanceof HTMLInputElement && normalize(found.type).toLowerCase() === "file") {
        return found;
      }
    }
    return null;
  };

  const ensureFallbackFileInput = (form, urlInput) => {
    const fallback = document.createElement("input");
    fallback.type = "file";
    fallback.accept = ".png,.jpg,.jpeg,.webp,.gif";
    fallback.style.display = "none";
    fallback.dataset.imageAssistFallback = "1";
    fallback.name = "";
    form.appendChild(fallback);
    return fallback;
  };

  const updatePreview = (previewEl, value) => {
    if (!(previewEl instanceof HTMLImageElement)) return;
    const next = normalize(value);
    if (!next) {
      previewEl.removeAttribute("src");
      previewEl.style.display = "none";
      return;
    }
    previewEl.src = next;
    previewEl.style.display = "";
  };

  const uploadFileToServer = async ({ file, guildId, uploadTarget, assetKind, channelHints }) => {
    const payload = new FormData();
    payload.append("file", file, file.name || "upload.png");
    payload.append("upload_target", uploadTarget);
    payload.append("asset_kind", normalize(assetKind) || "image");
    payload.append("channel_hints", channelHints.join(","));
    const response = await fetch(`/dashboard/guild/${guildId}/upload-image`, {
      method: "POST",
      body: payload,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data || data.ok !== true || !normalize(data.url)) {
      const message = normalize(data?.message) || "Upload failed";
      throw new Error(message);
    }
    return data;
  };

  const bindProxySync = (hiddenInput, visibleInput) => {
    if (!(hiddenInput instanceof HTMLInputElement) || !(visibleInput instanceof HTMLInputElement)) return;
    const syncFromVisible = () => {
      if (hiddenInput.value === visibleInput.value) return;
      hiddenInput.value = visibleInput.value;
      dispatchValueEvents(hiddenInput);
    };
    visibleInput.addEventListener("input", syncFromVisible);
    visibleInput.addEventListener("change", syncFromVisible);
    proxyBindings.push({
      hiddenInput,
      visibleInput,
      lastHiddenValue: normalize(hiddenInput.value),
    });
    startBindingLoop();
  };

  const enhanceInput = (sourceInput) => {
    if (!(sourceInput instanceof HTMLInputElement)) return;
    if (seen.has(sourceInput)) return;
    seen.add(sourceInput);

    const form = sourceInput.closest("form");
    if (!(form instanceof HTMLFormElement)) return;
    const guildId = extractGuildId(form);
    if (!guildId) return;
    const assetKind = detectAssetKind(sourceInput);

    let urlInput = sourceInput;
    let hostContainer = sourceInput.closest(".field-item") || sourceInput.parentElement;
    if (!(hostContainer instanceof HTMLElement)) return;

    if (normalize(sourceInput.type).toLowerCase() === "hidden") {
      const proxy = buildProxyUrlInput(sourceInput);
      urlInput = proxy.input;
      hostContainer = proxy.container;
      bindProxySync(sourceInput, urlInput);
    }

    if (!(urlInput instanceof HTMLInputElement)) return;
    if (normalize(urlInput.dataset.imageAssistBound) === "1") return;
    urlInput.dataset.imageAssistBound = "1";

    const wrap = document.createElement("div");
    wrap.className = "dashboard-image-assist-wrap";
    const row = document.createElement("div");
    row.className = "dashboard-image-assist-row";

    const uploadBtn = document.createElement("button");
    uploadBtn.type = "button";
    uploadBtn.className = "dashboard-image-assist-btn";
    uploadBtn.textContent = "Upload Image";

    const status = document.createElement("span");
    status.className = "dashboard-image-assist-status";
    status.textContent = "Ready";

    const preview = document.createElement("img");
    preview.className = "dashboard-image-assist-preview";
    preview.alt = "image-preview";

    row.append(uploadBtn, status);
    wrap.append(row, preview);
    hostContainer.appendChild(wrap);

    let fileInput = findCompanionFileInput(form, sourceInput);
    if (!(fileInput instanceof HTMLInputElement)) {
      fileInput = ensureFallbackFileInput(form, urlInput);
    }

    const showStatus = (message, isError = false) => {
      status.textContent = normalize(message) || "Ready";
      status.style.color = isError ? "#fda4af" : "";
    };

    const setUrlValue = (value) => {
      setValue(urlInput, value);
      if (sourceInput !== urlInput && sourceInput instanceof HTMLInputElement) {
        sourceInput.value = normalize(value);
        dispatchValueEvents(sourceInput);
      }
      updatePreview(preview, value);
    };

    const uploadCurrentFile = async () => {
      if (!(fileInput instanceof HTMLInputElement)) return;
      const file = fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
      if (!file) return;
      showStatus("Uploading...");
      uploadBtn.disabled = true;
      try {
        const data = await uploadFileToServer({
          file,
          guildId,
          uploadTarget: detectUploadTarget(form),
          assetKind,
          channelHints: collectChannelHints(form),
        });
        setUrlValue(normalize(data.url));
        const before = Number(data.original_size || 0);
        const after = Number(data.optimized_size || 0);
        if (before > 0 && after > 0 && after < before) {
          const saved = Math.max(0, Math.round(((before - after) / before) * 100));
          showStatus(`Uploaded (compressed ${saved}%)`);
        } else {
          showStatus("Uploaded");
        }
        fileInput.value = "";
      } catch (error) {
        const message = normalize(error?.message) || "Upload failed";
        showStatus(message, true);
      } finally {
        uploadBtn.disabled = false;
      }
    };

    uploadBtn.addEventListener("click", () => fileInput?.click());
    fileInput.addEventListener("change", uploadCurrentFile);
    urlInput.addEventListener("input", () => updatePreview(preview, urlInput.value));
    urlInput.addEventListener("change", () => updatePreview(preview, urlInput.value));

    updatePreview(preview, urlInput.value);
  };

  const scan = () => {
    ensureStyles();
    const inputs = document.querySelectorAll("form input[name], form input[id]");
    inputs.forEach((input) => {
      if (!isImageField(input)) return;
      enhanceInput(input);
    });
  };

  function startBindingLoop() {
    if (bindingLoopTimer || !proxyBindings.length) return;
    bindingLoopTimer = window.setInterval(() => {
      if (!proxyBindings.length) return;
      proxyBindings.forEach((item) => {
        if (!item || !(item.hiddenInput instanceof HTMLInputElement) || !(item.visibleInput instanceof HTMLInputElement)) return;
        const hiddenValue = normalize(item.hiddenInput.value);
        if (hiddenValue === item.lastHiddenValue) return;
        item.lastHiddenValue = hiddenValue;
        if (normalize(item.visibleInput.value) !== hiddenValue) {
          item.visibleInput.value = hiddenValue;
          dispatchValueEvents(item.visibleInput);
        }
      });
    }, 1200);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scan, { once: true });
  } else {
    scan();
  }
  startBindingLoop();

  let scanTimer = 0;
  const observerRoot = document.querySelector(".dashboard-dynamic-content") || document.body || document.documentElement;
  const observer = new MutationObserver(() => {
    if (scanTimer) {
      window.clearTimeout(scanTimer);
    }
    scanTimer = window.setTimeout(() => {
      scanTimer = 0;
      scan();
    }, 250);
  });
  observer.observe(observerRoot, { childList: true, subtree: true });
})();
