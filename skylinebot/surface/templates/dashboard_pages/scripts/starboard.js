(() => {{
  const form = document.getElementById('starboardForm');
  if (!form) return;

  const submitBtn = document.getElementById('starboardSubmitBtn');
  const modeInput = document.getElementById('starboardMessageModeInput');
  const textTabBtn = document.getElementById('starboardTextTabBtn');
  const embedTabBtn = document.getElementById('starboardEmbedTabBtn');
  const embedEditor = document.getElementById('starboardEmbedEditor');
  const colorInput = document.getElementById('starboardColorInput');
  const messageContentInput = document.getElementById('starboardMessageContentInput');
  const embedDescInput = document.getElementById('starboardDescInput');
  const enabledToggle = document.getElementById('starboardEnabledToggle');
  const emojiInput = document.getElementById('starboardEmojiInput');
  const starsLimitInput = document.getElementById('starboardStarsLimitInput');

  const authorIconInput = document.getElementById('starboardAuthorIconInput');
  const thumbInput = document.getElementById('starboardThumbnailInput');
  const imageInput = document.getElementById('starboardImageInput');
  const footerIconInput = document.getElementById('starboardFooterIconInput');
  const authorIconFileInput = document.getElementById('starboardAuthorIconFileInput');
  const thumbnailFileInput = document.getElementById('starboardThumbnailFileInput');
  const imageFileInput = document.getElementById('starboardImageFileInput');
  const footerIconFileInput = document.getElementById('starboardFooterIconFileInput');
  const authorIconPicker = document.getElementById('starboardAuthorIconPicker');
  const thumbPicker = document.getElementById('starboardThumbPicker');
  const imagePicker = document.getElementById('starboardImagePicker');
  const footerIconPicker = document.getElementById('starboardFooterIconPicker');

  const addFieldBtn = document.getElementById('starboardAddFieldBtn');
  const fieldsWrap = document.getElementById('starboardFieldsWrap');
  const fieldsJsonInput = document.getElementById('starboardFieldsJsonInput');

  const messageContentWrap = document.getElementById('starboardMessageContentWrap');
  const messageTokensWrap = document.getElementById('starboardMessageTokensWrap');

  const summaryMode = document.getElementById('starboardSummaryMode');
  const summaryThreshold = document.getElementById('starboardSummaryThreshold');
  const summaryEmoji = document.getElementById('starboardSummaryEmoji');
  const summarySource = document.getElementById('starboardSummarySource');
  const summaryTarget = document.getElementById('starboardSummaryTarget');
  const statusBadge = document.getElementById('starboardStatusBadge');
  const warningsList = document.getElementById('starboardWarnings');

  const channelInput = form.querySelector('[name="channel_id"]');
  const enabledChannelInput = form.querySelector('[name="enabled_channel_id"]');

  const escapeHtml = (value) => String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

  const getFieldLabel = (node, fallback = '-') => {{
    if (!(node instanceof HTMLElement)) return fallback;
    if (node instanceof HTMLSelectElement) {{
      const option = node.options[node.selectedIndex];
      const value = String(node.value || '').trim();
      if (!value) return fallback;
      return String(option?.textContent || value).trim() || fallback;
    }}
    const text = String((node.value || node.textContent || '')).trim();
    return text || fallback;
  }};

  const insertTokenAtCursor = (input, token) => {{
    if (!(input instanceof HTMLInputElement) && !(input instanceof HTMLTextAreaElement)) return;
    const current = String(input.value || '');
    const start = Number.isInteger(input.selectionStart) ? Number(input.selectionStart) : current.length;
    const end = Number.isInteger(input.selectionEnd) ? Number(input.selectionEnd) : current.length;
    input.value = `${{current.slice(0, start)}}${{token}}${{current.slice(end)}}`;
    const cursor = start + token.length;
    input.focus();
    input.setSelectionRange(cursor, cursor);
    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
  }};

  let fields = [];
  try {{
    const decoded = JSON.parse(fieldsJsonInput?.value || '[]');
    fields = Array.isArray(decoded) ? decoded : [];
  }} catch (_error) {{
    fields = [];
  }}

  const syncFields = () => {{
    if (!fieldsJsonInput) return;
    fieldsJsonInput.value = JSON.stringify(fields || []);
  }};

  const renderWarnings = (items) => {{
    if (!warningsList) return;
    if (!Array.isArray(items) || items.length === 0) {{
      warningsList.innerHTML = '<li>พร้อมใช้งานแล้ว สามารถกดบันทึกได้ทันที</li>';
      return;
    }}
    warningsList.innerHTML = items.map((row) => `<li>${{escapeHtml(row)}}</li>`).join('');
  }};

  const updateSummary = () => {{
    const mode = String(modeInput?.value || 'embed').trim().toLowerCase() === 'text' ? 'ข้อความ' : 'Embed';
    const threshold = Math.max(1, Math.min(20, Number(starsLimitInput?.value || '3') || 3));
    const emoji = String(emojiInput?.value || '⭐').trim() || '⭐';
    const sourceLabel = String(enabledChannelInput?.value || '').trim()
      ? getFieldLabel(enabledChannelInput, 'ทุกช่อง')
      : 'ทุกช่อง';
    const targetValue = String(channelInput?.value || '').trim();
    const targetLabel = targetValue ? getFieldLabel(channelInput, targetValue) : 'ยังไม่ได้เลือก';
    const enabled = Boolean(enabledToggle?.checked);

    if (summaryMode) summaryMode.textContent = mode;
    if (summaryThreshold) summaryThreshold.textContent = `${{threshold}} ดาว`;
    if (summaryEmoji) summaryEmoji.textContent = emoji;
    if (summarySource) summarySource.textContent = sourceLabel;
    if (summaryTarget) summaryTarget.textContent = targetLabel;

    const issues = [];
    if (enabled && !targetValue) issues.push('ยังไม่ได้เลือกช่องปลายทาง');
    if (enabled && !emoji) issues.push('ยังไม่ได้ตั้งค่าอีโมจิ');
    if (enabled && threshold < 1) issues.push('Threshold ต้องมากกว่า 0');

    if (statusBadge) {{
      statusBadge.classList.remove('ok', 'warn', 'off');
      if (!enabled) {{
        statusBadge.textContent = 'ปิดอยู่';
        statusBadge.classList.add('off');
      }} else if (issues.length > 0) {{
        statusBadge.textContent = 'ต้องแก้ไข';
        statusBadge.classList.add('warn');
      }} else {{
        statusBadge.textContent = 'พร้อมใช้งาน';
        statusBadge.classList.add('ok');
      }}
    }}

    renderWarnings(issues);
  }};

  const setMode = (nextMode) => {{
    const mode = nextMode === 'text' ? 'text' : 'embed';
    if (modeInput) modeInput.value = mode;
    if (textTabBtn) textTabBtn.className = mode === 'text' ? 'primary-btn' : 'ghost-btn';
    if (embedTabBtn) embedTabBtn.className = mode === 'embed' ? 'primary-btn' : 'ghost-btn';
    if (messageContentWrap) messageContentWrap.style.display = mode === 'text' ? '' : 'none';
    if (messageTokensWrap) messageTokensWrap.style.display = mode === 'text' ? '' : 'none';
    if (embedEditor) embedEditor.style.display = mode === 'embed' ? '' : 'none';
    updateSummary();
  }};

  const paintImageButtons = () => {{
    const setBackground = (el, url) => {{
      if (!el) return;
      const localPreview = String(el.getAttribute('data-local-preview') || '').trim();
      const finalUrl = String(localPreview || url || '').trim();
      if (finalUrl) {{
        el.style.backgroundImage = `linear-gradient(rgba(0,0,0,.35), rgba(0,0,0,.35)), url(${{finalUrl}})`;
        el.style.backgroundSize = 'cover';
        el.style.backgroundPosition = 'center';
        el.style.color = '#fff';
      }} else {{
        el.style.backgroundImage = '';
        el.style.color = '';
      }}
    }};

    setBackground(authorIconPicker, authorIconInput?.value || '');
    setBackground(thumbPicker, thumbInput?.value || '');
    setBackground(imagePicker, imageInput?.value || '');
    setBackground(footerIconPicker, footerIconInput?.value || '');
  }};

  const clearMediaField = (pickerEl, fileInputEl, hiddenInputEl) => {{
    if (pickerEl) pickerEl.removeAttribute('data-local-preview');
    if (fileInputEl) fileInputEl.value = '';
    if (hiddenInputEl) hiddenInputEl.value = '';
    paintImageButtons();
  }};

  const bindFilePreview = (pickerEl, fileInputEl, hiddenUrlInputEl) => {{
    if (!pickerEl || !fileInputEl) return;

    pickerEl.addEventListener('click', () => fileInputEl.click());
    pickerEl.addEventListener('dblclick', (event) => {{
      event.preventDefault();
      clearMediaField(pickerEl, fileInputEl, hiddenUrlInputEl);
    }});

    fileInputEl.addEventListener('change', () => {{
      const file = fileInputEl.files && fileInputEl.files[0] ? fileInputEl.files[0] : null;
      if (!file) {{
        pickerEl.removeAttribute('data-local-preview');
        paintImageButtons();
        return;
      }}
      if (hiddenUrlInputEl) hiddenUrlInputEl.value = '';
      const reader = new FileReader();
      reader.onload = () => {{
        try {{
          pickerEl.setAttribute('data-local-preview', String(reader.result || ''));
        }} catch (_error) {{
          pickerEl.removeAttribute('data-local-preview');
        }}
        paintImageButtons();
      }};
      reader.readAsDataURL(file);
    }});
  }};

  const renderFields = () => {{
    if (!fieldsWrap) return;

    fieldsWrap.innerHTML = (fields || []).map((field, index) => `
      <article class="embed-field-row">
        <div style="display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;">
          <input data-sb-field-name="${{index}}" type="text" maxlength="256" value="${{escapeHtml(String(field?.name || ''))}}" placeholder="หัวข้อ">
          <div style="display:flex;gap:8px;align-items:center;">
            <button type="button" class="sb-field-ctrl ${{String(field?.align || 'left') === 'center' ? 'active' : ''}}" data-sb-field-align="${{index}}" title="จัดตำแหน่ง">C</button>
            <button type="button" class="sb-field-ctrl" data-sb-field-remove="${{index}}" title="ลบ" style="color:#ef4444;">x</button>
          </div>
        </div>
        <textarea data-sb-field-value="${{index}}" style="min-height:78px;margin-top:8px;text-align:${{String(field?.align || 'left') === 'center' ? 'center' : 'left'}};" placeholder="รายละเอียดฟิลด์">${{escapeHtml(String(field?.value || ''))}}</textarea>
      </article>
    `).join('');

    fieldsWrap.querySelectorAll('[data-sb-field-name],[data-sb-field-value]').forEach((el) => {{
      const update = () => {{
        const idx = Number(el.getAttribute('data-sb-field-name') || el.getAttribute('data-sb-field-value'));
        if (!Number.isFinite(idx) || !fields[idx]) return;
        if (el.hasAttribute('data-sb-field-name')) fields[idx].name = String(el.value || '').slice(0, 256);
        if (el.hasAttribute('data-sb-field-value')) fields[idx].value = String(el.value || '').slice(0, 1024);
        syncFields();
      }};
      el.addEventListener('input', update);
      el.addEventListener('change', update);
    }});

    fieldsWrap.querySelectorAll('[data-sb-field-align]').forEach((btn) => {{
      btn.addEventListener('click', () => {{
        const idx = Number(btn.getAttribute('data-sb-field-align'));
        if (!Number.isFinite(idx) || !fields[idx]) return;
        fields[idx].align = String(fields[idx].align || 'left') === 'center' ? 'left' : 'center';
        renderFields();
        syncFields();
      }});
    }});

    fieldsWrap.querySelectorAll('[data-sb-field-remove]').forEach((btn) => {{
      btn.addEventListener('click', () => {{
        const idx = Number(btn.getAttribute('data-sb-field-remove'));
        if (!Number.isFinite(idx)) return;
        fields.splice(idx, 1);
        renderFields();
        syncFields();
      }});
    }});
  }};

  textTabBtn?.addEventListener('click', () => setMode('text'));
  embedTabBtn?.addEventListener('click', () => setMode('embed'));

  form.querySelectorAll('[data-step-target]').forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const targetName = String(btn.getAttribute('data-step-target') || '');
      const delta = Number(btn.getAttribute('data-step-delta') || '0');
      if (!targetName || !Number.isFinite(delta)) return;
      const input = form.querySelector(`input[name="${{targetName}}"]`);
      if (!(input instanceof HTMLInputElement)) return;
      const min = Number(input.min || '0');
      const max = Number(input.max || '999999');
      const current = Number(input.value || '0');
      const next = Math.max(min, Math.min(max, current + delta));
      input.value = String(next);
      input.dispatchEvent(new Event('input', {{ bubbles: true }}));
      updateSummary();
    }});
  }});

  document.querySelectorAll('.embed-color-dot').forEach((dot) => {{
    dot.addEventListener('click', () => {{
      const c = String(dot.getAttribute('data-color') || '#5865F2');
      if (colorInput) colorInput.value = c;
      if (embedEditor) embedEditor.style.borderLeftColor = c;
    }});
  }});

  colorInput?.addEventListener('input', () => {{
    if (embedEditor) embedEditor.style.borderLeftColor = colorInput.value || '#5865F2';
  }});

  bindFilePreview(authorIconPicker, authorIconFileInput, authorIconInput);
  bindFilePreview(thumbPicker, thumbnailFileInput, thumbInput);
  bindFilePreview(imagePicker, imageFileInput, imageInput);
  bindFilePreview(footerIconPicker, footerIconFileInput, footerIconInput);

  addFieldBtn?.addEventListener('click', () => {{
    if ((fields || []).length >= 25) return;
    fields.push({{
      id: `field_${{Date.now()}}_${{Math.floor(Math.random() * 1000)}}`,
      name: 'หัวข้อ',
      value: '',
      inline: false,
      align: 'left',
    }});
    renderFields();
    syncFields();
  }});

  form.querySelectorAll('[data-sb-token]').forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const token = String(btn.getAttribute('data-sb-token') || '').trim();
      if (!token) return;

      const activeEl = document.activeElement;
      if (activeEl instanceof HTMLInputElement || activeEl instanceof HTMLTextAreaElement) {{
        if (form.contains(activeEl)) {{
          insertTokenAtCursor(activeEl, token);
          return;
        }}
      }}

      const fallback = (String(modeInput?.value || 'embed') === 'text') ? messageContentInput : embedDescInput;
      if (fallback) insertTokenAtCursor(fallback, token);
    }});
  }});

  [enabledToggle, emojiInput, starsLimitInput, channelInput, enabledChannelInput, modeInput].forEach((node) => {{
    node?.addEventListener('change', updateSummary);
    node?.addEventListener('input', updateSummary);
  }});

  form.addEventListener('submit', (event) => {{
    const enabled = Boolean(enabledToggle?.checked);
    const targetValue = String(channelInput?.value || '').trim();
    const threshold = Number(starsLimitInput?.value || '0');
    const emoji = String(emojiInput?.value || '').trim();

    if (enabled && !targetValue) {{
      event.preventDefault();
      alert('กรุณาเลือกช่องปลายทางของ Starboard ก่อนบันทึก');
      channelInput?.focus();
      return;
    }}
    if (enabled && (!Number.isFinite(threshold) || threshold < 1)) {{
      event.preventDefault();
      alert('Stars Limit ต้องมีค่าอย่างน้อย 1');
      starsLimitInput?.focus();
      return;
    }}
    if (enabled && !emoji) {{
      event.preventDefault();
      alert('กรุณาตั้งค่า Emoji สำหรับ Starboard');
      emojiInput?.focus();
      return;
    }}

    if (submitBtn instanceof HTMLButtonElement) {{
      submitBtn.disabled = true;
      submitBtn.textContent = 'กำลังบันทึก...';
    }}
  }});

  setMode(modeInput?.value || 'embed');
  renderFields();
  syncFields();
  paintImageButtons();
  updateSummary();
}})();
