(() => {{
        const form = document.getElementById('economySettingsForm');
        if (!form) return;
        const contentRoot = form.querySelector('.econ-content');
        if (contentRoot instanceof HTMLElement) {{
          contentRoot.setAttribute('data-econ-ready', '1');
          contentRoot.classList.add('is-initialized');
        }}
        const navButtons = Array.from(form.querySelectorAll('.econ-nav-item[data-econ-target]'))
          .filter((btn) => !(btn instanceof HTMLElement) || !btn.closest('[hidden]'));
        const pages = Array.from(form.querySelectorAll('.econ-page[data-econ-page]'));
        const jumpButtons = Array.from(form.querySelectorAll('.econ-jump-chip[data-econ-target]'));
        const activeSectionLabel = document.getElementById('econActiveSectionLabel');
        const sectionSearchInput = document.getElementById('econSectionSearch');
        const sectionSearchMeta = document.getElementById('econSectionSearchMeta');
        const fallbackPageId = String(pages[0]?.dataset.econPage || 'currency_symbol');
        const resolveSectionLabel = (id) => {{
          const nav = navButtons.find((btn) => String(btn.dataset.econTarget || '') === String(id || ''));
          if (nav) {{
            const titleNode = nav.querySelector('.econ-nav-main');
            const rawFromNav = String(titleNode?.textContent || nav.textContent || 'Currency Symbol');
            return rawFromNav.replace(/\\s+/g, ' ').trim() || 'Currency Symbol';
          }}
          const jump = jumpButtons.find((btn) => String(btn.dataset.econTarget || '') === String(id || ''));
          const raw = String(jump?.querySelector('span')?.textContent || jump?.textContent || 'Currency Symbol');
          return raw.replace(/\\s+/g, ' ').trim() || 'Currency Symbol';
        }};
        const applySectionSearch = () => {{
          const query = String(sectionSearchInput instanceof HTMLInputElement ? sectionSearchInput.value : '')
            .toLowerCase()
            .trim();
          let visibleCount = 0;
          navButtons.forEach((btn) => {{
            const text = String(btn.textContent || '').toLowerCase();
            const visible = !query || text.includes(query);
            if (btn instanceof HTMLElement) btn.style.display = visible ? '' : 'none';
            if (visible) visibleCount += 1;
          }});
          let jumpVisibleCount = 0;
          jumpButtons.forEach((btn) => {{
            const text = String(btn.textContent || '').toLowerCase();
            const visible = !query || text.includes(query);
            if (btn instanceof HTMLElement) btn.style.display = visible ? '' : 'none';
            if (visible) jumpVisibleCount += 1;
          }});
          if (sectionSearchMeta) {{
            const total = navButtons.length || jumpButtons.length || 0;
            const count = navButtons.length ? visibleCount : jumpVisibleCount;
            sectionSearchMeta.textContent = query
              ? `${{count}} / ${{total}} sections`
              : `${{total}} sections`;
          }}
        }};
        const activatePage = (id) => {{
          const candidateId = String(id || fallbackPageId);
          const hasPage = pages.some((page) => String(page.dataset.econPage || '') === candidateId);
          const normalizedId = hasPage ? candidateId : fallbackPageId;
          navButtons.forEach((btn) => btn.classList.toggle('active', btn.dataset.econTarget === normalizedId));
          pages.forEach((page) => page.classList.toggle('active', page.dataset.econPage === normalizedId));
          jumpButtons.forEach((btn) => btn.classList.toggle('active', btn.dataset.econTarget === normalizedId));
          if (activeSectionLabel) activeSectionLabel.textContent = resolveSectionLabel(normalizedId);
          if (contentRoot instanceof HTMLElement) {{
            contentRoot.setAttribute('data-econ-ready', '1');
            contentRoot.classList.add('is-initialized');
            contentRoot.scrollTop = 0;
          }}
          return normalizedId;
        }};
        navButtons.forEach((btn) => btn.addEventListener('click', () => {{
          const target = String(btn.dataset.econTarget || 'currency_symbol');
          const finalTarget = activatePage(target);
          if (window.history && typeof window.history.replaceState === 'function') {{
            window.history.replaceState(null, '', `#${{finalTarget}}`);
          }}
        }}));
        jumpButtons.forEach((btn) => btn.addEventListener('click', () => {{
          const target = String(btn.dataset.econTarget || 'currency_symbol');
          const finalTarget = activatePage(target);
          if (window.history && typeof window.history.replaceState === 'function') {{
            window.history.replaceState(null, '', `#${{finalTarget}}`);
          }}
        }}));
        const initialPage = String(window.location.hash || '').replace('#', '').trim() || 'currency_symbol';
        const existsInitial = pages.some((page) => page.dataset.econPage === initialPage);
        activatePage(existsInitial ? initialPage : fallbackPageId);
        sectionSearchInput?.addEventListener('input', applySectionSearch);
        applySectionSearch();
        if (window.location.hash && window.scrollY > 180) {{
          const shell = form.closest('.page-economy-shell');
          if (shell instanceof HTMLElement) {{
            const top = Math.max(0, Math.floor(window.scrollY + shell.getBoundingClientRect().top - 12));
            window.scrollTo({{ top, behavior: 'auto' }});
          }}
        }}

        const currencyInput = document.getElementById('currencySymbolInput');
        const pickerToggle = document.getElementById('toggleEmojiPicker');
        const picker = document.getElementById('economyEmojiPicker');
        const searchInput = document.getElementById('economyEmojiSearch');
        const PICKER_GAP = 8;
        const PICKER_MAX_HEIGHT = 420;
        const PICKER_VIEWPORT_PADDING = 12;
        let pickerPositionRaf = 0;
        const allEmojiButtons = Array.from(form.querySelectorAll('.econ-emoji-btn[data-emoji]'));
        const serverEmojiGroups = Array.from(form.querySelectorAll('.econ-emoji-server-group'));
        const previewCash = document.getElementById('econPreviewCash');
        const previewBank = document.getElementById('econPreviewBank');
        const previewTotal = document.getElementById('econPreviewTotal');
        const DEFAULT_CURRENCY_SYMBOL = '\u0E3F';
        const parseCustomEmojiToken = (value) => {{
          const token = String(value || '').trim();
          if (!token.startsWith('<') || !token.endsWith('>')) return null;
          const body = token.slice(1, -1);
          const parts = body.split(':');
          if (parts.length !== 3) return null;
          let animated = false;
          let name = '';
          let id = '';
          if (parts[0] === 'a') {{
            animated = true;
            name = String(parts[1] || '').trim();
            id = String(parts[2] || '').trim();
          }} else if (parts[0] === '') {{
            name = String(parts[1] || '').trim();
            id = String(parts[2] || '').trim();
          }} else {{
            return null;
          }}
          if (!name || name.length < 2 || name.length > 32) return null;
          if (!/^[0-9]+$/.test(id) || id.length < 15 || id.length > 22) return null;
          return {{ animated, name, id }};
        }};
        const escapeHtml = (raw) => {{
          return String(raw || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
        }};
        const buildPreviewValueMarkup = (symbol, amount) => {{
          const parsed = parseCustomEmojiToken(symbol);
          if (parsed) {{
            const ext = parsed.animated ? 'gif' : 'png';
            const emojiUrl = `https://cdn.discordapp.com/emojis/${{parsed.id}}.${{ext}}?size=48&quality=lossless`;
            return (
              `<span class="econ-preview-symbol emoji"><img src="${{emojiUrl}}" alt="${{escapeHtml(parsed.name)}}" loading="lazy"></span>` +
              `<span class="econ-preview-amount">${{amount}}</span>`
            );
          }}
          return (
            `<span class="econ-preview-symbol text">${{escapeHtml(symbol)}}</span>` +
            `<span class="econ-preview-amount">${{amount}}</span>`
          );
        }};
        const normalizeCurrencySymbol = (raw) => {{
          const cleaned = String(raw || '')
            .replace(/\\uFFFD/g, '')
            .replace(/[\\r\\n\\t]/g, '')
            .trim();
          if (!cleaned) return DEFAULT_CURRENCY_SYMBOL;
          if (parseCustomEmojiToken(cleaned)) {{
            return cleaned.slice(0, 64);
          }}
          return cleaned.slice(0, 32);
        }};
        const syncPreview = () => {{
          const sym = normalizeCurrencySymbol(currencyInput?.value || DEFAULT_CURRENCY_SYMBOL);
          if (currencyInput && currencyInput.value !== sym) currencyInput.value = sym;
          if (previewCash) previewCash.innerHTML = buildPreviewValueMarkup(sym, '1,000');
          if (previewBank) previewBank.innerHTML = buildPreviewValueMarkup(sym, '5,000');
          if (previewTotal) previewTotal.innerHTML = buildPreviewValueMarkup(sym, '6,000');
        }};
        syncPreview();
        currencyInput?.addEventListener('input', syncPreview);

        const isPickerOpen = () => Boolean(picker && picker.classList.contains('show'));
        const clearPickerRaf = () => {{
          if (!pickerPositionRaf || typeof window.cancelAnimationFrame !== 'function') return;
          window.cancelAnimationFrame(pickerPositionRaf);
          pickerPositionRaf = 0;
        }};
        const resetPickerPlacement = () => {{
          if (!picker) return;
          picker.classList.remove('flip-up');
          picker.style.top = '';
          picker.style.bottom = '';
          picker.style.maxHeight = '';
          picker.style.visibility = '';
        }};
        const positionPicker = () => {{
          if (!picker || !pickerToggle || !isPickerOpen()) return;
          picker.classList.remove('flip-up');
          picker.style.top = `calc(100% + ${{PICKER_GAP}}px)`;
          picker.style.bottom = 'auto';
          picker.style.visibility = 'hidden';
          const toggleRect = pickerToggle.getBoundingClientRect();
          const spaceBelow = Math.floor(window.innerHeight - toggleRect.bottom - PICKER_VIEWPORT_PADDING - PICKER_GAP);
          const spaceAbove = Math.floor(toggleRect.top - PICKER_VIEWPORT_PADDING - PICKER_GAP);
          const shouldFlipUp = spaceBelow < 260 && spaceAbove > spaceBelow;
          const availableSpace = Math.max(96, shouldFlipUp ? spaceAbove : spaceBelow);
          const finalHeight = Math.min(PICKER_MAX_HEIGHT, availableSpace);
          if (shouldFlipUp) {{
            picker.classList.add('flip-up');
            picker.style.top = 'auto';
            picker.style.bottom = `calc(100% + ${{PICKER_GAP}}px)`;
          }}
          picker.style.maxHeight = `${{Math.max(96, finalHeight)}}px`;
          picker.style.visibility = '';
        }};
        const queuePickerPosition = () => {{
          if (!isPickerOpen() || !picker) return;
          clearPickerRaf();
          if (typeof window.requestAnimationFrame === 'function') {{
            pickerPositionRaf = window.requestAnimationFrame(() => {{
              pickerPositionRaf = 0;
              positionPicker();
            }});
          }} else {{
            positionPicker();
          }}
        }};
        const closePicker = () => {{
          if (!picker) return;
          clearPickerRaf();
          picker.classList.remove('show');
          picker.style.display = 'none';
          resetPickerPlacement();
          picker.setAttribute('aria-hidden', 'true');
          pickerToggle?.setAttribute('aria-expanded', 'false');
        }};
        const openPicker = () => {{
          if (!picker) return;
          picker.style.display = 'flex';
          picker.classList.add('show');
          picker.setAttribute('aria-hidden', 'false');
          pickerToggle?.setAttribute('aria-expanded', 'true');
          positionPicker();
          if (searchInput && typeof searchInput.focus === 'function') {{
            try {{
              searchInput.focus({{ preventScroll: true }});
            }} catch {{
              searchInput.focus();
            }}
          }}
        }};
        closePicker();
        navButtons.forEach((btn) => btn.addEventListener('click', closePicker));
        pickerToggle?.addEventListener('click', (ev) => {{
          ev.preventDefault();
          ev.stopPropagation();
          if (isPickerOpen()) {{
            closePicker();
          }} else {{
            openPicker();
          }}
        }});
        picker?.addEventListener('click', (ev) => ev.stopPropagation());
        document.addEventListener('click', (ev) => {{
          if (!picker || !pickerToggle) return;
          const target = ev.target;
          if (!(target instanceof Element)) return;
          if (picker.contains(target) || pickerToggle.contains(target)) return;
          closePicker();
        }});
        document.addEventListener('keydown', (ev) => {{
          if (ev.key === 'Escape') closePicker();
        }});
        document.addEventListener('visibilitychange', () => {{
          if (document.hidden) closePicker();
        }});
        window.addEventListener('resize', queuePickerPosition);
        window.addEventListener('scroll', queuePickerPosition, true);
        searchInput?.addEventListener('input', () => {{
          const q = String(searchInput.value || '').toLowerCase().trim();
          allEmojiButtons.forEach((btn) => {{
            const src = String(btn.getAttribute('data-search') || '').toLowerCase();
            btn.style.display = !q || src.includes(q) ? '' : 'none';
          }});
          serverEmojiGroups.forEach((group) => {{
            const hasVisibleEmoji = Array.from(group.querySelectorAll('.econ-emoji-btn[data-emoji]')).some((btn) => {{
              return (btn instanceof HTMLElement ? btn.style.display : '') !== 'none';
            }});
            if (group instanceof HTMLElement) {{
              group.style.display = hasVisibleEmoji ? '' : 'none';
            }}
          }});
        }});
        allEmojiButtons.forEach((btn) => btn.addEventListener('click', () => {{
          if (!currencyInput) return;
          currencyInput.value = normalizeCurrencySymbol(String(btn.getAttribute('data-emoji') || ''));
          syncPreview();
          closePicker();
        }}));

        const syncCooldownPrefix = (prefix) => {{
          const hidden = form.querySelector(`.cooldown-total[data-prefix="${{prefix}}"]`);
          if (!(hidden instanceof HTMLInputElement)) return;
          const getPart = (unit) => {{
            const el = form.querySelector(`.cooldown-part[data-prefix="${{prefix}}"][data-unit="${{unit}}"]`);
            return el instanceof HTMLInputElement ? Number(el.value || 0) : 0;
          }};
          const d = Math.max(0, Math.floor(getPart('d')));
          const h = Math.max(0, Math.floor(getPart('h')));
          const m = Math.max(0, Math.floor(getPart('m')));
          const s = Math.max(0, Math.floor(getPart('s')));
          hidden.value = String((d * 86400) + (h * 3600) + (m * 60) + s);
        }};
        Array.from(form.querySelectorAll('.cooldown-part[data-prefix]')).forEach((input) => {{
          input.addEventListener('input', () => {{
            const prefix = String(input.getAttribute('data-prefix') || '');
            if (prefix) syncCooldownPrefix(prefix);
          }});
        }});
        ['work', 'slut', 'crime', 'rob', 'chat_money'].forEach(syncCooldownPrefix);

        const allChannelToggle = document.getElementById('chatMoneyAllChannels');
        const channelChecks = Array.from(form.querySelectorAll('.chat-money-channel'));
        const csvInput = document.getElementById('chatMoneyChannelsCsv');
        const economyCommandSelectedCount = document.getElementById('economyCommandSelectedCount');
        const updateChannelRowState = (checkboxes) => {{
          checkboxes.forEach((el) => {{
            if (!(el instanceof HTMLInputElement)) return;
            const row = el.closest('.econ-check-row');
            if (!(row instanceof HTMLElement)) return;
            row.classList.toggle('is-checked', el.checked);
            row.classList.toggle('is-disabled', el.disabled);
          }});
        }};
        const syncChannelCsv = () => {{
          if (!(csvInput instanceof HTMLInputElement)) return;
          if (allChannelToggle instanceof HTMLInputElement && allChannelToggle.checked) {{
            csvInput.value = '';
            channelChecks.forEach((el) => {{
              if (el instanceof HTMLInputElement) el.disabled = true;
            }});
            updateChannelRowState(channelChecks);
            return;
          }}
          channelChecks.forEach((el) => {{
            if (el instanceof HTMLInputElement) el.disabled = false;
          }});
          const ids = channelChecks
            .filter((el) => el instanceof HTMLInputElement && el.checked)
            .map((el) => String(el.value || '').trim())
            .filter(Boolean);
          csvInput.value = ids.join(',');
          updateChannelRowState(channelChecks);
        }};
        if (allChannelToggle) allChannelToggle.addEventListener('change', syncChannelCsv);
        channelChecks.forEach((el) => el.addEventListener('change', syncChannelCsv));
        syncChannelCsv();

        const economyAllChannelsToggle = document.getElementById('economyAllowAllChannels');
        const economyCommandChecks = Array.from(form.querySelectorAll('.economy-command-channel'));
        const economyCommandCsv = document.getElementById('economyCommandChannelsCsv');
        const syncEconomyCommandChannels = () => {{
          if (!(economyCommandCsv instanceof HTMLInputElement)) return;
          if (economyAllChannelsToggle instanceof HTMLInputElement && economyAllChannelsToggle.checked) {{
            economyCommandCsv.value = '';
            economyCommandChecks.forEach((el) => {{
              if (el instanceof HTMLInputElement) el.disabled = true;
            }});
            updateChannelRowState(economyCommandChecks);
            if (economyCommandSelectedCount) economyCommandSelectedCount.textContent = 'ALL';
            return;
          }}
          economyCommandChecks.forEach((el) => {{
            if (el instanceof HTMLInputElement) el.disabled = false;
          }});
          const ids = economyCommandChecks
            .filter((el) => el instanceof HTMLInputElement && el.checked)
            .map((el) => String(el.value || '').trim())
            .filter(Boolean);
          economyCommandCsv.value = ids.join(',');
          updateChannelRowState(economyCommandChecks);
          if (economyCommandSelectedCount) economyCommandSelectedCount.textContent = String(ids.length);
        }};
        economyAllChannelsToggle?.addEventListener('change', syncEconomyCommandChannels);
        economyCommandChecks.forEach((el) => el.addEventListener('change', syncEconomyCommandChannels));
        syncEconomyCommandChannels();
        const economyCommandSearchInput = document.getElementById('economyCommandSearchInput');
        const chatMoneyChannelSearchInput = document.getElementById('chatMoneyChannelSearchInput');
        const filterChannelRows = (query, selector) => {{
          const normalized = String(query || '').toLowerCase().trim();
          const rows = Array.from(form.querySelectorAll(selector));
          rows.forEach((row) => {{
            if (!(row instanceof HTMLElement)) return;
            const label = row.querySelector('.econ-check-label');
            const text = String(label?.textContent || row.textContent || '').toLowerCase();
            const visible = !normalized || text.includes(normalized);
            row.classList.toggle('is-filtered-out', !visible);
          }});
        }};
        const applyChannelFilters = () => {{
          filterChannelRows(
            economyCommandSearchInput instanceof HTMLInputElement ? economyCommandSearchInput.value : '',
            '#economyCommandChannelList .econ-check-row'
          );
          filterChannelRows(
            chatMoneyChannelSearchInput instanceof HTMLInputElement ? chatMoneyChannelSearchInput.value : '',
            '#chatMoneyChannelList .econ-check-row'
          );
        }};
        economyCommandSearchInput?.addEventListener('input', applyChannelFilters);
        chatMoneyChannelSearchInput?.addEventListener('input', applyChannelFilters);
        applyChannelFilters();

        const roleIncomeItems = Array.from(form.querySelectorAll('.econ-role-item[data-ri-target]'));
        const roleIncomeCards = Array.from(form.querySelectorAll('.econ-role-card[data-ri-card]'));
        const roleModeButtons = Array.from(form.querySelectorAll('.econ-role-mode[data-ri-mode]'));
        const roleIncomeLeftPanel = document.getElementById('roleIncomeLeftPanel');
        const roleIncomeModeHint = document.getElementById('roleIncomeModeHint');
        const roleIncomeSlotList = document.getElementById('roleIncomeSlotList');
        const roleIncomeAddSlotBtn = document.getElementById('roleIncomeAddSlotBtn');
        const roleIncomeSlotCounter = document.getElementById('roleIncomeSlotCounter');
        const roleIncomeAddSlotFeedback = document.getElementById('roleIncomeAddSlotFeedback');
        const roleIncomeEnabledToggle = form.querySelector('input[name="role_income_enabled"]');
        const collectableModeButton = roleModeButtons.find((btn) => String(btn.dataset.riMode || '').toLowerCase() === 'collectable') || null;
        const parsedSlotLimit = Number(roleIncomeLeftPanel?.dataset.riLimit || 12);
        const roleIncomeSlotLimit = Number.isFinite(parsedSlotLimit) ? Math.max(1, Math.floor(parsedSlotLimit)) : 12;
        const getRoleIncomeItem = (key) => {{
          return roleIncomeItems.find((el) => String(el.dataset.riTarget || '') === String(key || '')) || null;
        }};
        const fallbackRoleSlotName = (key) => `<Role Slot #${{Math.max(1, Number(key) + 1)}}>`;
        const normalizeSlotKey = (key) => String(key || '').trim();
        const getRoleSelectByKey = (key) => {{
          return form.querySelector(`[name="role_income_role_${{normalizeSlotKey(key)}}"]`);
        }};
        const isRoleSlotUsed = (key) => {{
          const roleSelect = getRoleSelectByKey(key);
          if (!(roleSelect instanceof HTMLSelectElement)) return false;
          return /^[0-9]+$/.test(String(roleSelect.value || '').trim());
        }};
        const getUsedRoleSlotCount = () => {{
          return roleIncomeItems.reduce((count, item) => {{
            const key = normalizeSlotKey(item.dataset.riTarget || '');
            return count + (isRoleSlotUsed(key) ? 1 : 0);
          }}, 0);
        }};
        const cleanRoleName = (raw) => {{
          return String(raw || '')
            .replace(/^@+\s*/, '')
            .replace(/^\u26A0(?:\uFE0F)?\s*/, '')
            .replace(/\s+/g, ' ')
            .trim();
        }};
        const updateRoleIncomeSlotLabel = (key) => {{
          const item = getRoleIncomeItem(key);
          if (!(item instanceof HTMLElement)) return;
          const fallback = String(item.dataset.riSlotLabel || fallbackRoleSlotName(key));
          const labelNode = item.querySelector('.econ-role-item-name');
          if (!(labelNode instanceof HTMLElement)) return;
          const roleSelect = getRoleSelectByKey(key);
          if (!(roleSelect instanceof HTMLSelectElement)) {{
            labelNode.textContent = fallback;
            item.setAttribute('title', fallback);
            return;
          }}
          const selectedOption = roleSelect.options[roleSelect.selectedIndex];
          const selectedRaw = selectedOption ? String(selectedOption.textContent || '') : '';
          const roleName = cleanRoleName(selectedRaw);
          const finalLabel = roleName || fallback;
          labelNode.textContent = finalLabel;
          item.setAttribute('title', finalLabel);
        }};
        const setRoleIncomeCard = (target) => {{
          const key = String(target || '').trim();
          const resolved = roleIncomeItems.some((el) => String(el.dataset.riTarget || '') === key)
            ? key
            : String(roleIncomeItems[0]?.dataset.riTarget || '0');
          roleIncomeItems.forEach((el) => el.classList.toggle('active', String(el.dataset.riTarget || '') === resolved));
          roleIncomeCards.forEach((el) => el.classList.toggle('active', String(el.dataset.riCard || '') === resolved));
        }};
        const setRoleCardInputsDisabled = (disabled) => {{
          roleIncomeCards.forEach((card) => {{
            const controls = Array.from(card.querySelectorAll('input, select, textarea, button'));
            controls.forEach((control) => {{
              if (
                control instanceof HTMLInputElement ||
                control instanceof HTMLSelectElement ||
                control instanceof HTMLTextAreaElement ||
                control instanceof HTMLButtonElement
              ) {{
                control.disabled = Boolean(disabled);
              }}
            }});
            card.classList.toggle('is-disabled', Boolean(disabled));
          }});
        }};
        const setRoleIncomeAddFeedback = (message, tone = '') => {{
          if (!(roleIncomeAddSlotFeedback instanceof HTMLElement)) return;
          const safeMessage = String(message || '').trim();
          roleIncomeAddSlotFeedback.classList.remove('warn', 'ok');
          if (!safeMessage) {{
            roleIncomeAddSlotFeedback.hidden = true;
            roleIncomeAddSlotFeedback.textContent = '';
            return;
          }}
          if (tone === 'warn' || tone === 'ok') roleIncomeAddSlotFeedback.classList.add(tone);
          roleIncomeAddSlotFeedback.hidden = false;
          roleIncomeAddSlotFeedback.textContent = safeMessage;
        }};
        const updateRoleIncomeCapacityUi = () => {{
          const usedCount = getUsedRoleSlotCount();
          const remainingCount = Math.max(0, roleIncomeSlotLimit - usedCount);
          if (collectableModeButton instanceof HTMLElement) {{
            const meta = collectableModeButton.querySelector('span');
            if (meta instanceof HTMLElement) meta.textContent = `${{remainingCount}} remaining`;
          }}
          if (roleIncomeSlotCounter instanceof HTMLElement) {{
            roleIncomeSlotCounter.textContent = `${{usedCount}} / ${{roleIncomeSlotLimit}} slots used`;
          }}
          const mode = roleIncomeMode === 'automatic' ? 'automatic' : 'collectable';
          const enabled = roleIncomeEnabledToggle instanceof HTMLInputElement ? roleIncomeEnabledToggle.checked : true;
          const canAdd = mode === 'collectable' && enabled;
          if (roleIncomeAddSlotBtn instanceof HTMLButtonElement) {{
            roleIncomeAddSlotBtn.disabled = !canAdd || remainingCount <= 0;
          }}
          if (!canAdd) setRoleIncomeAddFeedback('');
        }};
        let roleIncomeMode = String(roleModeButtons.find((btn) => btn.classList.contains('active'))?.dataset.riMode || 'collectable').toLowerCase();
        const applyRoleIncomeState = () => {{
          const mode = roleIncomeMode === 'automatic' ? 'automatic' : 'collectable';
          const enabled = roleIncomeEnabledToggle instanceof HTMLInputElement ? roleIncomeEnabledToggle.checked : true;
          roleModeButtons.forEach((btn) => {{
            const buttonMode = String(btn.dataset.riMode || 'collectable').toLowerCase();
            btn.classList.toggle('active', buttonMode === mode);
          }});
          if (roleIncomeSlotList instanceof HTMLElement) {{
            roleIncomeSlotList.classList.toggle('is-disabled', mode !== 'collectable');
          }}
          setRoleCardInputsDisabled(mode !== 'collectable' || !enabled);
          if (roleIncomeModeHint instanceof HTMLElement) {{
            if (mode !== 'collectable') {{
              roleIncomeModeHint.hidden = false;
              roleIncomeModeHint.textContent = 'Automatic mode is coming soon. Please use Collectable mode for now.';
            }} else if (!enabled) {{
              roleIncomeModeHint.hidden = false;
              roleIncomeModeHint.textContent = 'Role Income is disabled. Turn it on to edit slots.';
            }} else {{
              roleIncomeModeHint.hidden = true;
              roleIncomeModeHint.textContent = '';
            }}
          }}
          updateRoleIncomeCapacityUi();
        }};
        roleIncomeItems.forEach((el) => {{
          el.addEventListener('click', () => setRoleIncomeCard(el.dataset.riTarget || '0'));
          const key = String(el.dataset.riTarget || '0');
          const roleSelect = getRoleSelectByKey(key);
          roleSelect?.addEventListener('change', () => {{
            updateRoleIncomeSlotLabel(key);
            updateRoleIncomeCapacityUi();
          }});
          updateRoleIncomeSlotLabel(key);
        }});
        Array.from(form.querySelectorAll('.econ-role-delete-btn[data-ri-delete]')).forEach((btn) => {{
          btn.addEventListener('click', () => {{
            const key = String(btn.getAttribute('data-ri-delete') || '').trim();
            if (!key) return;
            const roleSelect = form.querySelector(`[name="role_income_role_${{key}}"]`);
            const amountInput = form.querySelector(`[name="role_income_amount_${{key}}"]`);
            const cooldownInput = form.querySelector(`[name="role_income_cooldown_${{key}}"]`);
            const channelSelect = form.querySelector(`[name="role_income_channel_${{key}}"]`);
            if (roleSelect instanceof HTMLSelectElement) {{
              roleSelect.value = '';
              roleSelect.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            if (amountInput instanceof HTMLInputElement) {{
              amountInput.value = '0';
              amountInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
              amountInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            if (cooldownInput instanceof HTMLInputElement) {{
              cooldownInput.value = '3600';
              cooldownInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
              cooldownInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            if (channelSelect instanceof HTMLSelectElement) {{
              channelSelect.value = '';
              channelSelect.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            updateRoleIncomeSlotLabel(key);
            setRoleIncomeCard(key);
            updateRoleIncomeCapacityUi();
            setRoleIncomeAddFeedback(`Slot #${{Number(key) + 1}} cleared`, 'ok');
          }});
        }});
        roleIncomeAddSlotBtn?.addEventListener('click', () => {{
          const mode = roleIncomeMode === 'automatic' ? 'automatic' : 'collectable';
          const enabled = roleIncomeEnabledToggle instanceof HTMLInputElement ? roleIncomeEnabledToggle.checked : true;
          if (mode !== 'collectable') {{
            setRoleIncomeAddFeedback('Please switch to Collectable mode first', 'warn');
            return;
          }}
          if (!enabled) {{
            setRoleIncomeAddFeedback('Enable Role Income before adding a new slot', 'warn');
            return;
          }}
          const nextEmptyItem = roleIncomeItems.find((item) => {{
            const key = String(item.dataset.riTarget || '').trim();
            return key !== '' && !isRoleSlotUsed(key);
          }});
          if (!(nextEmptyItem instanceof HTMLElement)) {{
            const usedCount = getUsedRoleSlotCount();
            const remainingCount = Math.max(0, roleIncomeSlotLimit - usedCount);
            if (remainingCount > 0) {{
              setRoleIncomeAddFeedback('All visible slots are filled. Save changes and reopen this page to unlock more slots.', 'warn');
            }} else {{
              setRoleIncomeAddFeedback('Role Income slot limit reached', 'warn');
            }}
            return;
          }}
          const key = String(nextEmptyItem.dataset.riTarget || '0').trim();
          setRoleIncomeCard(key);
          updateRoleIncomeSlotLabel(key);
          updateRoleIncomeCapacityUi();
          setRoleIncomeAddFeedback(`Opened Slot #${{Number(key) + 1}}. Select a role to activate it.`, 'ok');
          const roleSelect = getRoleSelectByKey(key);
          if (roleSelect instanceof HTMLSelectElement) {{
            try {{
              roleSelect.focus({{ preventScroll: true }});
            }} catch {{
              roleSelect.focus();
            }}
          }}
        }});
        roleModeButtons.forEach((btn) => {{
          btn.addEventListener('click', () => {{
            roleIncomeMode = String(btn.dataset.riMode || 'collectable').toLowerCase();
            applyRoleIncomeState();
          }});
        }});
        roleIncomeEnabledToggle?.addEventListener('change', applyRoleIncomeState);
        setRoleIncomeCard(roleIncomeItems[0]?.dataset.riTarget || '0');
        updateRoleIncomeCapacityUi();
        applyRoleIncomeState();

        const openStoreCreateModal = document.getElementById('openStoreCreateModal');
        const closeStoreCreateModal = document.getElementById('closeStoreCreateModal');
        const storeCreateModal = document.getElementById('storeCreateModal');
        openStoreCreateModal?.addEventListener('click', () => storeCreateModal?.classList.add('show'));
        closeStoreCreateModal?.addEventListener('click', () => storeCreateModal?.classList.remove('show'));
        storeCreateModal?.addEventListener('click', (ev) => {{
          if (ev.target === storeCreateModal) storeCreateModal.classList.remove('show');
        }});

        const storeBtn = document.getElementById('storeOptionsButton');
        const storeMenu = document.getElementById('storeOptionsMenu');
        storeBtn?.addEventListener('click', (ev) => {{
          ev.preventDefault();
          if (!storeMenu) return;
          storeMenu.classList.toggle('show');
        }});
        document.addEventListener('click', (ev) => {{
          if (!storeMenu || !storeBtn) return;
          const target = ev.target;
          if (!(target instanceof Element)) return;
          if (storeMenu.contains(target) || storeBtn.contains(target)) return;
          storeMenu.classList.remove('show');
        }});

        const saveBar = document.getElementById('economySaveBar');
        const saveBarText = document.getElementById('economySaveBarText');
        const validationNotice = document.getElementById('econFormValidationNotice');
        const economyChannelsEnabledToggle = form.querySelector('input[name="economy_channels_enabled"]');
        const chatMoneyEnabledToggle = form.querySelector('input[name="chat_money_enabled"]');
        const showValidationNotice = (message) => {{
          if (!(validationNotice instanceof HTMLElement)) return;
          const text = String(message || '').trim();
          if (!text) {{
            validationNotice.hidden = true;
            validationNotice.textContent = '';
            return;
          }}
          validationNotice.hidden = false;
          validationNotice.textContent = text;
          try {{
            validationNotice.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
          }} catch {{
          }}
        }};
        const buildFormSignature = () => {{
          const data = new FormData(form);
          const pairs = [];
          for (const [key, value] of data.entries()) {{
            pairs.push(`${{key}}=${{String(value)}}`);
          }}
          pairs.sort();
          return pairs.join('&');
        }};
        const setDirtyState = (isDirty) => {{
          if (!saveBar) return;
          saveBar.hidden = !isDirty;
          if (saveBarText) {{
            saveBarText.textContent = isDirty ? 'Unsaved changes detected' : 'All changes saved';
          }}
        }};
        let initialSignature = buildFormSignature();
        const refreshDirtyState = () => {{
          setDirtyState(buildFormSignature() !== initialSignature);
        }};
        form.addEventListener('input', refreshDirtyState);
        form.addEventListener('change', refreshDirtyState);
        form.addEventListener('submit', (ev) => {{
          const issues = [];
          const economySelectedCount = economyCommandChecks.filter((el) => el instanceof HTMLInputElement && el.checked).length;
          if (
            economyChannelsEnabledToggle instanceof HTMLInputElement &&
            economyChannelsEnabledToggle.checked &&
            !(economyAllChannelsToggle instanceof HTMLInputElement && economyAllChannelsToggle.checked) &&
            economySelectedCount === 0
          ) {{
            issues.push('เปิดการจำกัดห้อง Economy อยู่ แต่ยังไม่ได้เลือกห้องสำหรับคำสั่ง');
          }}
          const chatSelectedCount = channelChecks.filter((el) => el instanceof HTMLInputElement && el.checked).length;
          if (
            chatMoneyEnabledToggle instanceof HTMLInputElement &&
            chatMoneyEnabledToggle.checked &&
            !(allChannelToggle instanceof HTMLInputElement && allChannelToggle.checked) &&
            chatSelectedCount === 0
          ) {{
            issues.push('เปิด Chat Money อยู่ แต่ยังไม่ได้เลือกห้องสำหรับรับเงินจากแชต');
          }}
          const rangePairs = [
            ['work_payout_min', 'work_payout_max', 'Work payout'],
            ['slut_payout_min', 'slut_payout_max', 'Slut payout'],
            ['crime_payout_min', 'crime_payout_max', 'Crime payout'],
            ['rob_payout_min', 'rob_payout_max', 'Rob payout'],
            ['chat_money_min', 'chat_money_max', 'Chat money'],
            ['bet_min', 'bet_max', 'Bet limit'],
          ];
          rangePairs.forEach(([minKey, maxKey, label]) => {{
            const minInput = form.querySelector(`[name="${{minKey}}"]`);
            const maxInput = form.querySelector(`[name="${{maxKey}}"]`);
            if (!(minInput instanceof HTMLInputElement) || !(maxInput instanceof HTMLInputElement)) return;
            const minValue = Number(minInput.value || 0);
            const maxValue = Number(maxInput.value || 0);
            if (Number.isFinite(minValue) && Number.isFinite(maxValue) && minValue > maxValue) {{
              issues.push(`${{label}}: min value must be less than or equal to max value`);
            }}
          }});
          if (issues.length) {{
            ev.preventDefault();
            const firstIssue = issues[0];
            showValidationNotice(firstIssue);
            if (firstIssue.toLowerCase().includes('chat money')) activatePage('chat_money');
            else if (firstIssue.toLowerCase().includes('economy')) activatePage('command_channels');
            return;
          }}
          showValidationNotice('');
          if (saveBarText) saveBarText.textContent = 'Saving...';
        }});
        refreshDirtyState();
      }})();

