(() => {{
        const tbody = document.getElementById('moderationLogRows');
        if (!tbody) return;
        const searchInput = document.getElementById('logSearchInput');
        const emptyState = document.getElementById('moderationLogEmpty');
        const pageLabel = document.getElementById('logCurrentPage');
        const prevBtn = document.getElementById('logPrevPageBtn');
        const nextBtn = document.getElementById('logNextPageBtn');
        const filterButtons = Array.from(document.querySelectorAll('[data-log-filter]'));
        let currentFilter = 'all';
        let currentPage = 1;
        const pageSize = 50;
        const collectRows = () => Array.from(tbody.querySelectorAll('tr')).filter((row) => !row.hasAttribute('data-empty-row'));
        const applyFilter = () => {{
          const q = String(searchInput?.value || '').trim().toLowerCase();
          const allRows = collectRows();
          const emptyRows = Array.from(tbody.querySelectorAll('tr[data-empty-row]'));
          emptyRows.forEach((row) => (row.style.display = 'none'));
          const matched = allRows.filter((row) => {{
            const action = String(row.getAttribute('data-action') || 'all').toLowerCase();
            const member = String(row.getAttribute('data-member') || '').toLowerCase();
            const passAction = currentFilter === 'all' || action === currentFilter;
            const passSearch = !q || member.includes(q);
            return passAction && passSearch;
          }});
          const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));
          currentPage = Math.min(Math.max(1, currentPage), totalPages);
          const start = (currentPage - 1) * pageSize;
          const end = start + pageSize;
          allRows.forEach((row) => (row.style.display = 'none'));
          matched.slice(start, end).forEach((row) => (row.style.display = ''));
          if (emptyState) emptyState.style.display = matched.length ? 'none' : '';
          if (pageLabel) pageLabel.textContent = `${{currentPage}}/${{totalPages}}`;
          if (prevBtn) prevBtn.disabled = currentPage <= 1;
          if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
        }};
        filterButtons.forEach((button) => {{
          button.addEventListener('click', () => {{
            currentFilter = String(button.getAttribute('data-log-filter') || 'all');
            currentPage = 1;
            filterButtons.forEach((item) => {{
              const isActive = String(item.getAttribute('data-log-filter') || '') === currentFilter;
              item.className = isActive ? 'primary-btn log-filter-btn is-active' : 'ghost-btn log-filter-btn';
              item.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            }});
            applyFilter();
          }});
        }});
        searchInput?.addEventListener('input', () => {{
          currentPage = 1;
          applyFilter();
        }});
        prevBtn?.addEventListener('click', () => {{
          currentPage = Math.max(1, currentPage - 1);
          applyFilter();
        }});
        nextBtn?.addEventListener('click', () => {{
          currentPage += 1;
          applyFilter();
        }});
        applyFilter();
      }})();
