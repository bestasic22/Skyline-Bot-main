(() => {
  const commandSearch = document.getElementById('ownerbotCommandSearch');
  const commandMatrix = document.getElementById('ownerbotCommandMatrix');
  const commandSummary = document.getElementById('ownerbotCommandSummary');
  const commandHidden = document.getElementById('ownerbotCommandHidden');
  const seedSelectedCommands = {selected_disabled_commands_json};

  if (!(commandMatrix instanceof HTMLElement) || !(commandHidden instanceof HTMLInputElement)) {
    return;
  }

  const normalize = (value) => String(value || '').trim().toLowerCase();
  const selectedSet = new Set(
    (Array.isArray(seedSelectedCommands) ? seedSelectedCommands : [])
      .map((item) => normalize(item))
      .filter((item) => Boolean(item))
  );

  let queryText = '';
  let limit = 220;
  let total = 0;
  let commands = [];
  let loading = false;
  let debounceTimer = 0;

  const syncHidden = () => {
    const rows = Array.from(selectedSet).sort();
    commandHidden.value = rows.join('\n');
  };

  const updateSummary = () => {
    if (!(commandSummary instanceof HTMLElement)) {
      return;
    }
    const selectedCount = selectedSet.size;
    const loadedCount = commands.length;
    if (loading) {
      commandSummary.textContent = `Loading commands... (${loadedCount}/${Math.max(total, loadedCount)}) | Disabled: ${selectedCount}`;
      return;
    }
    commandSummary.textContent = `Showing ${loadedCount}/${Math.max(total, loadedCount)} command(s) | Disabled: ${selectedCount}`;
  };

  const renderMatrix = () => {
    commandMatrix.innerHTML = '';
    if (!commands.length && !loading) {
      const empty = document.createElement('div');
      empty.className = 'ownerbot-empty';
      empty.textContent = queryText ? 'No command found for this search' : 'No command data';
      commandMatrix.appendChild(empty);
      updateSummary();
      return;
    }

    const list = document.createElement('div');
    list.className = 'ownerbot-command-grid';

    commands.forEach((name) => {
      const normalized = normalize(name);
      if (!normalized) {
        return;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'ghost-btn ownerbot-command-chip';
      if (selectedSet.has(normalized)) {
        button.classList.add('is-active');
      }
      button.dataset.commandName = normalized;
      button.textContent = normalized;
      button.addEventListener('click', () => {
        if (selectedSet.has(normalized)) {
          selectedSet.delete(normalized);
          button.classList.remove('is-active');
        } else {
          selectedSet.add(normalized);
          button.classList.add('is-active');
        }
        syncHidden();
        updateSummary();
      });
      list.appendChild(button);
    });

    commandMatrix.appendChild(list);

    if (commands.length < total) {
      const moreWrap = document.createElement('div');
      moreWrap.className = 'auth-actions';
      moreWrap.style.justifyContent = 'flex-start';
      moreWrap.style.marginTop = '10px';
      const moreButton = document.createElement('button');
      moreButton.type = 'button';
      moreButton.className = 'ghost-btn';
      moreButton.textContent = `Show more (${commands.length}/${total})`;
      moreButton.addEventListener('click', () => {
        if (loading) {
          return;
        }
        limit = Math.min(5000, limit + 220);
        void loadCommands({ force: true });
      });
      moreWrap.appendChild(moreButton);
      commandMatrix.appendChild(moreWrap);
    }

    updateSummary();
  };

  const loadCommands = async ({ force = false } = {}) => {
    if (loading && !force) {
      return;
    }
    loading = true;
    updateSummary();
    try {
      const params = new URLSearchParams();
      params.set('limit', String(limit));
      if (queryText) {
        params.set('q', queryText);
      }
      const response = await fetch(`/dashboard/admin/ownerbot/commands?${params.toString()}`, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      if (!payload || payload.ok !== true) {
        throw new Error('bad_payload');
      }
      total = Number(payload.total || 0);
      commands = Array.isArray(payload.commands)
        ? payload.commands.map((item) => normalize(item)).filter((item) => Boolean(item))
        : [];
    } catch (_error) {
      commands = [];
      total = 0;
    } finally {
      loading = false;
      renderMatrix();
      syncHidden();
    }
  };

  const queueSearch = () => {
    if (debounceTimer) {
      window.clearTimeout(debounceTimer);
    }
    debounceTimer = window.setTimeout(() => {
      limit = 220;
      void loadCommands({ force: true });
    }, 240);
  };

  if (commandSearch instanceof HTMLInputElement) {
    commandSearch.addEventListener('input', () => {
      queryText = normalize(commandSearch.value);
      queueSearch();
    });
    commandSearch.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') {
        return;
      }
      event.preventDefault();
      queryText = normalize(commandSearch.value);
      limit = 220;
      void loadCommands({ force: true });
    });
  }

  syncHidden();
  void loadCommands({ force: true });
})();
