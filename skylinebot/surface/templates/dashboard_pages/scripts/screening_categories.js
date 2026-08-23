(() => {{
  const form = document.getElementById('screeningCategoriesForm');
  if (!form) return;

  const cards = Array.from(form.querySelectorAll('[data-sc-card]'));
  const searchInput = document.getElementById('scSearchInput');
  const filterButtons = Array.from(form.querySelectorAll('[data-sc-filter]'));
  const expandButtons = Array.from(form.querySelectorAll('[data-sc-expand]'));
  const resultCount = document.getElementById('scResultCount');
  const emptyState = document.getElementById('scEmptyState');
  const capNotice = document.getElementById('scCapNotice');

  const statTotal = document.getElementById('scStatTotal');
  const statEnabled = document.getElementById('scStatEnabled');
  const statDisabled = document.getElementById('scStatDisabled');
  const statLocked = document.getElementById('scStatLocked');
  const statPlanCap = document.getElementById('scStatPlanCap');

  const planCapValue = Number.parseInt(String(form.getAttribute('data-plan-cap') || '0'), 10);
  const planCap = Number.isFinite(planCapValue) && planCapValue > 0 ? planCapValue : 0;

  let activeFilter = 'all';
  let capNoticeTimer = null;

  const getToggle = (card) => card.querySelector('[data-sc-toggle]');
  const isPremiumLocked = (card) => String(card.getAttribute('data-sc-premium-locked') || '0') === '1';

  const enabledCountNow = () => cards.reduce((acc, card) => {{
    const toggle = getToggle(card);
    if (!toggle) return acc;
    if (toggle.checked && !isPremiumLocked(card)) return acc + 1;
    return acc;
  }}, 0);

  const showCapNotice = (message) => {{
    if (!capNotice) return;
    capNotice.textContent = String(message || '');
    capNotice.hidden = false;
    if (capNoticeTimer) clearTimeout(capNoticeTimer);
    capNoticeTimer = setTimeout(() => {{
      capNotice.hidden = true;
      capNotice.textContent = '';
    }}, 3200);
  }};

  const syncCard = (card, autoOpen = false) => {{
    const toggle = getToggle(card);
    const color = card.querySelector('[data-sc-color]');
    const select = card.querySelector('select[name$="_channel_id"]');
    const stateNode = card.querySelector('[data-sc-state]');
    if (!toggle || !color || !select) return;

    const premiumLocked = isPremiumLocked(card);
    const capLocked = String(card.getAttribute('data-sc-cap-locked') || '0') === '1';
    const enabled = !!toggle.checked && !premiumLocked;

    card.classList.remove('is-enabled', 'is-disabled', 'is-locked');

    let stateText = 'Disabled';
    let stateClass = 'off';

    if (premiumLocked) {{
      card.classList.add('is-locked', 'is-disabled');
      stateText = 'Premium Locked';
      stateClass = 'locked';
    }} else if (capLocked && !enabled) {{
      card.classList.add('is-locked', 'is-disabled');
      stateText = 'Plan Limit';
      stateClass = 'locked';
    }} else if (enabled) {{
      card.classList.add('is-enabled');
      stateText = 'Enabled';
      stateClass = 'on';
    }} else {{
      card.classList.add('is-disabled');
    }}

    if (stateNode) {{
      stateNode.classList.remove('on', 'off', 'locked');
      stateNode.classList.add(stateClass);
      stateNode.textContent = stateText;
    }}

    const disableInputs = !enabled || premiumLocked || (capLocked && !enabled);
    color.disabled = disableInputs;
    select.disabled = disableInputs;

    if (enabled && autoOpen && !card.open) {{
      card.open = true;
    }}
  }};

  const applyCapLocks = () => {{
    const enabledCount = enabledCountNow();
    const capReached = planCap > 0 && enabledCount >= planCap;

    cards.forEach((card) => {{
      const toggle = getToggle(card);
      if (!toggle) return;
      const premiumLocked = isPremiumLocked(card);
      const capLocked = !premiumLocked && !toggle.checked && capReached;

      card.setAttribute('data-sc-cap-locked', capLocked ? '1' : '0');
      toggle.disabled = premiumLocked || capLocked;

      syncCard(card);
    }});
  }};

  const getCardState = (card) => {{
    if (card.classList.contains('is-locked')) return 'locked';
    if (card.classList.contains('is-enabled')) return 'enabled';
    return 'disabled';
  }};

  const refreshStats = () => {{
    let enabled = 0;
    let disabled = 0;
    let locked = 0;

    cards.forEach((card) => {{
      const state = getCardState(card);
      if (state === 'locked') locked += 1;
      else if (state === 'enabled') enabled += 1;
      else disabled += 1;
    }});

    if (statTotal) statTotal.textContent = String(cards.length);
    if (statEnabled) statEnabled.textContent = String(enabled);
    if (statDisabled) statDisabled.textContent = String(disabled);
    if (statLocked) statLocked.textContent = String(locked);
    if (statPlanCap) statPlanCap.textContent = String(enabled) + '/' + String(planCap || cards.length);
  }};

  const matchesFilter = (card) => {{
    if (activeFilter === 'all') return true;
    return getCardState(card) === activeFilter;
  }};

  const applyView = () => {{
    const query = String((searchInput && searchInput.value) || '').trim().toLowerCase();
    let visibleCount = 0;

    cards.forEach((card) => {{
      const token = String(card.getAttribute('data-sc-search') || '').toLowerCase();
      const searchMatch = !query || token.indexOf(query) >= 0;
      const show = searchMatch && matchesFilter(card);
      card.classList.toggle('is-hidden', !show);
      if (show) visibleCount += 1;
    }});

    if (resultCount) {{
      resultCount.textContent = 'Showing ' + visibleCount + ' / ' + cards.length + ' categories';
    }}

    if (emptyState) {{
      const shouldShow = visibleCount === 0;
      emptyState.hidden = !shouldShow;
      emptyState.classList.toggle('is-show', shouldShow);
    }}
  }};

  cards.forEach((card) => {{
    const toggle = getToggle(card);

    card.querySelectorAll('[data-sc-stop-toggle], [data-sc-stop-toggle] *').forEach((node) => {{
      node.addEventListener('click', (event) => event.stopPropagation());
      node.addEventListener('keydown', (event) => {{
        if (event.key === ' ' || event.key === 'Enter') event.stopPropagation();
      }});
    }});

    if (toggle) {{
      toggle.addEventListener('change', () => {{
        if (toggle.checked && planCap > 0 && enabledCountNow() > planCap) {{
          toggle.checked = false;
          showCapNotice('Reached plan limit: max ' + planCap + ' categories');
        }}

        applyCapLocks();
        refreshStats();
        applyView();
      }});
    }}

    syncCard(card, true);
  }});

  filterButtons.forEach((button) => {{
    button.addEventListener('click', () => {{
      activeFilter = String(button.getAttribute('data-sc-filter') || 'all');
      filterButtons.forEach((node) => node.classList.remove('is-active'));
      button.classList.add('is-active');
      applyView();
    }});
  }});

  expandButtons.forEach((button) => {{
    button.addEventListener('click', () => {{
      const mode = String(button.getAttribute('data-sc-expand') || 'all');
      cards.forEach((card) => {{
        if (card.classList.contains('is-hidden')) return;
        card.open = mode === 'all';
      }});
    }});
  }});

  if (searchInput) searchInput.addEventListener('input', applyView);

  applyCapLocks();
  refreshStats();
  applyView();
}})();
