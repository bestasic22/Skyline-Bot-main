const i18nRegistry =
  window.SKYLINE_DASHBOARD_I18N && typeof window.SKYLINE_DASHBOARD_I18N === "object"
    ? window.SKYLINE_DASHBOARD_I18N
    : {{}};
const fallbackDict = i18nRegistry.th && typeof i18nRegistry.th === "object" ? i18nRegistry.th : {{}};

function resolveLanguage() {{
  const lang = String(document.documentElement.lang || "th").toLowerCase();
  return lang === "en" ? "en" : "th";
}}

function t(key, fallback) {{
  const lang = resolveLanguage();
  const activeDict =
    i18nRegistry[lang] && typeof i18nRegistry[lang] === "object"
      ? i18nRegistry[lang]
      : {{}};
  const translated = activeDict[key] ?? fallbackDict[key];
  return typeof translated === "string" && translated.trim()
    ? translated
    : String(fallback || "");
}}

const COMMAND_FAVORITE_KEY = 'skyline_cmd_favorites_{current_guild["id"]}';
      let favoriteCommands = new Set();
      let activeCommandCategory = '';

      function loadCommandFavorites() {{
        try {{
          const raw = localStorage.getItem(COMMAND_FAVORITE_KEY);
          const parsed = JSON.parse(raw || '[]');
          if (Array.isArray(parsed)) {{
            favoriteCommands = new Set(parsed.map((v) => String(v || '').trim().toLowerCase()).filter(Boolean));
          }} else {{
            favoriteCommands = new Set();
          }}
        }} catch (_) {{
          favoriteCommands = new Set();
        }}
      }}

      function saveCommandFavorites() {{
        try {{
          localStorage.setItem(COMMAND_FAVORITE_KEY, JSON.stringify(Array.from(favoriteCommands)));
        }} catch (_) {{}}
      }}

      function applyFavoriteStateToButtons() {{
        document.querySelectorAll('[data-fav-toggle]').forEach((btn) => {{
          const name = String(btn.getAttribute('data-command-name') || '').trim().toLowerCase();
          const active = !!name && favoriteCommands.has(name);
          btn.classList.toggle('active', active);
          btn.setAttribute('aria-pressed', active ? 'true' : 'false');
          const label = active
            ? t("cmdall_fav_remove", "Remove from favorites")
            : t("cmdall_fav_add", "Add to favorites");
          btn.setAttribute('title', label);
          btn.setAttribute('aria-label', label);
        }});
      }}

      function renderFavoriteCommands() {{
        const wrap = document.getElementById('commandFavoriteList');
        const clearBtn = document.getElementById('commandFavoriteClearBtn');
        if (!wrap) return;
        const rows = Array.from(document.querySelectorAll('[data-command-row]'));
        const cards = [];
        rows.forEach((row) => {{
          const btn = row.querySelector('[data-fav-toggle]');
          const title = row.querySelector('.cmd-title');
          const desc = row.querySelector('.cmd-desc');
          if (!btn || !title) return;
          const name = String(btn.getAttribute('data-command-name') || '').trim().toLowerCase();
          if (!name || !favoriteCommands.has(name)) return;
          cards.push(`
            <article class="cmd-favorite-card">
              <div class="cmd-favorite-main">
                <strong>${{title.textContent || name}}</strong>
                <small>${{(desc?.textContent || '').trim() || t("cmdall_no_description", "No description")}}</small>
              </div>
              <div class="cmd-favorite-actions">
                <button type="button" class="cmd-favorite-open" data-favorite-open="${{name}}">${{t("cmdall_open", "Open")}}</button>
                <button type="button" class="cmd-favorite-remove" data-favorite-remove="${{name}}">${{t("cmdall_remove", "Remove")}}</button>
              </div>
            </article>
          `);
        }});
        wrap.innerHTML = cards.length
          ? cards.join('')
          : `<div class="notice">${{t("cmdall_no_favorites", "No favorites yet. Press heart to pin commands here.")}}</div>`;
        if (clearBtn) clearBtn.style.display = cards.length ? '' : 'none';
      }}

      function toggleCommandFavorite(event, commandName) {{
        if (event) {{
          event.preventDefault();
          event.stopPropagation();
        }}
        const name = String(commandName || '').trim().toLowerCase();
        if (!name) return;
        if (favoriteCommands.has(name)) {{
          favoriteCommands.delete(name);
        }} else {{
          favoriteCommands.add(name);
        }}
        saveCommandFavorites();
        applyFavoriteStateToButtons();
        renderFavoriteCommands();
      }}

      function focusFavoriteCommand(commandName) {{
        const name = String(commandName || '').trim().toLowerCase();
        if (!name) return;
        const targetBtn = document.querySelector(`[data-fav-toggle][data-command-name="${{CSS.escape(name)}}"]`);
        const row = targetBtn ? targetBtn.closest('[data-command-row]') : null;
        if (!row) return;
        row.open = true;
        row.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      }}

      function setCommandCategory(cat) {{
        activeCommandCategory = cat || '';
        document.querySelectorAll('.cmd-cat-tab').forEach((btn) => {{
          const current = btn.getAttribute('data-cat-tab') || '';
          btn.classList.toggle('active', current === activeCommandCategory);
        }});
        filterCommandRows();
      }}

      function filterCommandRows() {{
        const q = (document.getElementById('commandAllSearch')?.value || '').toLowerCase().trim();
        let visible = 0;
        document.querySelectorAll('[data-command-row]').forEach((row) => {{
          const searchText = (row.getAttribute('data-search') || '').toLowerCase();
          const rowCategory = row.getAttribute('data-category') || '';
          const passCategory = activeCommandCategory === '' || rowCategory === activeCommandCategory;
          const passSearch = !q || searchText.includes(q);
          const ok = passCategory && passSearch;
          row.style.display = ok ? '' : 'none';
          if (ok) visible += 1;
        }});
        const empty = document.getElementById('commandAllEmpty');
        if (empty) empty.style.display = visible ? 'none' : '';
      }}

      document.querySelectorAll('.cmd-cat-tab').forEach((btn) => {{
        btn.addEventListener('click', () => {{
          setCommandCategory(btn.getAttribute('data-cat-tab') || '');
        }});
      }});

      document.querySelectorAll('[data-fav-toggle]').forEach((btn) => {{
        btn.addEventListener('click', (event) => {{
          toggleCommandFavorite(event, btn.getAttribute('data-command-name') || '');
        }});
      }});

      document.addEventListener('click', (event) => {{
        const removeBtn = event.target.closest('[data-favorite-remove]');
        if (removeBtn) {{
          toggleCommandFavorite(event, removeBtn.getAttribute('data-favorite-remove') || '');
          return;
        }}
        const openBtn = event.target.closest('[data-favorite-open]');
        if (openBtn) {{
          event.preventDefault();
          focusFavoriteCommand(openBtn.getAttribute('data-favorite-open') || '');
        }}
      }});

      const clearFavoritesBtn = document.getElementById('commandFavoriteClearBtn');
      if (clearFavoritesBtn) {{
        clearFavoritesBtn.addEventListener('click', () => {{
          favoriteCommands = new Set();
          saveCommandFavorites();
          applyFavoriteStateToButtons();
          renderFavoriteCommands();
        }});
      }}

      loadCommandFavorites();
      applyFavoriteStateToButtons();
      renderFavoriteCommands();

      window.addEventListener("dashboard:language-change", () => {{
        applyFavoriteStateToButtons();
        renderFavoriteCommands();
      }});
