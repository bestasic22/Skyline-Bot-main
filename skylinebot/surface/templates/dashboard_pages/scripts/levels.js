(() => {{
  const form = document.getElementById('levelsSettingsForm');
  if (!form) return;

  const textToggle = form.querySelector('input[name="notify_send_text"]');
  const embedToggle = form.querySelector('input[name="notify_send_embed"]');
  const imageToggle = form.querySelector('input[name="notify_send_image"]');

  const messageInput = form.querySelector('textarea[name="notify_message"]');
  const embedTitleInput = form.querySelector('input[name="notify_embed_title"]');
  const embedDescInput = form.querySelector('input[name="notify_embed_description"]');

  const imageTopInput = form.querySelector('input[name="notify_image_top_text"]');
  const imageBottomInput = form.querySelector('input[name="notify_image_bottom_text"]');
  const imageThemeInput = form.querySelector('select[name="notify_image_theme"]');
  const imageThemeUrlInput = form.querySelector('input[name="notify_image_theme_url"]');
  const imageLayoutInput = form.querySelector('select[name="notify_image_layout_mode"]');
  const imageAvatarPosInput = form.querySelector('select[name="notify_image_avatar_position"]');
  const imageTextAlignInput = form.querySelector('select[name="notify_image_text_align"]');
  const imageFontStyleInput = form.querySelector('select[name="notify_image_font_style"]');

  const modeView = document.getElementById('levelNotifyPreviewModes');
  const textView = document.getElementById('levelNotifyTextPreview');
  const embedView = document.getElementById('levelNotifyEmbedPreview');
  const embedTitleView = document.getElementById('levelNotifyEmbedTitlePreview');
  const embedDescView = document.getElementById('levelNotifyEmbedDescriptionPreview');

  const imageView = document.getElementById('levelNotifyImagePreview');
  const imageLayoutView = document.getElementById('levelNotifyImageLayout');
  const imageAvatarView = document.getElementById('levelNotifyImageAvatar');
  const imageTextWrapView = document.getElementById('levelNotifyImageTextWrap');
  const imageTopView = document.getElementById('levelNotifyImageTopPreview');
  const imageBottomView = document.getElementById('levelNotifyImageBottomPreview');
  const imageThemeView = document.getElementById('levelNotifyImageThemePreview');

  const mockUserButtons = document.getElementById('levelMockUserButtons');
  const mockServerButtons = document.getElementById('levelMockServerButtons');

  const imageThemeMap = {level_image_theme_presets_json};
  const templatePreviewUser = {template_preview_user};
  const templatePreviewGuild = {template_preview_guild};
  const rawMockUsers = {levels_mock_users_json};
  const rawMockServers = {levels_mock_servers_json};

  const mockUsers = Array.isArray(rawMockUsers) ? rawMockUsers : [];
  const mockServers = Array.isArray(rawMockServers) ? rawMockServers : [];
  let activeMockUser = mockUsers[0] || null;
  let activeMockServer = mockServers[0] || null;

  const resolveUserMention = () => String(activeMockUser?.mention || templatePreviewUser || '@Member').trim() || '@Member';
  const resolveUserName = () => {{
    const preferred = String(activeMockUser?.name || '').trim();
    if (preferred) return preferred;
    const mention = resolveUserMention().replace(/^@/, '').trim();
    return mention || 'Member';
  }};
  const resolveUserAvatar = () =>
    String(
      activeMockUser?.avatar
      || imageAvatarView?.getAttribute('src')
      || 'https://cdn.discordapp.com/embed/avatars/0.png'
    ).trim();
  const resolveServerName = () => String(activeMockServer?.name || templatePreviewGuild || 'Guild').trim() || 'Guild';
  const resolveServerIcon = () =>
    String(
      activeMockServer?.icon
      || activeMockServer?.avatar
      || imageThemeMap.guild
      || 'https://cdn.discordapp.com/embed/avatars/0.png'
    ).trim();

  const renderMockButtons = (host, items, activeId, onPick) => {{
    if (!(host instanceof HTMLElement)) return;
    host.textContent = '';
    items.forEach((item, idx) => {{
      const button = document.createElement('button');
      button.type = 'button';
      const itemId = String(item?.id || idx);
      button.className = `ghost-btn mock-toggle-btn${{itemId === String(activeId || '') ? ' is-active' : ''}}`;
      button.textContent = String(item?.label || item?.name || itemId);
      button.addEventListener('click', () => onPick(itemId));
      host.appendChild(button);
    }});
  }};

  const redrawMockSwitchers = () => {{
    renderMockButtons(
      mockUserButtons,
      mockUsers,
      activeMockUser?.id || '',
      (itemId) => {{
        const nextUser = mockUsers.find((item) => String(item?.id || '') === String(itemId));
        if (!nextUser) return;
        activeMockUser = nextUser;
        redrawMockSwitchers();
        syncLevelPreview();
      }},
    );
    renderMockButtons(
      mockServerButtons,
      mockServers,
      activeMockServer?.id || '',
      (itemId) => {{
        const nextServer = mockServers.find((item) => String(item?.id || '') === String(itemId));
        if (!nextServer) return;
        activeMockServer = nextServer;
        redrawMockSwitchers();
        syncLevelPreview();
      }},
    );
  }};

  const applyVars = (raw) => {{
    let value = String(raw || '');
    const lb = String.fromCharCode(123);
    const rb = String.fromCharCode(125);
    const token = (name) => lb + name + rb;
    const token2 = (name) => lb + lb + name + rb + rb;

    const currentUserName = resolveUserName();
    const currentUserMention = resolveUserMention();
    const currentServer = resolveServerName();
    const swaps = [
      [token2('user'), currentUserName],
      [token2('user.mention'), currentUserMention],
      [token2('level'), '42'],
      [token2('xp'), '12345'],
      [token2('server'), currentServer],
      [token2('guild'), currentServer],
      [token('user'), currentUserName],
      [token('user.mention'), currentUserMention],
      [token('level'), '42'],
      [token('xp'), '12345'],
      [token('server'), currentServer],
      [token('guild'), currentServer],
    ];

    swaps.forEach(([from, to]) => {{
      value = value.split(from).join(String(to));
    }});
    return value;
  }};

  const resolveImageThemeUrl = () => {{
    const key = String(imageThemeInput?.value || 'music').toLowerCase();
    const custom = String(imageThemeUrlInput?.value || '').trim();
    if (key === 'custom') return custom;
    if (key === 'user') return resolveUserAvatar();
    if (key === 'guild') return resolveServerIcon();
    return String(imageThemeMap[key] || imageThemeMap.music || '').trim();
  }};

  const previewFontFamily = (styleKey) => {{
    const key = String(styleKey || 'classic').toLowerCase();
    const map = {{
      classic: '"SkylineCardClassic","SkylineCardClassicBold","Segoe UI",sans-serif',
      clean: '"SkylineCardClean","Segoe UI",sans-serif',
      impact: '"SkylineCardImpact","Arial Black","Arial",sans-serif',
      soft: '"SkylineCardSoft","Segoe Print","Arial",sans-serif',
    }};
    return `${{map[key] || map.classic}},"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji","Noto Emoji",sans-serif`;
  }};

  const applyImageFontStyle = () => {{
    const fontStyle = String(imageFontStyleInput?.value || 'classic').toLowerCase();
    const family = previewFontFamily(fontStyle);
    if (imageTopView) imageTopView.style.fontFamily = family;
    if (imageBottomView) imageBottomView.style.fontFamily = family;
  }};

  const applyImageLayout = () => {{
    if (!(imageLayoutView instanceof HTMLElement)) return;
    const mode = String(imageLayoutInput?.value || 'center_stack').toLowerCase();
    const avatarPos = String(imageAvatarPosInput?.value || 'center').toLowerCase();
    const align = String(imageTextAlignInput?.value || 'center').toLowerCase();

    imageLayoutView.style.display = 'flex';
    imageLayoutView.style.gap = '12px';
    imageLayoutView.style.alignItems = 'center';

    if (mode === 'left_avatar') {{
      imageLayoutView.style.flexDirection = 'row';
      imageLayoutView.style.justifyContent = 'space-between';
    }} else if (mode === 'right_avatar') {{
      imageLayoutView.style.flexDirection = 'row-reverse';
      imageLayoutView.style.justifyContent = 'space-between';
    }} else {{
      imageLayoutView.style.flexDirection = 'column';
      imageLayoutView.style.justifyContent = 'center';
    }}

    if (imageTextWrapView instanceof HTMLElement) {{
      imageTextWrapView.style.display = 'grid';
      imageTextWrapView.style.gap = '6px';
      imageTextWrapView.style.textAlign = align === 'left' || align === 'right' ? align : 'center';
      imageTextWrapView.style.alignItems = align === 'left' ? 'flex-start' : (align === 'right' ? 'flex-end' : 'center');
    }}

    if (imageAvatarView instanceof HTMLElement) {{
      if (mode === 'center_stack') {{
        imageAvatarView.style.alignSelf = avatarPos === 'left' ? 'flex-start' : (avatarPos === 'right' ? 'flex-end' : 'center');
      }} else {{
        imageAvatarView.style.alignSelf = 'center';
      }}
    }}
  }};

  const syncLevelPreview = () => {{
    const modes = [];
    if (textToggle?.checked) modes.push('ข้อความ');
    if (embedToggle?.checked) modes.push('Embed');
    if (imageToggle?.checked) modes.push('รูปภาพ');
    if (modeView) modeView.textContent = `โหมดที่เปิด: ${{modes.length ? modes.join(' + ') : 'ไม่มี (ระบบจะเปิดข้อความอัตโนมัติเมื่อบันทึก)'}}`;

    if (textView) {{
      textView.style.display = textToggle?.checked ? '' : 'none';
      textView.textContent = applyVars(messageInput?.value || '🎉 {{user}} อัปเลเวลเป็น {{level}} (XP {{xp}})');
    }}

    if (embedView) embedView.style.display = embedToggle?.checked ? '' : 'none';
    if (embedTitleView) embedTitleView.textContent = applyVars(embedTitleInput?.value || 'Level up!');
    if (embedDescView) embedDescView.textContent = applyVars(embedDescInput?.value || '{{user.mention}} reached level {{level}} (XP {{xp}})');

    if (imageView) {{
      imageView.style.display = imageToggle?.checked ? '' : 'none';
      const bgUrl = resolveImageThemeUrl();
      imageView.style.backgroundImage = bgUrl ? `url("${{bgUrl}}")` : 'none';
      imageView.style.backgroundSize = 'cover';
      imageView.style.backgroundPosition = 'center';

      const avatarUrl = resolveUserAvatar();
      if (imageAvatarView && avatarUrl) {{
        imageAvatarView.src = avatarUrl;
        imageAvatarView.alt = resolveUserName();
      }}

      if (imageThemeView) {{
        const key = String(imageThemeInput?.value || 'music');
        const fontStyle = String(imageFontStyleInput?.value || 'classic');
        imageThemeView.textContent = bgUrl
          ? `Theme: ${{key}} | Font: ${{fontStyle}} | Mock: ${{resolveUserName()}} in ${{resolveServerName()}}`
          : `Theme: ${{key}} | Font: ${{fontStyle}} (missing URL)`;
      }}
      applyImageFontStyle();
      applyImageLayout();
    }}

    if (imageTopView) imageTopView.textContent = applyVars(imageTopInput?.value || '{{user}}');
    if (imageBottomView) imageBottomView.textContent = applyVars(imageBottomInput?.value || 'Level {{level}}');
  }};

  [textToggle, embedToggle, imageToggle].forEach((el) => el?.addEventListener('change', syncLevelPreview));
  [
    messageInput,
    embedTitleInput,
    embedDescInput,
    imageTopInput,
    imageBottomInput,
    imageThemeInput,
    imageThemeUrlInput,
    imageLayoutInput,
    imageAvatarPosInput,
    imageTextAlignInput,
    imageFontStyleInput,
  ].forEach((el) => el?.addEventListener('input', syncLevelPreview));
  [imageThemeInput, imageLayoutInput, imageAvatarPosInput, imageTextAlignInput, imageFontStyleInput].forEach((el) => el?.addEventListener('change', syncLevelPreview));

  redrawMockSwitchers();
  syncLevelPreview();

  const resetSearchInput = document.getElementById('levelResetSearchInput');
  const resetTargetSelect = document.getElementById('levelResetTargetSelect');
  const resetAllForm = document.getElementById('levelResetAllForm');

  const filterResetTargets = () => {{
    if (!(resetTargetSelect instanceof HTMLSelectElement)) return;
    const query = String((resetSearchInput instanceof HTMLInputElement ? resetSearchInput.value : '') || '').trim().toLowerCase();
    let firstVisible = null;
    Array.from(resetTargetSelect.options).forEach((option) => {{
      const src = String(option.getAttribute('data-search') || option.textContent || '').toLowerCase();
      const visible = !query || src.includes(query);
      option.hidden = !visible;
      if (visible && !firstVisible) firstVisible = option;
    }});
    const selected = resetTargetSelect.options[resetTargetSelect.selectedIndex];
    if (!selected || selected.hidden) {{
      if (firstVisible) resetTargetSelect.value = firstVisible.value;
    }}
  }};

  resetSearchInput?.addEventListener('input', filterResetTargets);
  filterResetTargets();

  resetAllForm?.addEventListener('submit', (ev) => {{
    const ok = window.confirm('ยืนยันรีเซ็ตเลเวลสมาชิกทั้งหมดในกิลด์นี้?');
    if (!ok) ev.preventDefault();
  }});
}})();
