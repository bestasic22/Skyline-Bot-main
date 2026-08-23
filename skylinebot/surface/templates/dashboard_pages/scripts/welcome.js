(() => {{
  const form = document.getElementById('welcomeSettingsForm');
  if (!form) return;

  const textInput = document.getElementById('welcomeMessageInput');
  const messageToggle = form.querySelector('input[name="welcome_message"]');
  const embedToggle = document.getElementById('welcomeEmbedToggle');
  const imageToggle = form.querySelector('input[name="welcome_image"]');
  const previewCard = document.getElementById('welcomePreviewCard');
  const previewText = document.getElementById('welcomePreviewText');
  const previewModes = document.getElementById('welcomePreviewModes');
  const previewEmbedImage = document.getElementById('welcomePreviewEmbedImage');

  const imageUrlInput = document.getElementById('welcomeEmbedImageInput');
  const imageFileInput = document.getElementById('welcomeEmbedImageFileInput');
  const imageDropzone = document.getElementById('welcomeEmbedImageDropzone');
  const imageFileName = document.getElementById('welcomeEmbedImageFileName');
  const imagePreviewWrap = document.getElementById('welcomeEmbedImagePreviewWrap');
  const imagePreview = document.getElementById('welcomeEmbedImagePreview');

  const imageThemeInput = form.querySelector('select[name="welcome_image_theme"]');
  const imageThemeUrlInput = form.querySelector('input[name="welcome_image_theme_url"]');
  const imageLayoutInput = form.querySelector('select[name="welcome_image_layout_mode"]');
  const imageAvatarPosInput = form.querySelector('select[name="welcome_image_avatar_position"]');
  const imageTextAlignInput = form.querySelector('select[name="welcome_image_text_align"]');
  const imageFontStyleInput = form.querySelector('select[name="welcome_image_font_style"]');
  const imageTopInput = form.querySelector('input[name="welcome_image_top_text"]');
  const imageBottomInput = form.querySelector('input[name="welcome_image_bottom_text"]');

  const cardPreview = document.getElementById('welcomeImageCardPreview');
  const cardLayout = document.getElementById('welcomeImageCardLayout');
  const cardAvatar = document.getElementById('welcomeImageCardAvatar');
  const cardTextWrap = document.getElementById('welcomeImageCardTextWrap');
  const cardTop = document.getElementById('welcomeImageCardTop');
  const cardBottom = document.getElementById('welcomeImageCardBottom');
  const cardMeta = document.getElementById('welcomeImageCardMeta');
  const previewMemberName = document.getElementById('welcomePreviewMemberName');
  const previewMemberAvatar = document.getElementById('welcomePreviewMemberAvatar');
  const mockUserButtons = document.getElementById('welcomeMockUserButtons');
  const mockServerButtons = document.getElementById('welcomeMockServerButtons');
  const welcomeChannelInput = form.querySelector('[name="welcome_channel"]');

  const themePresets = {welcome_theme_presets_json};
  const previewUser = {template_preview_user_name};
  const previewUserMention = {template_preview_user_mention};
  const previewServer = {template_preview_server_name};
  const previewUserId = {template_preview_user_id};
  const previewServerId = {template_preview_server_id};
  const previewMemberCount = {template_preview_member_count};
  const previewInviterName = 'InviteMaster';
  const previewInviterMention = '@InviteMaster';
  const previewInviterId = '100000000000000099';
  const previewInviterCount = '12';
  const previewInviteCode = 'welcome123';
  const previewInviteLink = 'https://discord.gg/welcome123';
  const rawMockUsers = {mock_preview_users_json};
  const rawMockServers = {mock_preview_servers_json};

  const mockUsers = Array.isArray(rawMockUsers) ? rawMockUsers : [];
  const mockServers = Array.isArray(rawMockServers) ? rawMockServers : [];
  let activeMockUser = mockUsers[0] || null;
  let activeMockServer = mockServers[0] || null;

  const resolveUserName = () => String(activeMockUser?.name || previewUser || 'Member').trim() || 'Member';
  const resolveUserMention = () => String(activeMockUser?.mention || previewUserMention || `@${{resolveUserName()}}`).trim() || `@${{resolveUserName()}}`;
  const resolveUserId = () => String(activeMockUser?.user_id || previewUserId || '100000000000000001').trim() || '100000000000000001';
  const resolveUserAvatar = () =>
    String(
      activeMockUser?.avatar
      || previewMemberAvatar?.getAttribute('src')
      || cardAvatar?.getAttribute('src')
      || 'https://cdn.discordapp.com/embed/avatars/0.png'
    ).trim();
  const resolveServerName = () => String(activeMockServer?.name || previewServer || 'Guild').trim() || 'Guild';
  const resolveServerId = () => String(activeMockServer?.guild_id || previewServerId || '100000000000000002').trim() || '100000000000000002';
  const resolveMemberCount = () => {{
    const raw = String(activeMockServer?.member_count || previewMemberCount || '117').trim();
    return /^\d+$/.test(raw) ? raw : '117';
  }};
  const resolveChannelId = () => {{
    const raw = String(welcomeChannelInput?.value || '').trim();
    return /^\d+$/.test(raw) ? raw : '';
  }};
  const resolveChannelMention = () => {{
    const channelId = resolveChannelId();
    return channelId ? `<#${{channelId}}>` : '#welcome-channel';
  }};
  const resolveChannelName = () => {{
    const label = String(welcomeChannelInput?.selectedOptions?.[0]?.text || '').trim();
    if (!label) return 'welcome-channel';
    return label.replace(/^#/, '');
  }};
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

  const setImagePreview = (url) => {{
    const clean = String(url || '').trim();
    if (imagePreview) imagePreview.src = clean;
    if (imagePreviewWrap) imagePreviewWrap.style.display = clean ? '' : 'none';
    if (previewEmbedImage) {{
      previewEmbedImage.src = clean;
      previewEmbedImage.style.display = clean ? '' : 'none';
    }}
  }};

  const replaceTokens = (raw) => {{
    let value = String(raw || '');
    const lb = String.fromCharCode(123);
    const rb = String.fromCharCode(125);
    const token = (name) => lb + name + rb;
    const token2 = (name) => lb + lb + name + rb + rb;

    const currentUserName = resolveUserName();
    const currentUserMention = resolveUserMention();
    const currentUserId = resolveUserId();
    const currentServer = resolveServerName();
    const currentServerId = resolveServerId();
    const currentMemberCount = resolveMemberCount();
    const currentChannelId = resolveChannelId();
    const currentChannelMention = resolveChannelMention();
    const currentChannelName = resolveChannelName();
    const currentInviterName = previewInviterName;
    const currentInviterMention = previewInviterMention;
    const currentInviterId = previewInviterId;
    const currentInviterCount = previewInviterCount;
    const currentInviteCode = previewInviteCode;
    const currentInviteLink = previewInviteLink;
    const currentTime = `${{new Date().toLocaleString('en-GB', {{ hour12: false }})}} UTC`;
    const swaps = [
      [token2('user.id'), currentUserId],
      [token2('user.mention'), currentUserMention],
      [token2('user'), currentUserName],
      [token2('server.id'), currentServerId],
      [token2('server'), currentServer],
      [token2('guild.id'), currentServerId],
      [token2('guild'), currentServer],
      [token2('member.count'), currentMemberCount],
      [token2('channel.id'), currentChannelId],
      [token2('channel.name'), currentChannelName],
      [token2('channel.mention'), currentChannelMention],
      [token2('channel'), currentChannelMention],
      [token2('welcome.channel.id'), currentChannelId],
      [token2('welcome.channel.mention'), currentChannelMention],
      [token2('welcome.channel'), currentChannelMention],
      [token2('room.id'), currentChannelId],
      [token2('room'), currentChannelMention],
      [token2('inviter'), currentInviterName],
      [token2('inviter.id'), currentInviterId],
      [token2('inviter.mention'), currentInviterMention],
      [token2('inviter.count'), currentInviterCount],
      [token2('invite.code'), currentInviteCode],
      [token2('invite.link'), currentInviteLink],
      [token2('invite.url'), currentInviteLink],
      [token2('time'), currentTime],
      [token('user.id'), currentUserId],
      [token('user.mention'), currentUserMention],
      [token('user'), currentUserName],
      [token('server.id'), currentServerId],
      [token('server'), currentServer],
      [token('guild.id'), currentServerId],
      [token('guild'), currentServer],
      [token('member.count'), currentMemberCount],
      [token('channel.id'), currentChannelId],
      [token('channel.name'), currentChannelName],
      [token('channel.mention'), currentChannelMention],
      [token('channel'), currentChannelMention],
      [token('welcome.channel.id'), currentChannelId],
      [token('welcome.channel.mention'), currentChannelMention],
      [token('welcome.channel'), currentChannelMention],
      [token('room.id'), currentChannelId],
      [token('room'), currentChannelMention],
      [token('inviter'), currentInviterName],
      [token('inviter.id'), currentInviterId],
      [token('inviter.mention'), currentInviterMention],
      [token('inviter.count'), currentInviterCount],
      [token('invite.code'), currentInviteCode],
      [token('invite.link'), currentInviteLink],
      [token('invite.url'), currentInviteLink],
      [token('time'), currentTime],
    ];

    swaps.forEach(([from, to]) => {{
      value = value.split(from).join(to);
    }});
    return value;
  }};

  const resolveThemeUrl = () => {{
    const key = String(imageThemeInput?.value || 'music').toLowerCase();
    const custom = String(imageThemeUrlInput?.value || '').trim();
    if (key === 'custom') return custom;
    if (key === 'user') return resolveUserAvatar();
    if (key === 'guild') return resolveServerIcon();
    return String(themePresets[key] || themePresets.music || '').trim();
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
    if (cardBottom) cardBottom.textContent = replaceTokens(imageBottomInput?.value || 'Welcome to {{server}}');
    if (cardMeta) {{
      const themeKey = String(imageThemeInput?.value || 'music');
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
    const renderedText = replaceTokens(textInput?.value || 'ยินดีต้อนรับ {{user.mention}} สู่ {{server}}');
    if (messageToggle?.checked) modes.push('ข้อความ');
    if (embedToggle?.checked) modes.push('Embed');
    if (imageToggle?.checked) modes.push('รูปภาพ');
    if (previewModes) previewModes.textContent = `โหมดที่เปิด: ${{modes.length ? modes.join(' + ') : 'ไม่มี'}}`;

    if (previewMemberName) previewMemberName.textContent = userName;
    if (previewMemberAvatar && userAvatar) {{
      previewMemberAvatar.src = userAvatar;
      previewMemberAvatar.alt = userName;
    }}
    if (previewText) previewText.textContent = renderedText.slice(0, 600);
    if (previewCard) previewCard.style.display = embedToggle?.checked ? 'block' : 'none';
    if (imageUrlInput) setImagePreview(imageUrlInput.value);
    refreshImageCard();
  }};

  imageDropzone?.addEventListener('click', () => imageFileInput?.click());
  imageFileInput?.addEventListener('change', () => {{
    const file = imageFileInput.files && imageFileInput.files[0];
    if (!file) return;
    if (imageFileName) imageFileName.textContent = file.name;
    const blobUrl = URL.createObjectURL(file);
    setImagePreview(blobUrl);
  }});
  imageDropzone?.addEventListener('dragover', (event) => {{
    event.preventDefault();
  }});
  imageDropzone?.addEventListener('drop', (event) => {{
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    if (imageFileInput) {{
      const dt = new DataTransfer();
      dt.items.add(file);
      imageFileInput.files = dt.files;
    }}
    if (imageFileName) imageFileName.textContent = file.name;
    const blobUrl = URL.createObjectURL(file);
    setImagePreview(blobUrl);
  }});

  imageUrlInput?.addEventListener('input', () => setImagePreview(imageUrlInput.value));
  imageThemeInput?.addEventListener('change', refreshImageCard);
  imageThemeUrlInput?.addEventListener('input', refreshImageCard);
  imageLayoutInput?.addEventListener('change', refreshImageCard);
  imageAvatarPosInput?.addEventListener('change', refreshImageCard);
  imageTextAlignInput?.addEventListener('change', refreshImageCard);
  imageFontStyleInput?.addEventListener('change', refreshImageCard);
  imageTopInput?.addEventListener('input', refreshImageCard);
  imageBottomInput?.addEventListener('input', refreshImageCard);

  textInput?.addEventListener('input', refresh);
  welcomeChannelInput?.addEventListener('change', refresh);
  messageToggle?.addEventListener('change', refresh);
  embedToggle?.addEventListener('change', refresh);
  imageToggle?.addEventListener('change', refresh);
  redrawMockSwitchers();
  refresh();
}})();
