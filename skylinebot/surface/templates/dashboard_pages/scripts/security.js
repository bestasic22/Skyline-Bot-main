(() => {{
  const form = document.getElementById('securitySettingsForm');
  if (!form) return;

  const plan = String(form.dataset.plan || 'free');
  const rank = {{ free: 0, silver: 1, golden: 2, diamond: 3, permanent: 4 }};
  const saveBtn = form.querySelector('[data-save-btn="security"]');
  const hint = form.querySelector('#securityPlanHint');
  const punishmentSelects = form.querySelectorAll('select.punishment-select');

  const modeSelect = document.getElementById('antinukeModeSelect');

  const previewMeta = document.getElementById('securityPreviewMeta');
  const previewName = document.getElementById('securityPreviewName');
  const previewServer = document.getElementById('securityPreviewServer');
  const previewAvatar = document.getElementById('securityPreviewAvatar');
  const previewMode = document.getElementById('securityPreviewMode');
  const previewText = document.getElementById('securityPreviewText');
  const previewTags = document.getElementById('securityPreviewEnabledModules');

  const mockUserButtons = document.getElementById('securityMockUserButtons');
  const mockServerButtons = document.getElementById('securityMockServerButtons');

  const previewUser = {template_preview_user_name};
  const previewUserMention = {template_preview_user_mention};
  const previewServerName = {template_preview_server_name};
  const rawMockUsers = {security_mock_users_json};
  const rawMockServers = {security_mock_servers_json};

  const mockUsers = Array.isArray(rawMockUsers) ? rawMockUsers : [];
  const mockServers = Array.isArray(rawMockServers) ? rawMockServers : [];
  let activeMockUser = mockUsers[0] || null;
  let activeMockServer = mockServers[0] || null;

  const resolveUserName = () => String(activeMockUser?.name || previewUser || 'Member').trim() || 'Member';
  const resolveUserMention = () => String(activeMockUser?.mention || previewUserMention || `@${{resolveUserName()}}`).trim() || `@${{resolveUserName()}}`;
  const resolveUserAvatar = () => String(activeMockUser?.avatar || previewAvatar?.getAttribute('src') || 'https://cdn.discordapp.com/embed/avatars/0.png').trim();
  const resolveServerName = () => String(activeMockServer?.name || previewServerName || 'Guild').trim() || 'Guild';

  const moduleDescriptors = [
    {{
      toggle: 'anti_bot_add',
      label: 'Bot Add',
      punishment: 'anti_bot_add_punishment',
      limit: 'anti_bot_add_limit',
    }},
    {{
      toggle: 'anti_channel_delete',
      label: 'Channel Delete',
      punishment: 'anti_channel_delete_punishment',
      limit: 'anti_channel_delete_limit',
    }},
    {{
      toggle: 'anti_role_delete',
      label: 'Role Delete',
      punishment: 'anti_role_delete_punishment',
      limit: 'anti_role_delete_limit',
    }},
    {{
      toggle: 'anti_webhook_create',
      label: 'Webhook Create',
      punishment: 'anti_webhook_create_punishment',
      limit: 'anti_webhook_create_limit',
    }},
    {{
      toggle: 'anti_everyone_mention',
      label: '@everyone Mention',
      punishment: 'anti_everyone_mention_punishment',
      limit: 'anti_everyone_mention_limit',
    }},
  ];

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
    let blocked = false;
    punishmentSelects.forEach((select) => {{
      const selected = select.options[select.selectedIndex];
      if (!selected) return;
      const min = String(selected.dataset.minPlan || 'free');
      if ((rank[plan] ?? 0) < (rank[min] ?? 0)) blocked = true;
    }});
    if (saveBtn) saveBtn.disabled = blocked;
    if (hint) hint.style.display = blocked ? 'block' : 'none';
    return !blocked;
  }};

  const enabledSecurityModules = () => {{
    const modules = [];
    moduleDescriptors.forEach((desc) => {{
      const toggle = form.querySelector(`input[name="${{desc.toggle}}"]`);
      if (!toggle?.checked) return;
      const punishmentSelect = form.querySelector(`select[name="${{desc.punishment}}"]`);
      const punishment = punishmentSelect?.options[punishmentSelect.selectedIndex]?.textContent?.trim() || 'Mute';
      const limitInput = form.querySelector(`input[name="${{desc.limit}}"]`);
      const limit = Math.max(1, Number(limitInput?.value || 1));
      modules.push({{ label: desc.label, punishment, limit }});
    }});
    return modules;
  }};

  const refreshPreview = () => {{
    const userName = resolveUserName();
    const userMention = resolveUserMention();
    const serverName = resolveServerName();
    const userAvatar = resolveUserAvatar();
    const mode = String(modeSelect?.value || 'normal');
    const antiNukeEnabled = !!form.querySelector('input[name="enabled"]')?.checked;
    const modules = enabledSecurityModules();

    if (previewName) previewName.textContent = userName;
    if (previewServer) previewServer.textContent = `in ${{serverName}}`;
    if (previewAvatar && userAvatar) {{
      previewAvatar.src = userAvatar;
      previewAvatar.alt = userName;
    }}
    if (previewMode) previewMode.textContent = mode;
    if (previewMeta) previewMeta.textContent = `Mode: ${{mode}} • Enabled ${{modules.length}}/5`;

    if (previewText) {{
      if (!antiNukeEnabled) {{
        previewText.textContent = `Security system is disabled in ${{serverName}}.`;
      }} else if (!modules.length) {{
        previewText.textContent = `Security monitor is active for ${{serverName}} with no extra module toggles.`;
      }} else {{
        const first = modules[0];
        previewText.textContent = `${{userMention}} exceeded ${{first.label}} limit (${{first.limit}}) in ${{serverName}}. Action: ${{first.punishment}}.`;
      }}
    }}

    if (previewTags) {{
      previewTags.textContent = '';
      const source = modules.length ? modules : [{{ label: 'No modules enabled', punishment: '-', limit: 0 }}];
      source.forEach((module) => {{
        const tag = document.createElement('span');
        tag.className = 'security-preview-tag';
        if (module.limit > 0) {{
          tag.textContent = `${{module.label}} • ${{module.punishment}} • limit ${{module.limit}}`;
        }} else {{
          tag.textContent = module.label;
        }}
        previewTags.appendChild(tag);
      }});
    }}
  }};

  punishmentSelects.forEach((select) => select.addEventListener('change', () => {{
    validate();
    refreshPreview();
  }}));

  form.addEventListener('submit', (event) => {{
    if (!validate()) {{
      event.preventDefault();
      alert('แพ็กเกจปัจจุบันยังไม่รองรับระดับนี้');
    }}
  }});

  const watchInputs = [modeSelect, ...Array.from(form.querySelectorAll('input[type="checkbox"], input[type="number"]'))];
  watchInputs.forEach((el) => el?.addEventListener('change', refreshPreview));
  watchInputs.forEach((el) => el?.addEventListener('input', refreshPreview));

  redrawMockSwitchers();
  validate();
  refreshPreview();

  const botProfileForm = document.getElementById('botProfileSettingsForm');
  if (botProfileForm) {{
    const actionInput = botProfileForm.querySelector('#botProfileActionInput');
    const actionButtons = Array.from(botProfileForm.querySelectorAll('[data-profile-action]'));
    const nicknameInput = botProfileForm.querySelector('input[name="bot_nickname"]');
    const avatarInput = botProfileForm.querySelector('input[name="bot_avatar_file"]');
    const submitButton = botProfileForm.querySelector('#botProfileSubmitButton');

    const previewToAvatar = document.getElementById('botProfilePreviewToAvatar');
    const previewToDisplay = document.getElementById('botProfilePreviewToDisplay');
    const previewToNick = document.getElementById('botProfilePreviewToNick');
    const previewMetaBot = document.getElementById('botProfilePreviewMeta');
    const previewFileLabel = document.getElementById('botProfilePreviewFileLabel');

    const confirmModal = document.getElementById('botProfileConfirmModal');
    const confirmTitle = document.getElementById('botProfileConfirmTitle');
    const confirmFromAvatar = document.getElementById('botProfileConfirmFromAvatar');
    const confirmFromDisplay = document.getElementById('botProfileConfirmFromDisplay');
    const confirmFromNick = document.getElementById('botProfileConfirmFromNick');
    const confirmToAvatar = document.getElementById('botProfileConfirmToAvatar');
    const confirmToDisplay = document.getElementById('botProfileConfirmToDisplay');
    const confirmToNick = document.getElementById('botProfileConfirmToNick');
    const confirmActionText = document.getElementById('botProfileConfirmActionText');
    const confirmFileText = document.getElementById('botProfileConfirmFileText');
    const confirmCancelBtn = document.getElementById('botProfileConfirmCancelBtn');
    const confirmSubmitBtn = document.getElementById('botProfileConfirmSubmitBtn');

    const currentAvatar = String(botProfileForm.dataset.currentAvatar || '').trim();
    const defaultAvatar = String(botProfileForm.dataset.defaultAvatar || currentAvatar).trim() || currentAvatar;
    const currentNick = String(botProfileForm.dataset.currentNick || '\u0e22\u0e31\u0e07\u0e44\u0e21\u0e48\u0e15\u0e31\u0e49\u0e07').trim() || '\u0e22\u0e31\u0e07\u0e44\u0e21\u0e48\u0e15\u0e31\u0e49\u0e07';
    const defaultNick = String(botProfileForm.dataset.defaultNick || currentNick).trim() || currentNick;
    const currentDisplay = String(botProfileForm.dataset.currentDisplay || currentNick).trim() || currentNick;
    const defaultDisplay = String(botProfileForm.dataset.defaultDisplay || defaultNick).trim() || defaultNick;

    const initialNicknameDisabled = !!nicknameInput?.disabled;
    const initialAvatarDisabled = !!avatarInput?.disabled;

    let selectedAvatarUrl = '';
    let allowDirectSubmit = false;
    let confirmModalOpen = false;
    let lastFocusBeforeModal = null;
    let previewState = {{
      action: 'save',
      actionLabel: '',
      fromAvatar: currentAvatar || defaultAvatar,
      fromDisplay: currentDisplay,
      fromNick: currentNick,
      toAvatar: currentAvatar || defaultAvatar,
      toDisplay: currentDisplay,
      toNick: currentNick,
      fileText: '',
    }};

    const actionLabels = {{
      save: '\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01\u0e0a\u0e37\u0e48\u0e2d/\u0e23\u0e39\u0e1b\u0e43\u0e2b\u0e21\u0e48',
      reset_nickname: '\u0e23\u0e35\u0e40\u0e0b\u0e47\u0e15\u0e0a\u0e37\u0e48\u0e2d\u0e40\u0e25\u0e48\u0e19\u0e1a\u0e2d\u0e17\u0e01\u0e25\u0e31\u0e1a\u0e04\u0e48\u0e32\u0e40\u0e14\u0e34\u0e21',
      reset_avatar: '\u0e23\u0e35\u0e40\u0e0b\u0e47\u0e15\u0e23\u0e39\u0e1b\u0e42\u0e1b\u0e23\u0e44\u0e1f\u0e25\u0e4c\u0e40\u0e09\u0e1e\u0e32\u0e30\u0e01\u0e34\u0e25\u0e14\u0e4c',
    }};
    const submitLabels = {{
      save: '\u0e22\u0e37\u0e19\u0e22\u0e31\u0e19\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01\u0e0a\u0e37\u0e48\u0e2d/\u0e23\u0e39\u0e1b\u0e43\u0e2b\u0e21\u0e48',
      reset_nickname: '\u0e22\u0e37\u0e19\u0e22\u0e31\u0e19\u0e23\u0e35\u0e40\u0e0b\u0e47\u0e15\u0e0a\u0e37\u0e48\u0e2d\u0e40\u0e25\u0e48\u0e19\u0e1a\u0e2d\u0e17',
      reset_avatar: '\u0e22\u0e37\u0e19\u0e22\u0e31\u0e19\u0e23\u0e35\u0e40\u0e0b\u0e47\u0e15\u0e23\u0e39\u0e1b\u0e42\u0e1b\u0e23\u0e44\u0e1f\u0e25\u0e4c\u0e1a\u0e2d\u0e17',
    }};

    const resolveAction = () => {{
      const action = String(actionInput?.value || 'save').trim().toLowerCase();
      if (action === 'reset_nickname' || action === 'reset_avatar') return action;
      return 'save';
    }};

    const setAction = (nextAction) => {{
      if (!actionInput) return;
      const action = String(nextAction || 'save').trim().toLowerCase();
      actionInput.value = (action === 'reset_nickname' || action === 'reset_avatar') ? action : 'save';
      renderBotProfilePreview();
    }};

    const renderActionButtons = () => {{
      const active = resolveAction();
      actionButtons.forEach((button) => {{
        const value = String(button.getAttribute('data-profile-action') || '').trim().toLowerCase();
        button.classList.toggle('is-active', value === active);
      }});
    }};

    const closeConfirmModal = () => {{
      if (!(confirmModal instanceof HTMLElement)) return;
      confirmModalOpen = false;
      confirmModal.style.display = 'none';
      confirmModal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
      if (lastFocusBeforeModal instanceof HTMLElement) {{
        lastFocusBeforeModal.focus();
      }}
    }};

    const openConfirmModal = () => {{
      if (!(confirmModal instanceof HTMLElement)) return;
      renderBotProfilePreview();
      const action = previewState.action;
      const submitLabel = submitLabels[action] || submitLabels.save;
      const actionLabel = previewState.actionLabel || actionLabels[action] || actionLabels.save;

      if (confirmTitle) confirmTitle.textContent = '\u0e22\u0e37\u0e19\u0e22\u0e31\u0e19\u0e01\u0e48\u0e2d\u0e19\u0e2a\u0e48\u0e07\u0e08\u0e23\u0e34\u0e07';

      if (confirmFromAvatar) {{
        confirmFromAvatar.src = previewState.fromAvatar || currentAvatar || defaultAvatar;
        confirmFromAvatar.alt = previewState.fromDisplay || currentDisplay;
      }}
      if (confirmFromDisplay) confirmFromDisplay.textContent = previewState.fromDisplay || currentDisplay;
      if (confirmFromNick) confirmFromNick.textContent = `\u0e0a\u0e37\u0e48\u0e2d\u0e40\u0e25\u0e48\u0e19\u0e43\u0e19\u0e40\u0e0b\u0e34\u0e23\u0e4c\u0e1f: ${{previewState.fromNick || currentNick}}`;

      if (confirmToAvatar) {{
        confirmToAvatar.src = previewState.toAvatar || currentAvatar || defaultAvatar;
        confirmToAvatar.alt = previewState.toDisplay || currentDisplay;
      }}
      if (confirmToDisplay) confirmToDisplay.textContent = previewState.toDisplay || currentDisplay;
      if (confirmToNick) confirmToNick.textContent = `\u0e0a\u0e37\u0e48\u0e2d\u0e40\u0e25\u0e48\u0e19\u0e43\u0e19\u0e40\u0e0b\u0e34\u0e23\u0e4c\u0e1f: ${{previewState.toNick || currentNick}}`;

      if (confirmActionText) confirmActionText.textContent = `\u0e42\u0e2b\u0e21\u0e14: ${{actionLabel}}`;
      if (confirmFileText) confirmFileText.textContent = previewState.fileText || '';
      if (confirmSubmitBtn) confirmSubmitBtn.textContent = submitLabel;

      lastFocusBeforeModal = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      confirmModal.style.display = 'flex';
      confirmModal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      confirmModalOpen = true;
      if (confirmSubmitBtn instanceof HTMLElement) confirmSubmitBtn.focus();
    }};

    const buildPreviewState = () => {{
      const action = resolveAction();
      const typedNick = String(nicknameInput?.value || '').trim();

      let targetNick = currentNick;
      let targetDisplay = currentDisplay;
      let targetAvatar = currentAvatar;

      if (action === 'save') {{
        if (typedNick) {{
          targetNick = typedNick;
          targetDisplay = typedNick;
        }}
        if (selectedAvatarUrl) targetAvatar = selectedAvatarUrl;
      }} else if (action === 'reset_nickname') {{
        targetNick = defaultNick;
        targetDisplay = defaultDisplay;
      }} else if (action === 'reset_avatar') {{
        targetAvatar = defaultAvatar;
      }}

      let fileText = '';
      if (action === 'save' && avatarInput?.files?.[0]) {{
        const file = avatarInput.files[0];
        fileText = `\u0e23\u0e39\u0e1b\u0e17\u0e35\u0e48\u0e40\u0e25\u0e37\u0e2d\u0e01: ${{file.name}} (${{Math.max(1, Math.round(file.size / 1024))}} KB)`;
      }} else if (action === 'reset_avatar') {{
        fileText = '\u0e1e\u0e23\u0e35\u0e27\u0e34\u0e27\u0e23\u0e39\u0e1b\u0e14\u0e49\u0e32\u0e19\u0e02\u0e27\u0e32\u0e40\u0e1b\u0e47\u0e19\u0e23\u0e39\u0e1b\u0e42\u0e1b\u0e23\u0e44\u0e1f\u0e25\u0e4c\u0e04\u0e48\u0e32\u0e40\u0e23\u0e34\u0e48\u0e21\u0e15\u0e49\u0e19\u0e02\u0e2d\u0e07\u0e1a\u0e2d\u0e17';
      }} else if (action === 'reset_nickname') {{
        fileText = `\u0e1e\u0e23\u0e35\u0e27\u0e34\u0e27\u0e0a\u0e37\u0e48\u0e2d\u0e14\u0e49\u0e32\u0e19\u0e02\u0e27\u0e32\u0e08\u0e30\u0e23\u0e35\u0e40\u0e0b\u0e47\u0e15\u0e01\u0e25\u0e31\u0e1a\u0e40\u0e1b\u0e47\u0e19: ${{defaultNick}}`;
      }}

      return {{
        action,
        actionLabel: actionLabels[action] || actionLabels.save,
        fromAvatar: currentAvatar || defaultAvatar,
        fromDisplay: currentDisplay,
        fromNick: currentNick,
        toAvatar: targetAvatar || currentAvatar || defaultAvatar,
        toDisplay: targetDisplay,
        toNick: targetNick,
        fileText,
      }};
    }};

    const renderBotProfilePreview = () => {{
      previewState = buildPreviewState();
      const action = previewState.action;

      if (previewToAvatar) {{
        previewToAvatar.src = previewState.toAvatar || currentAvatar || defaultAvatar;
        previewToAvatar.alt = previewState.toDisplay || currentDisplay;
      }}
      if (previewToDisplay) previewToDisplay.textContent = previewState.toDisplay || currentDisplay;
      if (previewToNick) previewToNick.textContent = `\u0e0a\u0e37\u0e48\u0e2d\u0e40\u0e25\u0e48\u0e19\u0e43\u0e19\u0e40\u0e0b\u0e34\u0e23\u0e4c\u0e1f: ${{previewState.toNick || currentNick}}`;
      if (previewMetaBot) previewMetaBot.textContent = `\u0e42\u0e2b\u0e21\u0e14: ${{previewState.actionLabel || actionLabels.save}}`;
      if (submitButton) submitButton.textContent = submitLabels[action] || submitLabels.save;

      if (nicknameInput) nicknameInput.disabled = initialNicknameDisabled || action !== 'save';
      if (avatarInput) avatarInput.disabled = initialAvatarDisabled || action !== 'save';
      if (previewFileLabel) previewFileLabel.textContent = previewState.fileText || '';

      renderActionButtons();
    }};

    actionButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        if (button.disabled) return;
        const next = String(button.getAttribute('data-profile-action') || 'save');
        setAction(next);
      }});
    }});

    nicknameInput?.addEventListener('input', renderBotProfilePreview);
    nicknameInput?.addEventListener('change', renderBotProfilePreview);
    avatarInput?.addEventListener('change', () => {{
      if (selectedAvatarUrl) {{
        URL.revokeObjectURL(selectedAvatarUrl);
        selectedAvatarUrl = '';
      }}
      const file = avatarInput.files?.[0];
      if (file) selectedAvatarUrl = URL.createObjectURL(file);
      renderBotProfilePreview();
    }});

    botProfileForm.addEventListener('submit', (event) => {{
      if (!actionInput || !actionInput.value) actionInput.value = 'save';
      if (allowDirectSubmit) {{
        allowDirectSubmit = false;
        return;
      }}
      event.preventDefault();
      if (submitButton?.disabled) return;
      if (confirmModal instanceof HTMLElement) {{
        openConfirmModal();
        return;
      }}
      allowDirectSubmit = true;
      if (typeof botProfileForm.requestSubmit === 'function') {{
        botProfileForm.requestSubmit();
      }} else {{
        botProfileForm.submit();
      }}
    }});

    confirmCancelBtn?.addEventListener('click', closeConfirmModal);
    confirmSubmitBtn?.addEventListener('click', () => {{
      if (confirmSubmitBtn?.disabled) return;
      closeConfirmModal();
      allowDirectSubmit = true;
      if (typeof botProfileForm.requestSubmit === 'function') {{
        botProfileForm.requestSubmit();
      }} else {{
        botProfileForm.submit();
      }}
    }});

    confirmModal?.addEventListener('click', (event) => {{
      if (event.target === confirmModal) {{
        closeConfirmModal();
      }}
    }});

    document.addEventListener('keydown', (event) => {{
      if (!confirmModalOpen) return;
      if (String(event.key || '').toLowerCase() !== 'escape') return;
      event.preventDefault();
      closeConfirmModal();
    }});

    window.addEventListener('beforeunload', () => {{
      if (selectedAvatarUrl) URL.revokeObjectURL(selectedAvatarUrl);
      if (confirmModalOpen) document.body.style.overflow = '';
    }});

    renderBotProfilePreview();
  }}
}})();
