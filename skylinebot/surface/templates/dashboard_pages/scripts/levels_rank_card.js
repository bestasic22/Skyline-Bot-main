(() => {{
  const entries = {rank_json};
  const select = document.getElementById('dashboardRankMemberSelect');
  if (!select || !Array.isArray(entries) || !entries.length) return;
  const nameEl = document.getElementById('dashboardRankName');
  const tagEl = document.getElementById('dashboardRankTag');
  const avatarEl = document.getElementById('dashboardRankAvatar');
  const rankBadgeEl = document.getElementById('dashboardRankBadge');
  const levelBadgeEl = document.getElementById('dashboardLevelBadge');
  const totalXpEl = document.getElementById('dashboardRankTotalXp');
  const nextXpEl = document.getElementById('dashboardRankNextXp');
  const progressTextEl = document.getElementById('dashboardRankProgressText');
  const progressBarEl = document.getElementById('dashboardRankProgressBar');
  const fmt = (n) => Number(n || 0).toLocaleString('th-TH');
  const xpNeed = (level) => Math.max(100, 80 + Math.floor((Number(level || 0) ** 2) * 35));
  const renderEntry = (entry) => {{
    if (!entry) return;
    const level = Number(entry.level || 0);
    const totalXp = Number(entry.xp || 0);
    const floorXp = level > 0 ? xpNeed(level) : 0;
    const nextXp = xpNeed(level + 1);
    const span = Math.max(1, nextXp - floorXp);
    const progress = Math.max(0, totalXp - floorXp);
    const percent = Math.max(0, Math.min(100, (progress / span) * 100));
    if (nameEl) nameEl.textContent = String(entry.name || 'Unknown');
    if (tagEl) tagEl.textContent = String(entry.tag || '-');
    if (avatarEl) avatarEl.setAttribute('src', String(entry.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'));
    if (rankBadgeEl) rankBadgeEl.textContent = `Rank #${{Number(entry.rank || 0)}}`;
    if (levelBadgeEl) levelBadgeEl.textContent = `Level ${{level}}`;
    if (totalXpEl) totalXpEl.textContent = fmt(totalXp);
    if (nextXpEl) nextXpEl.textContent = fmt(Math.max(0, nextXp - totalXp));
    if (progressTextEl) progressTextEl.textContent = `${{percent.toFixed(1)}}%`;
    if (progressBarEl) progressBarEl.style.width = `${{percent.toFixed(2)}}%`;
  }};
  renderEntry(entries.find((item) => String(item.user_id) === String(select.value)) || entries[0]);
  select.addEventListener('change', () => {{
    renderEntry(entries.find((item) => String(item.user_id) === String(select.value)) || entries[0]);
  }});
}})();
