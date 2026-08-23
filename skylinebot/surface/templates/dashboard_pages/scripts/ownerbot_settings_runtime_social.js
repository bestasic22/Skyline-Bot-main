(() => {
  const socialRowsWrap = document.getElementById('ownerbotSocialRows');
  const socialHidden = document.getElementById('ownerbotSocialHidden');
  const addSocialRowButton = document.getElementById('ownerbotAddSocialRow');
  const runtimeForm = document.getElementById('ownerbotRuntimeForm');

  if (!(socialRowsWrap instanceof HTMLElement) || !(socialHidden instanceof HTMLInputElement)) {
    return;
  }

  const seedSocialRows = {social_rows_json};
  const socialPlatformKeys = {social_platform_keys_json};
  const socialPlatformLabels = {social_platform_labels_json};
  const socialPlatformIcons = {social_platform_icons_json};
  const DEFAULT_SOCIAL_KEY = '__default__';

  const normalize = (value) => String(value || '').trim();
  const isValidDeveloperId = (value) => /^\d{15,22}$/.test(String(value || '').trim());

  const normalizeUrl = (value) => {
    const text = normalize(value);
    if (!text) {
      return '';
    }
    if (/^https?:\/\//i.test(text)) {
      return text;
    }
    return `https://${text}`;
  };

  const isValidHttpUrl = (value) => {
    const text = normalizeUrl(value);
    if (!text) {
      return false;
    }
    try {
      const parsed = new URL(text);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch (_error) {
      return false;
    }
  };

  const getDefaultIcon = (platform) => {
    const key = normalize(platform).toLowerCase();
    return normalize((socialPlatformIcons || {})[key]) || 'link';
  };

  const getPlatformLabel = (platform) => {
    const key = normalize(platform).toLowerCase();
    return normalize((socialPlatformLabels || {})[key]) || key || 'platform';
  };

  const createFieldLabel = (title, inputNode) => {
    const label = document.createElement('label');
    label.style.display = 'grid';
    label.style.gap = '6px';
    label.textContent = title;
    label.appendChild(inputNode);
    return label;
  };

  const renderEmptyState = () => {
    const hasRows = socialRowsWrap.querySelector('[data-social-row]');
    let emptyNode = socialRowsWrap.querySelector('[data-social-empty]');
    if (hasRows) {
      if (emptyNode) {
        emptyNode.remove();
      }
      return;
    }
    if (!emptyNode) {
      emptyNode = document.createElement('div');
      emptyNode.className = 'ownerbot-empty';
      emptyNode.setAttribute('data-social-empty', '1');
      emptyNode.textContent = 'ยังไม่มีรายการ กด + เพิ่มลิงก์โซเชียล';
      socialRowsWrap.appendChild(emptyNode);
    }
  };

  const syncHidden = () => {
    const payload = {};
    const rows = Array.from(socialRowsWrap.querySelectorAll('[data-social-row]'));

    rows.forEach((row) => {
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const devIdInput = row.querySelector('[data-field="dev_id"]');
      const platformSelect = row.querySelector('[data-field="platform"]');
      const urlInput = row.querySelector('[data-field="url"]');
      const iconInput = row.querySelector('[data-field="icon"]');

      if (!(platformSelect instanceof HTMLSelectElement) || !(urlInput instanceof HTMLInputElement)) {
        return;
      }

      const platform = normalize(platformSelect.value).toLowerCase();
      const normalizedUrl = normalizeUrl(urlInput.value);
      const iconName = normalize(iconInput instanceof HTMLInputElement ? iconInput.value : '') || getDefaultIcon(platform);
      const devId = normalize(devIdInput instanceof HTMLInputElement ? devIdInput.value : '');
      if (!platform || !normalizedUrl) {
        return;
      }

      const ownerKey = devId || DEFAULT_SOCIAL_KEY;
      if (!payload[ownerKey] || typeof payload[ownerKey] !== 'object') {
        payload[ownerKey] = {};
      }
      payload[ownerKey][platform] = {
        url: normalizedUrl,
        icon: iconName,
      };
    });

    socialHidden.value = JSON.stringify(payload);
  };

  const validateRow = (row) => {
    if (!(row instanceof HTMLElement)) {
      return true;
    }
    const devIdInput = row.querySelector('[data-field="dev_id"]');
    const urlInput = row.querySelector('[data-field="url"]');
    const statusNode = row.querySelector('[data-field="status"]');

    const devId = normalize(devIdInput instanceof HTMLInputElement ? devIdInput.value : '');
    const rawUrl = normalize(urlInput instanceof HTMLInputElement ? urlInput.value : '');

    if (!rawUrl && !devId) {
      if (statusNode instanceof HTMLElement) {
        statusNode.className = 'ownerbot-social-url-status muted';
        statusNode.textContent = 'กรอก URL แล้วระบบจะตรวจให้อัตโนมัติ';
      }
      return true;
    }

    if (devId && !isValidDeveloperId(devId)) {
      if (statusNode instanceof HTMLElement) {
        statusNode.className = 'ownerbot-social-url-status error';
        statusNode.textContent = 'Discord User ID ต้องเป็นตัวเลข 15-22 หลัก';
      }
      return false;
    }

    if (!rawUrl || !isValidHttpUrl(rawUrl)) {
      if (statusNode instanceof HTMLElement) {
        statusNode.className = 'ownerbot-social-url-status error';
        statusNode.textContent = 'URL ต้องเป็นรูปแบบ http(s) ที่ถูกต้อง';
      }
      return false;
    }

    if (urlInput instanceof HTMLInputElement) {
      urlInput.value = normalizeUrl(rawUrl);
    }

    if (statusNode instanceof HTMLElement) {
      statusNode.className = 'ownerbot-social-url-status ok';
      statusNode.textContent = devId
        ? `พร้อมบันทึกสำหรับ owner ${devId}`
        : 'พร้อมบันทึกเป็นค่า default owner';
    }
    return true;
  };

  const createRow = (seed = {}) => {
    const row = document.createElement('article');
    row.className = 'ownerbot-social-row';
    row.setAttribute('data-social-row', '1');

    const cardHead = document.createElement('div');
    cardHead.className = 'ownerbot-social-row-head';
    const title = document.createElement('strong');
    title.textContent = 'Social Link';
    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'ghost-btn';
    removeButton.textContent = 'ลบ';
    cardHead.appendChild(title);
    cardHead.appendChild(removeButton);

    const devIdInput = document.createElement('input');
    devIdInput.type = 'text';
    devIdInput.placeholder = 'Discord User ID (optional)';
    devIdInput.maxLength = 22;
    devIdInput.value = normalize(seed.dev_id);
    devIdInput.setAttribute('data-field', 'dev_id');

    const platformSelect = document.createElement('select');
    platformSelect.setAttribute('data-field', 'platform');
    const platformOptions = Array.isArray(socialPlatformKeys)
      ? socialPlatformKeys
      : ['discord', 'profile'];
    platformOptions.forEach((key) => {
      const option = document.createElement('option');
      option.value = String(key || '');
      option.textContent = getPlatformLabel(key);
      platformSelect.appendChild(option);
    });
    const seededPlatform = normalize(seed.platform).toLowerCase();
    if (seededPlatform) {
      platformSelect.value = seededPlatform;
    }

    const urlInput = document.createElement('input');
    urlInput.type = 'text';
    urlInput.placeholder = 'https://example.com/your-profile';
    urlInput.value = normalize(seed.url);
    urlInput.setAttribute('data-field', 'url');

    const iconInput = document.createElement('input');
    iconInput.type = 'text';
    iconInput.placeholder = 'icon id (optional)';
    iconInput.value = normalize(seed.icon) || getDefaultIcon(platformSelect.value);
    iconInput.setAttribute('data-field', 'icon');

    const status = document.createElement('small');
    status.className = 'ownerbot-social-url-status muted';
    status.setAttribute('data-field', 'status');
    status.textContent = 'กรอก URL แล้วระบบจะตรวจให้อัตโนมัติ';

    const fieldGrid = document.createElement('div');
    fieldGrid.className = 'field-grid';
    fieldGrid.style.gridTemplateColumns = 'repeat(auto-fit,minmax(210px,1fr))';
    fieldGrid.style.gap = '10px';
    fieldGrid.appendChild(createFieldLabel('Discord User ID', devIdInput));
    fieldGrid.appendChild(createFieldLabel('Platform', platformSelect));
    fieldGrid.appendChild(createFieldLabel('URL', urlInput));
    fieldGrid.appendChild(createFieldLabel('Icon', iconInput));

    row.appendChild(cardHead);
    row.appendChild(fieldGrid);
    row.appendChild(status);

    const handleChange = () => {
      if (!normalize(iconInput.value)) {
        iconInput.value = getDefaultIcon(platformSelect.value);
      }
      validateRow(row);
      syncHidden();
    };

    [devIdInput, platformSelect, urlInput, iconInput].forEach((node) => {
      node.addEventListener('input', handleChange);
      node.addEventListener('change', handleChange);
    });

    removeButton.addEventListener('click', () => {
      row.remove();
      renderEmptyState();
      syncHidden();
    });

    validateRow(row);
    return row;
  };

  const addRow = (seed = {}) => {
    const emptyNode = socialRowsWrap.querySelector('[data-social-empty]');
    if (emptyNode) {
      emptyNode.remove();
    }
    socialRowsWrap.appendChild(createRow(seed));
    renderEmptyState();
    syncHidden();
  };

  if (Array.isArray(seedSocialRows) && seedSocialRows.length) {
    seedSocialRows.forEach((row) => addRow(row || {}));
  } else {
    renderEmptyState();
    syncHidden();
  }

  if (addSocialRowButton instanceof HTMLButtonElement) {
    addSocialRowButton.addEventListener('click', () => {
      addRow({ platform: 'discord' });
    });
  }

  if (runtimeForm instanceof HTMLFormElement) {
    runtimeForm.addEventListener('submit', (event) => {
      const rows = Array.from(socialRowsWrap.querySelectorAll('[data-social-row]'));
      let invalidFound = false;
      rows.forEach((row) => {
        if (!validateRow(row)) {
          invalidFound = true;
        }
      });
      if (invalidFound) {
        event.preventDefault();
        alert('ยังมีลิงก์โซเชียลที่ไม่ถูกต้อง กรุณาตรวจสอบก่อนบันทึก');
        return;
      }
      syncHidden();
    });
  }
})();
