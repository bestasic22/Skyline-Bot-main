(() => {{
  const titleInput = document.getElementById('ticketPanelTitleInput');
  const panelInput = document.getElementById('ticketPanelTextInput');
  const closeInput = document.getElementById('ticketCloseTextInput');
  const panelImageInput = document.getElementById('ticketPanelImageUrlInput');
  const panelButtonLabelInput = document.getElementById('ticketPanelButtonLabelInput');
  const panelButtonColorSelect = document.getElementById('ticketPanelButtonColorSelect');
  const panelButtonEmojiInput = document.getElementById('ticketPanelButtonEmojiInput');

  const panelTitle = document.getElementById('ticketPanelPreviewTitle');
  const panelContext = document.getElementById('ticketPanelPreviewContext');
  const panelText = document.getElementById('ticketPanelPreviewText');
  const panelImage = document.getElementById('ticketPanelPreviewImage');
  const panelButton = document.getElementById('ticketPanelPreviewButton');
  const closeContext = document.getElementById('ticketClosePreviewContext');
  const closeText = document.getElementById('ticketClosePreviewText');
  const previewMeta = document.getElementById('ticketPreviewMeta');
  const colorMap = {{
    green: '#25c26e',
    blurple: '#5865f2',
    red: '#e14343',
    gray: '#6b7280',
  }};

  const statusFilter = document.getElementById('ticketHistoryStatusFilter');
  const searchInput = document.getElementById('ticketHistorySearchInput');
  const historyRows = Array.from(document.querySelectorAll('tr[data-ticket-id]'));

  const mockUserButtons = document.getElementById('ticketMockUserButtons');
  const mockServerButtons = document.getElementById('ticketMockServerButtons');

  const previewUser = {template_preview_user_name};
  const previewUserMention = {template_preview_user_mention};
  const previewServerName = {template_preview_server_name};
  const rawMockUsers = {ticket_mock_users_json};
  const rawMockServers = {ticket_mock_servers_json};

  const mockUsers = Array.isArray(rawMockUsers) ? rawMockUsers : [];
  const mockServers = Array.isArray(rawMockServers) ? rawMockServers : [];
  let activeMockUser = mockUsers[0] || null;
  let activeMockServer = mockServers[0] || null;

  const resolveUserName = () => String(activeMockUser?.name || previewUser || 'Member').trim() || 'Member';
  const resolveUserMention = () => String(activeMockUser?.mention || previewUserMention || `@${{resolveUserName()}}`).trim() || `@${{resolveUserName()}}`;
  const resolveServerName = () => String(activeMockServer?.name || previewServerName || 'Guild').trim() || 'Guild';

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
        syncPreview();
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
        syncPreview();
      }},
    );
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

  const syncPreview = () => {{
    const userName = resolveUserName();
    const serverName = resolveServerName();
    if (panelTitle) panelTitle.textContent = (titleInput?.value || 'Open a support ticket').slice(0, 120);
    if (panelText) panelText.textContent = replaceTokens((panelInput?.value || 'Support team is ready to help.')).slice(0, 800);
    if (panelButton) {{
      const buttonLabel = String(panelButtonLabelInput?.value || 'Open Ticket').trim().slice(0, 45) || 'Open Ticket';
      const buttonEmoji = String(panelButtonEmojiInput?.value || '').trim().slice(0, 64);
      const buttonColor = String(panelButtonColorSelect?.value || 'blurple').trim().toLowerCase();
      panelButton.style.background = colorMap[buttonColor] || colorMap.blurple;
      panelButton.textContent = `${{buttonEmoji ? `${{buttonEmoji}} ` : ''}}${{buttonLabel}}`;
    }}
    if (panelImage) {{
      const imageUrl = String(panelImageInput?.value || '').trim();
      panelImage.src = imageUrl;
      panelImage.style.display = imageUrl ? '' : 'none';
    }}
    if (closeText) closeText.textContent = replaceTokens((closeInput?.value || 'Your ticket has been closed.')).slice(0, 800);
    if (panelContext) panelContext.textContent = `${{userName}} in ${{serverName}}`;
    if (closeContext) closeContext.textContent = `${{userName}} in ${{serverName}}`;
    if (previewMeta) previewMeta.textContent = `Previewing: ${{userName}} in ${{serverName}}`;
  }};

  const filterHistory = () => {{
    const mode = String(statusFilter?.value || 'all');
    const q = String(searchInput?.value || '').trim().replace('#', '');
    historyRows.forEach((row) => {{
      const status = String(row.dataset.ticketStatus || 'open');
      const ticketId = String(row.dataset.ticketId || '');
      const passStatus = mode === 'all' || mode === status;
      const passSearch = !q || ticketId.includes(q);
      row.style.display = (passStatus && passSearch) ? '' : 'none';
    }});
  }};

  titleInput?.addEventListener('input', syncPreview);
  panelInput?.addEventListener('input', syncPreview);
  panelImageInput?.addEventListener('input', syncPreview);
  panelImageInput?.addEventListener('change', syncPreview);
  panelButtonLabelInput?.addEventListener('input', syncPreview);
  panelButtonColorSelect?.addEventListener('change', syncPreview);
  panelButtonEmojiInput?.addEventListener('input', syncPreview);
  closeInput?.addEventListener('input', syncPreview);
  statusFilter?.addEventListener('change', filterHistory);
  searchInput?.addEventListener('input', filterHistory);

  redrawMockSwitchers();
  syncPreview();
  filterHistory();
}})();
