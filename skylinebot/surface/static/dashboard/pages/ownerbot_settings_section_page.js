(() => {
  const root = document.querySelector('[data-ownerbot-root]');
  if (!root) {
    return;
  }

  const activeSection = String(root.getAttribute('data-ownerbot-initial-section') || '').trim().toLowerCase();
  const normalize = (value) => String(value || '').trim().toLowerCase();
  const contains = (haystack, needle) => !needle || haystack.includes(needle);
  const setText = (node, value) => {
    if (node) {
      node.textContent = String(value);
    }
  };

  const guildSearch = document.getElementById('ownerbotGuildSearch');
  const guildSelect = document.getElementById('ownerbotGuildSelect');
  const guildHint = document.getElementById('ownerbotGuildHint');
  const guildVisibleCount = document.getElementById('ownerbotGuildVisibleCount');

  const redeemSearch = document.getElementById('ownerbotRedeemSearch');
  const redeemVisibleCount = document.getElementById('ownerbotRedeemVisibleCount');

  const walletSearch = document.getElementById('ownerbotWalletSearch');
  const walletHint = document.getElementById('ownerbotWalletHint');
  const walletVisibleCount = document.getElementById('ownerbotWalletVisibleCount');

  const promoteGuildSearch = document.getElementById('ownerbotPromoteGuildSearch');
  const promoteGuildHint = document.getElementById('ownerbotPromoteGuildHint');
  const promoteGuildVisibleCount = document.getElementById('ownerbotPromoteGuildVisibleCount');

  const promoteSuspendedSearch = document.getElementById('ownerbotPromoteSuspendedSearch');
  const promoteSuspendedVisibleCount = document.getElementById('ownerbotPromoteSuspendedVisibleCount');

  const ownerbotRedeemValidDaysInput = document.getElementById('ownerbotRedeemValidDays');
  const ownerbotRedeemValidUntilInput = document.getElementById('ownerbotRedeemValidUntil');
  const ownerbotRedeemDurationHint = document.getElementById('ownerbotRedeemDurationHint');

  const clearFiltersButton = document.getElementById('ownerbotClearFilters');

  const getGuildCards = () => Array.from(document.querySelectorAll('[data-ownerbot-guild-card]'));
  const getRedeemCards = () => Array.from(document.querySelectorAll('[data-ownerbot-redeem]'));
  const getWalletCards = () => Array.from(document.querySelectorAll('[data-ownerbot-wallet-card]'));
  const getPromoteGuildCards = () => Array.from(document.querySelectorAll('[data-ownerbot-promote-guild-card]'));
  const getPromoteSuspensionCards = () => Array.from(document.querySelectorAll('[data-ownerbot-promote-suspension-card]'));

  const applyGuildOptionFilter = () => {
    if (!(guildSearch instanceof HTMLInputElement) || !(guildSelect instanceof HTMLSelectElement)) {
      return;
    }
    const query = normalize(guildSearch.value);
    const options = Array.from(guildSelect.options || []);
    options.forEach((option, index) => {
      if (!(option instanceof HTMLOptionElement)) {
        return;
      }
      if (index === 0) {
        option.hidden = false;
        return;
      }
      const text = normalize(option.textContent || option.value);
      option.hidden = !contains(text, query);
    });
    if (guildSelect.selectedOptions.length === 0 || guildSelect.selectedOptions[0]?.hidden) {
      guildSelect.value = '';
    }
  };

  const applyGuildFilter = () => {
    const cards = getGuildCards();
    if (!cards.length) {
      return;
    }
    const query = normalize(guildSearch?.value);
    const focusId = normalize(guildSelect?.value);
    let visible = 0;
    cards.forEach((card) => {
      const name = normalize(card.getAttribute('data-guild-name'));
      const guildId = normalize(card.getAttribute('data-guild-id'));
      const show = contains(`${name} ${guildId}`, query) && (!focusId || focusId === guildId);
      card.style.display = show ? '' : 'none';
      if (show) {
        visible += 1;
      }
    });
    setText(guildVisibleCount, visible);
    if (guildHint) {
      guildHint.textContent = visible > 0
        ? `Showing ${visible} guild card(s)`
        : 'No guild matches this filter';
    }
  };

  const applyRedeemFilter = () => {
    const cards = getRedeemCards();
    if (!cards.length) {
      return;
    }
    const query = normalize(redeemSearch?.value);
    let visible = 0;
    cards.forEach((card) => {
      const code = normalize(card.getAttribute('data-code'));
      const value = normalize(card.getAttribute('data-value'));
      const claimed = card.getAttribute('data-claimed') === '1' ? 'used claimed' : 'unused unclaimed';
      const show = contains(`${code} ${value} ${claimed}`, query);
      card.style.display = show ? '' : 'none';
      if (show) {
        visible += 1;
      }
    });
    setText(redeemVisibleCount, visible);
  };

  const renderWalletHistoryPage = (card, page) => {
    if (!(card instanceof HTMLElement)) {
      return;
    }
    const totalPages = Math.max(1, Number(card.getAttribute('data-wallet-history-total-pages') || 1));
    const nextPage = Math.min(totalPages, Math.max(1, Number(page || 1)));
    card.setAttribute('data-wallet-history-current-page', String(nextPage));

    const entries = Array.from(card.querySelectorAll('[data-wallet-history-entry]'));
    entries.forEach((entry) => {
      if (!(entry instanceof HTMLElement)) {
        return;
      }
      const entryPage = Number(entry.getAttribute('data-wallet-history-page') || 1);
      entry.style.display = entryPage === nextPage ? '' : 'none';
    });

    const label = card.querySelector('[data-wallet-history-page-label]');
    if (label instanceof HTMLElement) {
      label.textContent = `Page ${nextPage} / ${totalPages}`;
    }

    const prevButton = card.querySelector('[data-wallet-history-prev]');
    const nextButton = card.querySelector('[data-wallet-history-next]');
    if (prevButton instanceof HTMLButtonElement) {
      prevButton.disabled = nextPage <= 1;
    }
    if (nextButton instanceof HTMLButtonElement) {
      nextButton.disabled = nextPage >= totalPages;
    }

    const jumpButtons = Array.from(card.querySelectorAll('[data-wallet-history-page-jump]'));
    jumpButtons.forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      const isActive = Number(button.getAttribute('data-wallet-history-page-jump') || 0) === nextPage;
      button.classList.toggle('is-active', isActive);
    });
  };

  const initWalletHistoryPagination = () => {
    const cards = getWalletCards();
    cards.forEach((card) => {
      if (!(card instanceof HTMLElement)) {
        return;
      }
      const totalPages = Math.max(1, Number(card.getAttribute('data-wallet-history-total-pages') || 1));
      if (totalPages <= 1) {
        return;
      }
      card.addEventListener('click', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }

        const currentPage = Number(card.getAttribute('data-wallet-history-current-page') || 1);
        const prevBtn = target.closest('[data-wallet-history-prev]');
        if (prevBtn) {
          event.preventDefault();
          renderWalletHistoryPage(card, currentPage - 1);
          return;
        }

        const nextBtn = target.closest('[data-wallet-history-next]');
        if (nextBtn) {
          event.preventDefault();
          renderWalletHistoryPage(card, currentPage + 1);
          return;
        }

        const jumpBtn = target.closest('[data-wallet-history-page-jump]');
        if (jumpBtn instanceof HTMLElement) {
          event.preventDefault();
          const nextPage = Number(jumpBtn.getAttribute('data-wallet-history-page-jump') || currentPage);
          renderWalletHistoryPage(card, nextPage);
        }
      });
      renderWalletHistoryPage(card, 1);
    });
  };

  const applyWalletFilter = () => {
    const cards = getWalletCards();
    if (!cards.length) {
      return;
    }
    const query = normalize(walletSearch?.value);
    let visible = 0;
    cards.forEach((card) => {
      const userId = normalize(card.getAttribute('data-wallet-user-id'));
      const name = normalize(card.getAttribute('data-wallet-display'));
      const history = normalize(card.getAttribute('data-wallet-history-query'));
      const show = contains(`${userId} ${name} ${history}`, query);
      card.style.display = show ? '' : 'none';
      if (show) {
        visible += 1;
      }
    });
    setText(walletVisibleCount, visible);
    if (walletHint) {
      walletHint.textContent = visible > 0
        ? `Showing ${visible} wallet card(s)`
        : 'No wallet matches this filter';
    }
  };

  const applyPromoteGuildFilter = () => {
    const cards = getPromoteGuildCards();
    if (!cards.length) {
      return;
    }
    const query = normalize(promoteGuildSearch?.value);
    let visible = 0;
    cards.forEach((card) => {
      const guildId = normalize(card.getAttribute('data-guild-id'));
      const guildName = normalize(card.getAttribute('data-guild-name'));
      const status = normalize(card.getAttribute('data-guild-status'));
      const show = contains(`${guildId} ${guildName} ${status}`, query);
      card.style.display = show ? '' : 'none';
      if (show) {
        visible += 1;
      }
    });
    setText(promoteGuildVisibleCount, visible);
    if (promoteGuildHint) {
      promoteGuildHint.textContent = visible > 0
        ? `Showing ${visible} promote guild card(s)`
        : 'No promote guild matches this filter';
    }
  };

  const applyPromoteSuspensionFilter = () => {
    const cards = getPromoteSuspensionCards();
    if (!cards.length) {
      return;
    }
    const query = normalize(promoteSuspendedSearch?.value);
    let visible = 0;
    cards.forEach((card) => {
      const guildId = normalize(card.getAttribute('data-guild-id'));
      const guildName = normalize(card.getAttribute('data-guild-name'));
      const show = contains(`${guildId} ${guildName}`, query);
      card.style.display = show ? '' : 'none';
      if (show) {
        visible += 1;
      }
    });
    setText(promoteSuspendedVisibleCount, visible);
  };

  const updateRedeemDurationHint = () => {
    if (!ownerbotRedeemDurationHint) {
      return;
    }
    const days = Number(ownerbotRedeemValidDaysInput?.value || 0);
    const untilRaw = String(ownerbotRedeemValidUntilInput?.value || '').trim();

    if (untilRaw) {
      ownerbotRedeemDurationHint.textContent = 'Using exact date/time for validity';
      return;
    }
    if (!Number.isFinite(days) || days < 0) {
      ownerbotRedeemDurationHint.textContent = 'Please provide valid duration';
      return;
    }
    if (days === 0) {
      ownerbotRedeemDurationHint.textContent = '0 day means permanent subscription';
      return;
    }
    ownerbotRedeemDurationHint.textContent = `Redeem will grant approximately ${days} day(s)`;
  };

  const initRedeemDurationSync = () => {
    if (!(ownerbotRedeemValidDaysInput instanceof HTMLInputElement) || !(ownerbotRedeemValidUntilInput instanceof HTMLInputElement)) {
      return;
    }
    ownerbotRedeemValidDaysInput.addEventListener('input', () => {
      updateRedeemDurationHint();
    });
    ownerbotRedeemValidUntilInput.addEventListener('change', () => {
      updateRedeemDurationHint();
    });
    updateRedeemDurationHint();
  };

  const normalizeRedeemSubmitAction = (value) => {
    const action = normalize(value);
    if (action === 'remove' || action === 'del') {
      return 'delete';
    }
    if (action === 'reset' || action === 'reset_claim' || action === 'unclaimed') {
      return 'unclaim';
    }
    if (action === 'delete' || action === 'unclaim') {
      return action;
    }
    return 'save';
  };

  const ensureRedeemActionHidden = (form) => {
    if (!(form instanceof HTMLFormElement)) {
      return null;
    }
    let hidden = form.querySelector('input[type="hidden"][data-ownerbot-redeem-action-hidden="1"]');
    if (!(hidden instanceof HTMLInputElement)) {
      hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'action';
      hidden.value = 'save';
      hidden.setAttribute('data-ownerbot-redeem-action-hidden', '1');
      form.appendChild(hidden);
    }
    return hidden;
  };

  const setRedeemActionIntent = (form, rawAction) => {
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    const action = normalizeRedeemSubmitAction(rawAction);
    const hidden = ensureRedeemActionHidden(form);
    if (hidden instanceof HTMLInputElement) {
      hidden.value = action;
    }
    form.setAttribute('data-ownerbot-redeem-action-intent', action);

    const previousTimerId = Number(form.dataset.ownerbotRedeemIntentTimer || 0);
    if (previousTimerId > 0) {
      window.clearTimeout(previousTimerId);
    }
    const nextTimerId = window.setTimeout(() => {
      form.removeAttribute('data-ownerbot-redeem-action-intent');
      const staleHidden = ensureRedeemActionHidden(form);
      if (staleHidden instanceof HTMLInputElement) {
        staleHidden.value = 'save';
      }
      delete form.dataset.ownerbotRedeemIntentTimer;
    }, 3000);
    form.dataset.ownerbotRedeemIntentTimer = String(nextTimerId);
  };

  const consumeRedeemActionIntent = (form) => {
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    const previousTimerId = Number(form.dataset.ownerbotRedeemIntentTimer || 0);
    if (previousTimerId > 0) {
      window.clearTimeout(previousTimerId);
    }
    delete form.dataset.ownerbotRedeemIntentTimer;
    form.removeAttribute('data-ownerbot-redeem-action-intent');
  };

  const resolveRedeemSubmitAction = (form, submitEvent) => {
    if (!(form instanceof HTMLFormElement)) {
      return 'save';
    }

    let candidate = '';
    const submitter = submitEvent && submitEvent.submitter ? submitEvent.submitter : null;
    if (submitter instanceof HTMLButtonElement || submitter instanceof HTMLInputElement) {
      candidate = String(submitter.value || submitter.getAttribute('value') || '').trim();
    }

    if (!candidate) {
      const focused = document.activeElement;
      if (
        focused instanceof HTMLButtonElement &&
        focused.form === form &&
        normalize(focused.getAttribute('name')) === 'action'
      ) {
        candidate = String(focused.value || focused.getAttribute('value') || '').trim();
      }
    }

    if (!candidate) {
      candidate = String(form.getAttribute('data-ownerbot-redeem-action-intent') || '').trim();
    }

    return normalizeRedeemSubmitAction(candidate || 'save');
  };

  const initRedeemActionGuard = () => {
    const forms = Array.from(
      document.querySelectorAll('form[action="/dashboard/admin/ownerbot/redeem/update"]')
    ).filter((node) => node instanceof HTMLFormElement);
    if (!forms.length) {
      return;
    }

    forms.forEach((form) => {
      if (!(form instanceof HTMLFormElement)) {
        return;
      }
      ensureRedeemActionHidden(form);

      const actionButtons = Array.from(
        form.querySelectorAll('button[type="submit"][name="action"], input[type="submit"][name="action"]')
      );
      actionButtons.forEach((button) => {
        if (button instanceof HTMLButtonElement || button instanceof HTMLInputElement) {
          button.addEventListener('click', () => {
            setRedeemActionIntent(form, button.value || button.getAttribute('value') || 'save');
          });
        }
      });

      form.addEventListener('submit', (event) => {
        const resolvedAction = resolveRedeemSubmitAction(form, event);
        const hidden = ensureRedeemActionHidden(form);
        if (hidden instanceof HTMLInputElement) {
          hidden.value = resolvedAction;
        }
        consumeRedeemActionIntent(form);
      });
    });
  };

  const getMongoHistoryRows = () => Array.from(document.querySelectorAll('#ownerbotMongoHistoryBody [data-mongo-history-row]'));
  const getMongoHistoryCheckboxes = () => Array.from(document.querySelectorAll('[data-mongo-history-select]'));

  const initMongoHistoryTools = () => {
    const table = document.getElementById('ownerbotMongoHistoryTable');
    if (!(table instanceof HTMLTableElement)) {
      return;
    }

    const searchInput = document.getElementById('ownerbotMongoHistorySearch');
    const statusSelect = document.getElementById('ownerbotMongoHistoryStatus');
    const modeSelect = document.getElementById('ownerbotMongoHistoryMode');
    const selectedIdsInput = document.getElementById('ownerbotMongoHistorySelectedIds');
    const visibleNode = document.getElementById('ownerbotMongoHistoryVisible');
    const selectedNode = document.getElementById('ownerbotMongoHistorySelected');
    const selectAll = document.getElementById('ownerbotMongoHistorySelectAll');
    const clearButton = document.getElementById('ownerbotMongoHistoryClear');

    const syncMongoHistorySelection = () => {
      const visibleRows = getMongoHistoryRows().filter((row) => row instanceof HTMLElement && row.style.display !== 'none');
      const visibleChecks = visibleRows
        .map((row) => row.querySelector('[data-mongo-history-select]'))
        .filter((node) => node instanceof HTMLInputElement);
      const selectedChecks = getMongoHistoryCheckboxes().filter((node) => node instanceof HTMLInputElement && node.checked);
      const selectedIds = selectedChecks
        .map((node) => String(node.value || '').trim())
        .filter((value) => Boolean(value));

      if (selectedIdsInput instanceof HTMLInputElement) {
        selectedIdsInput.value = selectedIds.join(',');
      }
      setText(selectedNode, selectedIds.length);

      if (selectAll instanceof HTMLInputElement) {
        const visibleCount = visibleChecks.length;
        const checkedVisibleCount = visibleChecks.filter((node) => node.checked).length;
        selectAll.checked = visibleCount > 0 && checkedVisibleCount === visibleCount;
        selectAll.indeterminate = checkedVisibleCount > 0 && checkedVisibleCount < visibleCount;
      }
    };

    const applyMongoHistoryFilter = () => {
      const query = normalize(searchInput?.value);
      const statusValue = normalize(statusSelect?.value || 'all');
      const modeValue = normalize(modeSelect?.value || 'all');

      let visible = 0;
      getMongoHistoryRows().forEach((row) => {
        if (!(row instanceof HTMLElement)) {
          return;
        }
        const searchBlob = normalize(row.getAttribute('data-search'));
        const rowStatus = normalize(row.getAttribute('data-status'));
        const rowMode = normalize(row.getAttribute('data-mode'));
        const statusOk = statusValue === 'all' || rowStatus === statusValue;
        const modeOk = modeValue === 'all' || rowMode === modeValue;
        const textOk = contains(searchBlob, query);
        const show = statusOk && modeOk && textOk;
        row.style.display = show ? '' : 'none';
        if (show) {
          visible += 1;
        }
      });

      setText(visibleNode, visible);
      syncMongoHistorySelection();
    };

    if (searchInput instanceof HTMLInputElement) {
      searchInput.addEventListener('input', applyMongoHistoryFilter);
    }
    if (statusSelect instanceof HTMLSelectElement) {
      statusSelect.addEventListener('change', applyMongoHistoryFilter);
    }
    if (modeSelect instanceof HTMLSelectElement) {
      modeSelect.addEventListener('change', applyMongoHistoryFilter);
    }

    getMongoHistoryCheckboxes().forEach((checkbox) => {
      if (checkbox instanceof HTMLInputElement) {
        checkbox.addEventListener('change', syncMongoHistorySelection);
      }
    });

    if (selectAll instanceof HTMLInputElement) {
      selectAll.addEventListener('change', () => {
        const rows = getMongoHistoryRows();
        rows.forEach((row) => {
          if (!(row instanceof HTMLElement) || row.style.display === 'none') {
            return;
          }
          const checkbox = row.querySelector('[data-mongo-history-select]');
          if (checkbox instanceof HTMLInputElement) {
            checkbox.checked = selectAll.checked;
          }
        });
        syncMongoHistorySelection();
      });
    }

    if (clearButton instanceof HTMLButtonElement) {
      clearButton.addEventListener('click', () => {
        if (searchInput instanceof HTMLInputElement) {
          searchInput.value = '';
        }
        if (statusSelect instanceof HTMLSelectElement) {
          statusSelect.value = 'all';
        }
        if (modeSelect instanceof HTMLSelectElement) {
          modeSelect.value = 'all';
        }
        getMongoHistoryCheckboxes().forEach((checkbox) => {
          if (checkbox instanceof HTMLInputElement) {
            checkbox.checked = false;
          }
        });
        if (selectAll instanceof HTMLInputElement) {
          selectAll.checked = false;
          selectAll.indeterminate = false;
        }
        applyMongoHistoryFilter();
      });
    }

    applyMongoHistoryFilter();
  };

  const applyAllFilters = () => {
    applyGuildOptionFilter();
    applyGuildFilter();
    applyRedeemFilter();
    applyWalletFilter();
    applyPromoteGuildFilter();
    applyPromoteSuspensionFilter();
  };

  if (guildSearch instanceof HTMLInputElement) {
    guildSearch.addEventListener('input', () => {
      applyGuildOptionFilter();
      applyGuildFilter();
    });
  }
  if (guildSelect instanceof HTMLSelectElement) {
    guildSelect.addEventListener('change', applyGuildFilter);
  }
  if (redeemSearch instanceof HTMLInputElement) {
    redeemSearch.addEventListener('input', applyRedeemFilter);
  }
  if (walletSearch instanceof HTMLInputElement) {
    walletSearch.addEventListener('input', applyWalletFilter);
  }
  if (promoteGuildSearch instanceof HTMLInputElement) {
    promoteGuildSearch.addEventListener('input', applyPromoteGuildFilter);
  }
  if (promoteSuspendedSearch instanceof HTMLInputElement) {
    promoteSuspendedSearch.addEventListener('input', applyPromoteSuspensionFilter);
  }

  if (clearFiltersButton instanceof HTMLButtonElement) {
    clearFiltersButton.addEventListener('click', () => {
      [guildSearch, redeemSearch, walletSearch, promoteGuildSearch, promoteSuspendedSearch].forEach((input) => {
        if (input instanceof HTMLInputElement) {
          input.value = '';
        }
      });
      if (guildSelect instanceof HTMLSelectElement) {
        guildSelect.value = '';
      }
      applyAllFilters();
    });
  }

  if (activeSection === 'wallet') {
    initWalletHistoryPagination();
  }
  if (activeSection === 'redeem') {
    initRedeemDurationSync();
    initRedeemActionGuard();
  }
  if (activeSection === 'mongo') {
    initMongoHistoryTools();
  }

  applyAllFilters();
})();
