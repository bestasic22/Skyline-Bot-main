(() => {{
  const tbody = document.getElementById('controlPanelAuditRows');
  if (!tbody) return;

  const searchInput = document.getElementById('controlPanelAuditSearchInput');
  const emptyState = document.getElementById('controlPanelAuditEmpty');
  const pageLabel = document.getElementById('controlPanelAuditCurrentPage');
  const prevBtn = document.getElementById('controlPanelAuditPrevPageBtn');
  const nextBtn = document.getElementById('controlPanelAuditNextPageBtn');

  let currentPage = 1;
  const pageSize = 50;

  const collectRows = () => Array.from(tbody.querySelectorAll('tr[data-control-row]'));

  const applyPagination = () => {{
    const q = String(searchInput?.value || '').trim().toLowerCase();
    const rows = collectRows();
    const matched = rows.filter((row) => {{
      const user = String(row.getAttribute('data-user') || '').toLowerCase();
      const action = String(row.getAttribute('data-action') || '').toLowerCase();
      const target = String(row.getAttribute('data-target') || '').toLowerCase();
      if (!q) return true;
      return user.includes(q) || action.includes(q) || target.includes(q);
    }});

    const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));
    currentPage = Math.min(Math.max(1, currentPage), totalPages);
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;

    rows.forEach((row) => (row.style.display = 'none'));
    matched.slice(start, end).forEach((row) => (row.style.display = ''));

    if (emptyState) emptyState.style.display = matched.length ? 'none' : '';
    if (pageLabel) pageLabel.textContent = `${{currentPage}}/${{totalPages}}`;
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
  }};

  searchInput?.addEventListener('input', () => {{
    currentPage = 1;
    applyPagination();
  }});

  prevBtn?.addEventListener('click', () => {{
    currentPage = Math.max(1, currentPage - 1);
    applyPagination();
  }});

  nextBtn?.addEventListener('click', () => {{
    currentPage += 1;
    applyPagination();
  }});

  applyPagination();
}})();
