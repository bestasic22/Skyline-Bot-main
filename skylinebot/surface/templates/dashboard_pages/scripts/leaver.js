(() => {{
  const form = document.getElementById('leaverSettingsForm');
  if (!form) return;

  const textInput = document.getElementById('leaveMessageInput');
  const enableToggle = document.getElementById('leaveEnableToggle');
  const messageToggle = form.querySelector('input[name="leave_message_enabled"]');
  const embedToggle = form.querySelector('input[name="leave_embed"]');
  const imageToggle = form.querySelector('input[name="leave_image"]');

  const previewCard = document.getElementById('leavePreviewCard');
  const previewText = document.getElementById('leavePreviewText');
  const previewModes = document.getElementById('leavePreviewModes');

  const imageThemeInput = form.querySelector('select[name="leave_image_theme"]');
  const imageThemeUrlInput = form.querySelector('input[name="leave_image_theme_url"]');
  const imageLayoutInput = form.querySelector('select[name="leave_image_layout_mode"]');
  const imageAvatarPosInput = form.querySelector('select[name="leave_image_avatar_position"]');
  const imageTextAlignInput = form.querySelector('select[name="leave_image_text_align"]');
  const imageFontStyleInput = form.querySelector('select[name="leave_image_font_style"]');
  const imageTopInput = form.querySelector('input[name="leave_image_top_text"]');
  const imageBottomInput = form.querySelector('input[name="leave_image_bottom_text"]');

  const cardPreview = document.getElementById('leaveImageCardPreview');
  const cardLayout = document.getElementById('leaveImageCardLayout');
  const cardAvatar = document.getElementById('leaveImageCardAvatar');
  const cardTextWrap = document.getElementById('leaveImageCardTextWrap');
  const cardTop = document.getElementById('leaveImageCardTop');
  const cardBottom = document.getElementById('leaveImageCardBottom');
  const cardMeta = document.getElementById('leaveImageCardMeta');
  const previewMemberName = document.getElementById('leavePreviewMemberName');
  const previewMemberAvatar = document.getElementById('leavePreviewMemberAvatar');
  const mockUserButtons = document.getElementById('leaveMockUserButtons');
  const mockServerButtons = document.getElementById('leaveMockServerButtons');

  const themePresets = {leave_theme_presets_json};
  const previewUser = {template_preview_user_name};
  const previewUserMention = {template_preview_user_mention};
  const previewServer = {template_preview_server_name};
  const rawMockUsers = {mock_preview_users_json};
  const rawMockServers = {mock_preview_servers_json};

  const mockUsers = Array.isArray(rawMockUsers) ? rawMockUsers : [];
  const mockServers = Array.isArray(rawMockServers) ? rawMockServers : [];
  let activeMockUser = mockUsers[0] || null;
  let activeMockServer = mockServers[0] || null;

  const resolveUserName = () => String(activeMockUser?.name || previewUser || 'Member').trim() || 'Member';
  const resolveUserMention = () => String(activeMockUser?.mention || previewUserMention || `@${{resolveUserName()}}`).trim() || `@${{resolveUserName()}}`;
  const resolveUserAvatar = () =>
    String(
      activeMockUser?.avatar
      || previewMemberAvatar?.getAttribute('src')
      || cardAvatar?.getAttribute('src')
      || 'https://cdn.discordapp.com/embed/avatars/0.png'
    ).trim();
  const resolveServerName = () => String(activeMockServer?.name || previewServer || 'Guild').trim() || 'Guild';
  const resolveServerIcon = () =>
    String(
      activeMockServer?.icon
      || activeMockServer?.avatar
      || themePresets.guild
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

  const replaceTokens = (raw) => {{
    let value = String(raw || '');
    const lb = String.fromCharCode(123);
    const rb = String.fromCharCode(125);
    const token = (name) => lb + name + rb;
    const token2 = (name) => lb + lb + name + rb + rb;

    const currentUserName = resolveUserName();
    const currentUserMention = resolveUserMention();
    const currentServer = resolveServerName();
    const swaps = [
      [token2('user.mention'), currentUserMention],
      [token2('user'), currentUserName],
      [token2('server'), currentServer],
      [token2('guild'), currentServer],
      [token('user.mention'), currentUserMention],
      [token('user'), currentUserName],
      [token('server'), currentServer],
      [token('guild'), currentServer],
    ];

    swaps.forEach(([from, to]) => {{
      value = value.split(from).join(to);
    }});
    return value;
  }};

  const resolveThemeUrl = () => {{
    const key = String(imageThemeInput?.value || 'security').toLowerCase();
    const custom = String(imageThemeUrlInput?.value || '').trim();
    if (key === 'custom') return custom;
    if (key === 'user') return resolveUserAvatar();
    if (key === 'guild') return resolveServerIcon();
    return String(themePresets[key] || themePresets.security || themePresets.music || '').trim();
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

  const applyCardFontStyle = () => {{
    const fontStyle = String(imageFontStyleInput?.value || 'classic').toLowerCase();
    const family = previewFontFamily(fontStyle);
    if (cardTop) cardTop.style.fontFamily = family;
    if (cardBottom) cardBottom.style.fontFamily = family;
  }};

  const applyCardLayout = () => {{
    if (!(cardLayout instanceof HTMLElement)) return;
    const mode = String(imageLayoutInput?.value || 'center_stack').toLowerCase();
    const avatarPos = String(imageAvatarPosInput?.value || 'center').toLowerCase();
    const align = String(imageTextAlignInput?.value || 'center').toLowerCase();

    cardLayout.style.display = 'flex';
    cardLayout.style.gap = '12px';
    cardLayout.style.alignItems = 'center';

    if (mode === 'left_avatar') {{
      cardLayout.style.flexDirection = 'row';
      cardLayout.style.justifyContent = 'space-between';
    }} else if (mode === 'right_avatar') {{
      cardLayout.style.flexDirection = 'row-reverse';
      cardLayout.style.justifyContent = 'space-between';
    }} else {{
      cardLayout.style.flexDirection = 'column';
      cardLayout.style.justifyContent = 'center';
    }}

    if (cardTextWrap instanceof HTMLElement) {{
      cardTextWrap.style.display = 'grid';
      cardTextWrap.style.gap = '6px';
      cardTextWrap.style.textAlign = align === 'left' || align === 'right' ? align : 'center';
      cardTextWrap.style.alignItems = align === 'left' ? 'flex-start' : (align === 'right' ? 'flex-end' : 'center');
    }}

    if (cardAvatar instanceof HTMLElement) {{
      if (mode === 'center_stack') {{
        cardAvatar.style.alignSelf = avatarPos === 'left' ? 'flex-start' : (avatarPos === 'right' ? 'flex-end' : 'center');
      }} else {{
        cardAvatar.style.alignSelf = 'center';
      }}
    }}
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
        refresh();
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
        refresh();
      }},
    );
  }};

  const refreshImageCard = () => {{
    if (!(cardPreview instanceof HTMLElement)) return;
    const bgUrl = resolveThemeUrl();
    const userAvatar = resolveUserAvatar();
    cardPreview.style.backgroundImage = bgUrl ? `url("${{bgUrl}}")` : 'none';
    cardPreview.style.backgroundSize = 'cover';
    cardPreview.style.backgroundPosition = 'center';

    if (cardAvatar && userAvatar) {{
      cardAvatar.src = userAvatar;
      cardAvatar.alt = resolveUserName();
    }}
    if (cardTop) cardTop.textContent = replaceTokens(imageTopInput?.value || '{{user}}');
    if (cardBottom) cardBottom.textContent = replaceTokens(imageBottomInput?.value || 'ออกจาก {{server}} แล้ว');
    if (cardMeta) {{
      const themeKey = String(imageThemeInput?.value || 'security');
      const fontStyle = String(imageFontStyleInput?.value || 'classic');
      cardMeta.textContent = bgUrl
        ? `Theme: ${{themeKey}} | Font: ${{fontStyle}} | Mock: ${{resolveUserName()}} in ${{resolveServerName()}}`
        : `Theme: ${{themeKey}} | Font: ${{fontStyle}} (missing URL)`;
    }}
    applyCardFontStyle();
    applyCardLayout();
  }};

  const refresh = () => {{
    const modes = [];
    const userName = resolveUserName();
    const userAvatar = resolveUserAvatar();
    if (messageToggle?.checked) modes.push('ข้อความ');
    if (embedToggle?.checked) modes.push('Embed');
    if (imageToggle?.checked) modes.push('รูปภาพ');
    if (previewModes) previewModes.textContent = `โหมดที่เปิด: ${{modes.length ? modes.join(' + ') : 'ไม่มี'}}`;

    if (previewMemberName) previewMemberName.textContent = userName;
    if (previewMemberAvatar && userAvatar) {{
      previewMemberAvatar.src = userAvatar;
      previewMemberAvatar.alt = userName;
    }}
    if (previewText) previewText.textContent = replaceTokens((textInput?.value || '{{user.mention}} ออกจาก {{server}} แล้ว')).slice(0, 600);
    if (previewCard) previewCard.style.opacity = enableToggle?.checked ? '1' : '.45';
    refreshImageCard();
  }};

  textInput?.addEventListener('input', refresh);
  enableToggle?.addEventListener('change', refresh);
  messageToggle?.addEventListener('change', refresh);
  embedToggle?.addEventListener('change', refresh);
  imageToggle?.addEventListener('change', refresh);

  imageThemeInput?.addEventListener('change', refreshImageCard);
  imageThemeUrlInput?.addEventListener('input', refreshImageCard);
  imageLayoutInput?.addEventListener('change', refreshImageCard);
  imageAvatarPosInput?.addEventListener('change', refreshImageCard);
  imageTextAlignInput?.addEventListener('change', refreshImageCard);
  imageFontStyleInput?.addEventListener('change', refreshImageCard);
  imageTopInput?.addEventListener('input', refreshImageCard);
  imageBottomInput?.addEventListener('input', refreshImageCard);
  redrawMockSwitchers();
  refresh();
}})();
