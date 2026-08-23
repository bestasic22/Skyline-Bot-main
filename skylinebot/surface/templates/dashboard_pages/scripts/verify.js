(() => {{
  const form = document.getElementById('verifySettingsForm');
  if (!form) return;

  const verifyViewModeInput = document.getElementById('verifyViewModeInput');
  const verifyPanelSection = document.getElementById('verifyPanelSection');
  const webVerifyPageSection = document.getElementById('webVerifyPageSection');

  if (verifyViewModeInput) {{
    const fromServer = String(verifyViewModeInput.value || '').trim().toLowerCase();
    verifyViewModeInput.value = fromServer === 'web_verify' ? 'web_verify' : 'verify';
  }}

  const pagesRoot = document.getElementById('verifyPagesRoot');
  const pagesJson = document.getElementById('verifyPagesJson');
  const addPageBtn = document.getElementById('verifyAddPageBtn');
  const removePageBtn = document.getElementById('verifyRemovePageBtn');
  const planLimitBadge = document.getElementById('verifyPlanLimitBadge');

  const buttonColorSelect = document.getElementById('verifyButtonColorSelect');
  const buttonLabelInput = document.getElementById('verifyButtonLabelInput');
  const buttonEmojiInput = document.getElementById('verifyButtonEmojiInput');
  const previewButton = document.getElementById('verifyPreviewButton');

  const previewTitle = document.getElementById('verifyPreviewTitle');
  const previewDesc = document.getElementById('verifyPreviewDescription');
  const previewMeta = document.getElementById('verifyPreviewMeta');
  const previewImage = document.getElementById('verifyPreviewImage');
  const previewThumb = document.getElementById('verifyPreviewThumb');
  const previewFooter = document.getElementById('verifyPreviewFooter');
  const previewRoleGive = document.getElementById('verifyPreviewRoleGive');
  const previewRoleRemove = document.getElementById('verifyPreviewRoleRemove');
  const webPreviewTitle = document.getElementById('webVerifyPreviewTitle');
  const webPreviewDesc = document.getElementById('webVerifyPreviewDescription');
  const webPreviewImage = document.getElementById('webVerifyPreviewImage');
  const webPreviewThumb = document.getElementById('webVerifyPreviewThumb');
  const webPreviewFooter = document.getElementById('webVerifyPreviewFooter');
  const webPreviewButton = document.getElementById('webVerifyPreviewButton');

  const descInput = document.getElementById('verifyDescriptionInput') || form.querySelector('textarea[name="description"]');
  const rewardRoleIdsInput = document.getElementById('input_reward_role_ids');
  const removeRoleIdsInput = document.getElementById('input_remove_role_ids');
  const autoRoleEnabledSelect = form.querySelector('select[name="auto_role_enabled"]');
  const webRewardRoleIdsInput = document.getElementById('input_web_verify_reward_role_ids');
  const webAutoRoleEnabledSelect = form.querySelector('select[name="web_verify_auto_role_enabled"]');

  const embedTitleInput = document.getElementById('verifyEmbedTitleInput');
  const embedFooterInput = document.getElementById('verifyEmbedFooterInput');
  const embedThumbnailInput = document.getElementById('verifyEmbedThumbnailInput');
  const embedImageInput = document.getElementById('verifyEmbedImageInput');

  const webButtonLabelInput = document.getElementById('verifyWebButtonLabelInput');
  const webButtonColorSelect = document.getElementById('verifyWebButtonColorSelect');
  const webButtonEmojiInput = document.getElementById('verifyWebButtonEmojiInput');
  const webEmbedTitleInput = document.getElementById('verifyWebEmbedTitleInput');
  const webEmbedDescriptionInput = document.getElementById('verifyWebEmbedDescriptionInput');
  const webEmbedFooterInput = document.getElementById('verifyWebEmbedFooterInput');
  const webEmbedThumbInput = document.getElementById('verifyWebEmbedThumbInput');
  const webVerifyInputs = [
    document.getElementById('verifyWebIntroInput'),
    document.getElementById('verifyWebSuccessInput'),
    document.getElementById('verifyWebErrorInput'),
    webButtonLabelInput,
    document.getElementById('verifyBackButtonLabelInput'),
    document.getElementById('verifyBackToServerUrlInput'),
    webEmbedTitleInput,
    webEmbedDescriptionInput,
    webEmbedFooterInput,
    webEmbedThumbInput,
    document.getElementById('verifyWebEmbedImageInput'),
    webButtonColorSelect,
    webButtonEmojiInput,
    webRewardRoleIdsInput,
    webAutoRoleEnabledSelect,
  ];

  const dropzone = document.getElementById('verifyWebDropzone');
  const webImageInput = document.getElementById('verifyWebEmbedImageInput');
  const fileInput = document.getElementById('verifyWebEmbedImageFileInput');
  const fileName = document.getElementById('verifyWebFileName');

  const verifyPlanLimits = {{
    maxPages: {max_pages},
    maxItemsPerPage: {max_items_per_page},
    titleMaxLength: {title_max_length},
  }};

  const colorMap = {{
    green: '#25c26e',
    blurple: '#5865f2',
    red: '#e14343',
    gray: '#6b7280',
  }};

  const defaultItem = () => ({{
    label: 'Question',
    placeholder: '',
    description: '',
    input_type: 'short',
  }});

  const defaultPage = () => ({{
    title: 'Verification Form',
    items: [defaultItem()],
  }});

  let pages = [];
  try {{
    pages = JSON.parse({json.dumps(pages_seed)});
  }} catch (_error) {{
    pages = [];
  }}
  if (!Array.isArray(pages) || pages.length === 0) {{
    pages = [defaultPage()];
  }}

  const escapeHtml = (value) => String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');

  const normalizeItem = (item) => {{
    const inputType = String(item?.input_type || 'short').toLowerCase() === 'paragraph' ? 'paragraph' : 'short';
    return {{
      label: String(item?.label || 'Question').slice(0, 45),
      placeholder: String(item?.placeholder || '').slice(0, 45),
      description: String(item?.description || '').slice(0, 45),
      input_type: inputType,
    }};
  }};

  const clampPages = () => {{
    if (!Array.isArray(pages)) pages = [];
    pages = pages.slice(0, Math.max(1, verifyPlanLimits.maxPages));
    if (pages.length === 0) pages = [defaultPage()];

    pages = pages.map((page) => {{
      const normalizedTitle = String(page?.title || 'Verification Form').slice(0, verifyPlanLimits.titleMaxLength);
      let items = Array.isArray(page?.items) ? page.items.map(normalizeItem) : [];
      items = items.filter((item) => item.label || item.placeholder || item.description);
      if (items.length === 0) items = [defaultItem()];
      if (items.length > verifyPlanLimits.maxItemsPerPage) {{
        items = items.slice(0, verifyPlanLimits.maxItemsPerPage);
      }}
      return {{
        title: normalizedTitle || 'Verification Form',
        items,
      }};
    }});
  }};

  const rolePills = (container) => {{
    if (!container) return ['-'];
    const names = [];
    container.querySelectorAll('.tag-pill').forEach((tag) => {{
      const cleaned = String(tag.textContent || '').replace('ร—', '').trim();
      if (cleaned) names.push(cleaned);
    }});
    return names.length ? names : ['-'];
  }};

  const renderRolePills = (target, names, bg) => {{
    if (!target) return;
    target.innerHTML = names
      .map((name) => `<span style="padding:2px 8px;border-radius:999px;border:1px solid var(--line);background:${{bg}};font-size:12px;">${{escapeHtml(name)}}</span>`)
      .join('');
  }};

  const renderPreview = () => {{
    const colorKey = buttonColorSelect?.value || 'green';
    const buttonLabel = (buttonLabelInput?.value || 'ยืนยัน').slice(0, 45) || 'ยืนยัน';
    const buttonEmoji = (buttonEmojiInput?.value || '').trim().slice(0, 64);

    if (previewButton) {{
      previewButton.style.background = colorMap[colorKey] || colorMap.green;
      previewButton.textContent = `${{buttonEmoji ? `${{buttonEmoji}} ` : ''}}${{buttonLabel}}`;
    }}

    if (previewTitle) {{
      previewTitle.textContent = (embedTitleInput?.value || 'ยืนยันตัวตน').slice(0, 120) || 'ยืนยันตัวตน';
    }}

    if (previewDesc) {{
      previewDesc.textContent = (descInput?.value || 'Verification description').slice(0, 400) || 'Verification description';
    }}

    if (previewFooter) {{
      previewFooter.textContent = (embedFooterInput?.value || '').slice(0, 200);
    }}

    if (previewMeta) {{
      previewMeta.textContent = `Pages ${{pages.length}}/${{verifyPlanLimits.maxPages}}`;
    }}

    const thumbUrl = String(embedThumbnailInput?.value || '').trim();
    if (previewThumb) {{
      if (thumbUrl) {{
        previewThumb.src = thumbUrl;
        previewThumb.style.display = '';
      }} else {{
        previewThumb.style.display = 'none';
      }}
    }}

    if (previewImage) {{
      const imageUrl = String(embedImageInput?.value || '').trim();
      if (imageUrl) {{
        previewImage.src = imageUrl;
        previewImage.style.display = '';
      }} else {{
        previewImage.style.display = 'none';
      }}
    }}

    renderRolePills(previewRoleGive, rolePills(document.getElementById('tags_reward_role_ids')), 'rgba(74,222,128,.14)');
    renderRolePills(previewRoleRemove, rolePills(document.getElementById('tags_remove_role_ids')), 'rgba(248,113,113,.14)');
    renderWebVerifyPreview();
  }};

  const renderWebVerifyPreview = () => {{
    const webColorKey = String(webButtonColorSelect?.value || 'green').trim().toLowerCase();
    const webLabel = (webButtonLabelInput?.value || 'ยืนยันตัวตนตอนนี้').slice(0, 45) || 'ยืนยันตัวตนตอนนี้';
    const webEmoji = (webButtonEmojiInput?.value || '').trim().slice(0, 64);
    const webTitle = (webEmbedTitleInput?.value || 'ยืนยันตัวตนผ่านเว็บ').slice(0, 120) || 'ยืนยันตัวตนผ่านเว็บ';
    const webDesc = (webEmbedDescriptionInput?.value || 'กดปุ่มด้านล่างเพื่อเปิดหน้า Web Verify').slice(0, 400) || 'กดปุ่มด้านล่างเพื่อเปิดหน้า Web Verify';
    const webFooter = (webEmbedFooterInput?.value || '').slice(0, 200);
    const webThumbUrl = String(webEmbedThumbInput?.value || '').trim();
    const webImageUrl = String(webImageInput?.value || '').trim();

    if (webPreviewButton) {{
      webPreviewButton.style.background = colorMap[webColorKey] || colorMap.green;
      webPreviewButton.textContent = `${{webEmoji ? `${{webEmoji}} ` : ''}}${{webLabel}}`;
    }}
    if (webPreviewTitle) webPreviewTitle.textContent = webTitle;
    if (webPreviewDesc) webPreviewDesc.textContent = webDesc;
    if (webPreviewFooter) webPreviewFooter.textContent = webFooter;

    if (webPreviewThumb) {{
      if (webThumbUrl) {{
        webPreviewThumb.src = webThumbUrl;
        webPreviewThumb.style.display = '';
      }} else {{
        webPreviewThumb.style.display = 'none';
      }}
    }}

    if (webPreviewImage) {{
      if (webImageUrl) {{
        webPreviewImage.src = webImageUrl;
        webPreviewImage.style.display = '';
      }} else {{
        webPreviewImage.style.display = 'none';
      }}
    }}
  }};

  const bindEditorInputs = () => {{
    pagesRoot.querySelectorAll('[data-vf-page]').forEach((el) => {{
      el.addEventListener('input', () => {{
        const pageIndex = Number(el.getAttribute('data-vf-page-index') || -1);
        const itemIndex = Number(el.getAttribute('data-vf-item-index') || -1);
        const field = String(el.getAttribute('data-vf-field') || '');
        if (!Number.isFinite(pageIndex) || pageIndex < 0 || !pages[pageIndex]) return;

        if (itemIndex >= 0) {{
          if (!pages[pageIndex].items[itemIndex]) return;
          pages[pageIndex].items[itemIndex][field] = String(el.value || '');
        }} else {{
          pages[pageIndex][field] = String(el.value || '');
        }}

        clampPages();
        pagesJson.value = JSON.stringify(pages);
        refreshPageCounters();
        renderPreview();
      }});
    }});

    pagesRoot.querySelectorAll('[data-vf-add-item]').forEach((btn) => {{
      btn.addEventListener('click', () => {{
        const pageIndex = Number(btn.getAttribute('data-vf-add-item') || -1);
        if (!Number.isFinite(pageIndex) || pageIndex < 0 || !pages[pageIndex]) return;
        if ((pages[pageIndex].items || []).length >= verifyPlanLimits.maxItemsPerPage) return;
        pages[pageIndex].items.push(defaultItem());
        renderPages();
      }});
    }});

    pagesRoot.querySelectorAll('[data-vf-remove-item]').forEach((btn) => {{
      btn.addEventListener('click', () => {{
        const pageIndex = Number(btn.getAttribute('data-vf-page') || -1);
        const itemIndex = Number(btn.getAttribute('data-vf-remove-item') || -1);
        if (!Number.isFinite(pageIndex) || !Number.isFinite(itemIndex)) return;
        if (!pages[pageIndex] || !pages[pageIndex].items[itemIndex]) return;
        pages[pageIndex].items.splice(itemIndex, 1);
        renderPages();
      }});
    }});
  }};

  const refreshPageCounters = () => {{
    pagesRoot.querySelectorAll('[data-vf-page-summary]').forEach((node) => {{
      const pageIndex = Number(node.getAttribute('data-vf-page-summary') || -1);
      if (!Number.isFinite(pageIndex) || pageIndex < 0 || !pages[pageIndex]) return;
      const titleText = escapeHtml(String(pages[pageIndex].title || 'Verification Form'));
      node.innerHTML = `Page (${{pageIndex + 1}}/${{verifyPlanLimits.maxPages}}): ${{titleText}}`;
    }});
    pagesRoot.querySelectorAll('[data-vf-page-title-label]').forEach((node) => {{
      const pageIndex = Number(node.getAttribute('data-vf-page-title-label') || -1);
      if (!Number.isFinite(pageIndex) || pageIndex < 0 || !pages[pageIndex]) return;
      const titleLength = String(pages[pageIndex].title || '').length;
      node.textContent = `Title (${{titleLength}} / ${{verifyPlanLimits.titleMaxLength}})`;
    }});
  }};

  const renderPages = () => {{
    clampPages();

    pagesRoot.innerHTML = pages
      .map((page, pIndex) => {{
        const itemsHtml = (page.items || [])
          .map((item, iIndex) => `
            <details class="command-category" style="margin-bottom:8px;" ${{iIndex === 0 ? 'open' : ''}}>
              <summary><span>Item (${{iIndex + 1}}): ${{escapeHtml(String(item.label || 'Question'))}}</span></summary>
              <div class="command-category-body" style="display:grid;padding:10px 14px 14px;">
                <div class="field-group" style="margin-bottom:8px;">
                  <div class="field-item">
                    <label>Label</label>
                    <input type="text" maxlength="45" data-vf-page data-vf-page-index="${{pIndex}}" data-vf-item-index="${{iIndex}}" data-vf-field="label" value="${{escapeHtml(String(item.label || ''))}}">
                  </div>
                  <div class="field-item">
                    <label>Description</label>
                    <input type="text" maxlength="45" data-vf-page data-vf-page-index="${{pIndex}}" data-vf-item-index="${{iIndex}}" data-vf-field="description" value="${{escapeHtml(String(item.description || ''))}}">
                  </div>
                </div>
                <div class="field-group" style="margin-bottom:0;">
                  <div class="field-item">
                    <label>Placeholder</label>
                    <input type="text" maxlength="45" data-vf-page data-vf-page-index="${{pIndex}}" data-vf-item-index="${{iIndex}}" data-vf-field="placeholder" value="${{escapeHtml(String(item.placeholder || ''))}}">
                  </div>
                  <div class="field-item">
                    <label>Input Type</label>
                    <select data-vf-page data-vf-page-index="${{pIndex}}" data-vf-item-index="${{iIndex}}" data-vf-field="input_type">
                      <option value="short" ${{item.input_type === 'short' ? 'selected' : ''}}>Short</option>
                      <option value="paragraph" ${{item.input_type === 'paragraph' ? 'selected' : ''}}>Paragraph</option>
                    </select>
                  </div>
                </div>
                <div style="margin-top:8px;">
                  <button type="button" class="danger-btn" data-vf-page="${{pIndex}}" data-vf-remove-item="${{iIndex}}">- Remove</button>
                </div>
              </div>
            </details>
          `)
          .join('');

        return `
          <details class="command-category" style="margin-bottom:10px;" ${{pIndex === 0 ? 'open' : ''}}>
            <summary><span data-vf-page-summary="${{pIndex}}">Page (${{pIndex + 1}}/${{verifyPlanLimits.maxPages}}): ${{escapeHtml(String(page.title || 'Verification Form'))}}</span></summary>
            <div class="command-category-body" style="display:grid;padding:10px 14px 14px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <button type="button" class="ghost-btn" data-vf-add-item="${{pIndex}}">+ Add Item</button>
              </div>
              <div class="field-item" style="margin-bottom:8px;">
                <label data-vf-page-title-label="${{pIndex}}">Title (${{String(page.title || '').length}} / ${{verifyPlanLimits.titleMaxLength}})</label>
                <input type="text" maxlength="${{verifyPlanLimits.titleMaxLength}}" data-vf-page data-vf-page-index="${{pIndex}}" data-vf-field="title" value="${{escapeHtml(String(page.title || ''))}}" placeholder="Verification Form">
              </div>
              ${{itemsHtml}}
            </div>
          </details>
        `;
      }})
      .join('');

    pagesJson.value = JSON.stringify(pages);
    bindEditorInputs();
    refreshPageCounters();

    if (addPageBtn) {{
      addPageBtn.disabled = pages.length >= verifyPlanLimits.maxPages;
      addPageBtn.title = addPageBtn.disabled ? `Page limit: ${{verifyPlanLimits.maxPages}}` : '';
    }}

    if (removePageBtn) {{
      removePageBtn.disabled = pages.length <= 1;
      removePageBtn.title = removePageBtn.disabled ? 'At least 1 page is required' : '';
    }}

    if (planLimitBadge) {{
      const pagesAtLimit = pages.length >= verifyPlanLimits.maxPages;
      const itemsAtLimit = pages.some((page) => (Array.isArray(page.items) ? page.items.length : 0) >= verifyPlanLimits.maxItemsPerPage);
      if (pagesAtLimit || itemsAtLimit) {{
        planLimitBadge.textContent = 'At Plan Limit';
        planLimitBadge.style.borderColor = 'rgba(248,113,113,.55)';
        planLimitBadge.style.color = '#ffb4c2';
      }} else {{
        planLimitBadge.textContent = 'Under Plan Limit';
        planLimitBadge.style.borderColor = 'rgba(74,222,128,.45)';
        planLimitBadge.style.color = '#9af5bb';
      }}
    }}

    renderPreview();
  }};

  addPageBtn?.addEventListener('click', () => {{
    if (pages.length >= verifyPlanLimits.maxPages) return;
    pages.push(defaultPage());
    renderPages();
  }});

  removePageBtn?.addEventListener('click', () => {{
    if (pages.length <= 1) return;
    pages.pop();
    renderPages();
  }});

  [
    buttonColorSelect,
    buttonLabelInput,
    buttonEmojiInput,
    embedTitleInput,
    embedFooterInput,
    embedThumbnailInput,
    embedImageInput,
    descInput,
    rewardRoleIdsInput,
    removeRoleIdsInput,
    ...webVerifyInputs,
  ].forEach((el) => {{
    el?.addEventListener('input', renderPreview);
    el?.addEventListener('change', renderPreview);
  }});

  ['tags_reward_role_ids', 'tags_remove_role_ids'].forEach((id) => {{
    const target = document.getElementById(id);
    if (!target) return;
    const observer = new MutationObserver(() => renderPreview());
    observer.observe(target, {{ childList: true, subtree: true }});
  }});

  if (dropzone && fileInput && fileName) {{
    const setFile = (file) => {{
      if (!file) return;
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      fileName.textContent = `File: ${{file.name}}`;
      if (webImageInput && !String(webImageInput.value || '').trim()) {{
        webImageInput.value = '';
      }}
      if (webPreviewImage) {{
        webPreviewImage.src = URL.createObjectURL(file);
        webPreviewImage.style.display = '';
      }}
    }};

    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {{
      const file = fileInput.files && fileInput.files[0];
      if (file) setFile(file);
    }});

    dropzone.addEventListener('dragover', (event) => {{
      event.preventDefault();
      dropzone.style.borderColor = 'rgba(107,140,255,.95)';
    }});

    dropzone.addEventListener('dragleave', () => {{
      dropzone.style.borderColor = 'rgba(255,110,199,.7)';
    }});

    dropzone.addEventListener('drop', (event) => {{
      event.preventDefault();
      dropzone.style.borderColor = 'rgba(255,110,199,.7)';
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) setFile(file);
    }});
  }}

  const activeView = () => {{
    const raw = String(verifyViewModeInput?.value || '').trim().toLowerCase();
    if (raw === 'web_verify' || raw === 'verify') return raw;
    const webVisible = !!(webVerifyPageSection && webVerifyPageSection.style.display !== 'none');
    return webVisible ? 'web_verify' : 'verify';
  }};

  form.addEventListener('submit', (event) => {{
    clampPages();
    pagesJson.value = JSON.stringify(pages);

    const view = activeView();
    if (verifyViewModeInput) verifyViewModeInput.value = view;

    if (view === 'verify') {{
      const buttonLabel = (buttonLabelInput?.value || '').trim();
      if (!buttonLabel) {{
        event.preventDefault();
        alert('Please enter Verify button label');
        return;
      }}

      const needAutoRole = (autoRoleEnabledSelect?.value || 'off') === 'on';
      const rewardRoles = String(rewardRoleIdsInput?.value || '').trim();
      if (needAutoRole && !rewardRoles) {{
        event.preventDefault();
        alert('Please select at least one reward role when Auto Role is enabled');
        return;
      }}
      return;
    }}

    const webLabel = String(webButtonLabelInput?.value || '').trim();
    if (!webLabel) {{
      event.preventDefault();
      alert('Please enter Web Verify button label');
      return;
    }}

    const needWebAutoRole = (webAutoRoleEnabledSelect?.value || 'off') === 'on';
    const webRewardRoles = String(webRewardRoleIdsInput?.value || '').trim();
    if (needWebAutoRole && !webRewardRoles) {{
      event.preventDefault();
      alert('Please select at least one reward role when Web Verify Auto Role is enabled');
    }}
  }});

  renderPages();
}})();
