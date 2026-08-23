(() => {{
  const form = document.getElementById('moderationSettingsForm');
  if (!form) return;

  const plan = String(form.dataset.plan || 'free');
  const rank = {{ free: 0, silver: 1, golden: 2, diamond: 3, permanent: 4 }};
  const saveBtn = form.querySelector('[data-save-btn="moderation"]');
  const hint = form.querySelector('#moderationPlanHint');
  const punishmentSelect = form.querySelector('select.punishment-select');

  const modeSelect = document.getElementById('automodModeSelect');
  const durationInput = form.querySelector('input[name="antispam_punishment_duration"]');

  const antilinkToggle = form.querySelector('input[name="antilink_enabled"]');
  const antispamToggle = form.querySelector('input[name="antispam_enabled"]');
  const antibadwordsToggle = form.querySelector('input[name="antibadwords_enabled"]');

  const previewMeta = document.getElementById('moderationPreviewMeta');
  const previewName = document.getElementById('moderationPreviewName');
  const previewServer = document.getElementById('moderationPreviewServer');
  const previewAvatar = document.getElementById('moderationPreviewAvatar');
  const previewPunishment = document.getElementById('moderationPreviewPunishment');
  const previewText = document.getElementById('moderationPreviewText');
  const previewTags = document.getElementById('moderationPreviewEnabledModules');

  const mockUserButtons = document.getElementById('moderationMockUserButtons');
  const mockServerButtons = document.getElementById('moderationMockServerButtons');

  const previewUser = {template_preview_user_name};
  const previewUserMention = {template_preview_user_mention};
  const previewServerName = {template_preview_server_name};
  const rawMockUsers = {moderation_mock_users_json};
  const rawMockServers = {moderation_mock_servers_json};

  const mockUsers = Array.isArray(rawMockUsers) ? rawMockUsers : [];
  const mockServers = Array.isArray(rawMockServers) ? rawMockServers : [];
  let activeMockUser = mockUsers[0] || null;
  let activeMockServer = mockServers[0] || null;

  const resolveUserName = () => String(activeMockUser?.name || previewUser || 'Member').trim() || 'Member';
  const resolveUserMention = () => String(activeMockUser?.mention || previewUserMention || `@${{resolveUserName()}}`).trim() || `@${{resolveUserName()}}`;
  const resolveUserAvatar = () => String(activeMockUser?.avatar || previewAvatar?.getAttribute('src') || 'https://cdn.discordapp.com/embed/avatars/0.png').trim();
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
        refreshPreview();
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
        refreshPreview();
      }},
    );
  }};

  const validate = () => {{
    if (!punishmentSelect) return true;
    const selected = punishmentSelect.options[punishmentSelect.selectedIndex];
    if (!selected) return true;
    const min = String(selected.dataset.minPlan || 'free');
    const ok = (rank[plan] ?? 0) >= (rank[min] ?? 0);
    if (saveBtn) saveBtn.disabled = !ok;
    if (hint) hint.style.display = ok ? 'none' : 'block';
    return ok;
  }};

  const enabledModules = () => {{
    const labels = [];
    if (antilinkToggle?.checked) labels.push('Anti-Link');
    if (antispamToggle?.checked) labels.push('Anti-Spam');
    if (antibadwordsToggle?.checked) labels.push('Anti-Badwords');
    return labels;
  }};

  const refreshPreview = () => {{
    const userName = resolveUserName();
    const userMention = resolveUserMention();
    const serverName = resolveServerName();
    const userAvatar = resolveUserAvatar();
    const selectedPunishment = punishmentSelect?.options[punishmentSelect.selectedIndex]?.textContent?.trim() || 'Mute';
    const durationMinutes = Math.max(0, Number(durationInput?.value || 0));
    const mode = String(modeSelect?.value || 'normal');
    const modules = enabledModules();

    if (previewName) previewName.textContent = userName;
    if (previewServer) previewServer.textContent = `in ${{serverName}}`;
    if (previewAvatar && userAvatar) {{
      previewAvatar.src = userAvatar;
      previewAvatar.alt = userName;
    }}
    if (previewPunishment) previewPunishment.textContent = selectedPunishment;
    if (previewMeta) previewMeta.textContent = `Mode: ${{mode}} • Enabled ${{modules.length}}/3`;

    if (previewText) {{
      const moduleText = modules.length ? modules.join(', ') : 'no module';
      const durationText = durationMinutes > 0 ? ` (${{durationMinutes}}m)` : '';
      previewText.textContent = `${{userMention}} triggered ${{moduleText}} in ${{serverName}}. Action: ${{selectedPunishment}}${{durationText}}.`;
    }}

    if (previewTags) {{
      previewTags.textContent = '';
      const source = modules.length ? modules : ['No modules enabled'];
      source.forEach((label) => {{
        const pill = document.createElement('span');
        pill.className = 'moderation-preview-tag';
        pill.textContent = label;
        previewTags.appendChild(pill);
      }});
    }}
  }};

  if (punishmentSelect) punishmentSelect.addEventListener('change', () => {{
    validate();
    refreshPreview();
  }});

  [modeSelect, durationInput, antilinkToggle, antispamToggle, antibadwordsToggle].forEach((el) => el?.addEventListener('input', refreshPreview));
  [modeSelect, durationInput, antilinkToggle, antispamToggle, antibadwordsToggle].forEach((el) => el?.addEventListener('change', refreshPreview));

  form.addEventListener('submit', (event) => {{
    if (!validate()) {{
      event.preventDefault();
      alert('แพ็กเกจปัจจุบันยังไม่รองรับระดับนี้');
    }}
  }});

  redrawMockSwitchers();
  validate();
  refreshPreview();
}})();
