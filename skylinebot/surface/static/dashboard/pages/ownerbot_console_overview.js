(() => {
  const runtimeStatusShell = document.getElementById('ownerbotRuntimeStatusShell');
  if (!runtimeStatusShell) return;
  const OWNERBOT_OVERVIEW_SCROLL_KEY = 'ownerbot.console.overview.scroll.v1';
  const OWNERBOT_OVERVIEW_SCROLL_TTL_MS = 2 * 60 * 1000;

  const runtimeStatusLabel = document.getElementById('ownerbotRuntimeStatusLabel');
  const runtimeStatusLevel = document.getElementById('ownerbotRuntimeStatusLevel');
  const runtimeStatusMessage = document.getElementById('ownerbotRuntimeStatusMessage');
  const runtimeStatusMeta = document.getElementById('ownerbotRuntimeStatusMeta');
  const statusForm = document.getElementById('ownerbotStatusForm');
  const statusOverrideLevelInput = document.getElementById('ownerbotStatusOverrideLevel');
  const statusOverrideActivityInput = document.getElementById('ownerbotStatusOverrideActivity');
  const statusOverrideMessageInput = document.getElementById('ownerbotStatusOverrideMessage');
  const statusAutoResetButton = document.getElementById('ownerbotStatusAutoResetButton');
  const mongoHealthyCount = document.getElementById('ownerbotMongoHealthyCount');
  const mongoTotalCount = document.getElementById('ownerbotMongoTotalCount');
  const mongoQuotaCount = document.getElementById('ownerbotMongoQuotaCount');
  const mongoRowsWrap = document.getElementById('ownerbotMongoRows');
  const redeemRowsWrap = document.getElementById('ownerbotRecentRedeemRows');
  const liveStatus = document.getElementById('ownerbotOverviewLiveStatus');

  const seedNode = document.getElementById('ownerbotOverviewSeed');
  let overviewSeed = {};
  let latestRuntimePayload = {};
  try {
    overviewSeed = JSON.parse(seedNode?.textContent || '{}') || {};
  } catch (_error) {
    overviewSeed = {};
  }

  const kpiNodes = {
    total_codes: document.querySelector('[data-ownerbot-kpi="total_codes"]'),
    total_unclaimed: document.querySelector('[data-ownerbot-kpi="total_unclaimed"]'),
    total_claimed: document.querySelector('[data-ownerbot-kpi="total_claimed"]'),
    total_guilds: document.querySelector('[data-ownerbot-kpi="total_guilds"]'),
    disabled_commands_count: document.querySelector('[data-ownerbot-kpi="disabled_commands_count"]'),
    hidden_tabs_count: document.querySelector('[data-ownerbot-kpi="hidden_tabs_count"]'),
    total_wallet_users: document.querySelector('[data-ownerbot-kpi="total_wallet_users"]'),
    wallet_balance_total_text: document.querySelector('[data-ownerbot-kpi="wallet_balance_total_text"]'),
    wallet_positive_users: document.querySelector('[data-ownerbot-kpi="wallet_positive_users"]'),
    whitelist_count: document.querySelector('[data-ownerbot-kpi="whitelist_count"]'),
    blacklist_count: document.querySelector('[data-ownerbot-kpi="blacklist_count"]'),
    tester_guild_count: document.querySelector('[data-ownerbot-kpi="tester_guild_count"]'),
  };

  const writeOverviewScrollState = () => {
    try {
      const root = document.scrollingElement || document.documentElement;
      const payload = {
        x: Number(window.scrollX || root?.scrollLeft || 0),
        y: Number(window.scrollY || root?.scrollTop || 0),
        at: Date.now(),
        path: String(window.location.pathname || ''),
      };
      window.sessionStorage.setItem(OWNERBOT_OVERVIEW_SCROLL_KEY, JSON.stringify(payload));
    } catch (_error) {
    }
  };

  const restoreOverviewScrollState = () => {
    try {
      const raw = window.sessionStorage.getItem(OWNERBOT_OVERVIEW_SCROLL_KEY);
      if (!raw) return;
      const payload = JSON.parse(raw);
      const ageMs = Date.now() - Number(payload?.at || 0);
      const samePath = String(payload?.path || '') === String(window.location.pathname || '');
      if (!samePath || !Number.isFinite(ageMs) || ageMs < 0 || ageMs > OWNERBOT_OVERVIEW_SCROLL_TTL_MS) {
        window.sessionStorage.removeItem(OWNERBOT_OVERVIEW_SCROLL_KEY);
        return;
      }
      const nextX = Math.max(0, Number(payload?.x || 0));
      const nextY = Math.max(0, Number(payload?.y || 0));
      const applyScroll = () => {
        window.scrollTo({
          left: nextX,
          top: nextY,
          behavior: 'auto',
        });
      };
      applyScroll();
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(applyScroll);
      });
      window.sessionStorage.removeItem(OWNERBOT_OVERVIEW_SCROLL_KEY);
    } catch (_error) {
      try {
        window.sessionStorage.removeItem(OWNERBOT_OVERVIEW_SCROLL_KEY);
      } catch (_err2) {
      }
    }
  };

  const bindOverviewScrollPersistence = () => {
    const forms = Array.from(document.querySelectorAll('form[action^="/dashboard/admin/ownerbot"]'));
    forms.forEach((formNode) => {
      if (!(formNode instanceof HTMLFormElement)) return;
      formNode.addEventListener('submit', () => {
        writeOverviewScrollState();
      }, { capture: true });
    });

    window.addEventListener('beforeunload', writeOverviewScrollState);
    window.addEventListener('pagehide', writeOverviewScrollState);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        writeOverviewScrollState();
      }
    });
    window.addEventListener('pageshow', () => {
      restoreOverviewScrollState();
    });
  };
  const normalizeRuntimeLevel = (value) => String(value || '').trim().toLowerCase();
  const allowedPresenceLevels = ['online', 'idle', 'dnd', 'offline'];
  const allowedPresenceActivities = ['playing', 'streaming', 'listening', 'watching', 'competing'];
  const normalizePresenceLevel = (rawValue) => {
    const token = String(rawValue || '').trim().toLowerCase();
    if (token === 'live' || token === 'ok' || token === 'running') return 'online';
    if (token === 'stream' || token === 'starting' || token === 'reloading' || token === 'reload') return 'idle';
    if (token === 'ded' || token === 'maintenance' || token === 'error' || token === 'err') return 'dnd';
    if (token === 'auto' || allowedPresenceLevels.includes(token)) return token;
    return 'auto';
  };
  const normalizePresenceActivity = (rawValue) => {
    const token = String(rawValue || '').trim().toLowerCase();
    if (token === 'custom') return 'watching';
    if (token === 'auto' || allowedPresenceActivities.includes(token)) return token;
    return 'auto';
  };
  const parseLegacyDisplayChoice = (rawValue) => {
    const token = String(rawValue || '').trim().toLowerCase();
    if (token === 'auto') {
      return { level: 'auto', activity: 'auto' };
    }
    if (allowedPresenceLevels.includes(token)) {
      return { level: token, activity: 'auto' };
    }
    if (allowedPresenceActivities.includes(token)) {
      return { level: 'online', activity: token };
    }
    return { level: 'auto', activity: 'auto' };
  };
  const parseOverrideMessages = (rawValue) =>
    String(rawValue || '')
      .split(/\r?\n/g)
      .map((line) => String(line || '').trim().replace(/\s+/g, ' '))
      .filter((line) => Boolean(line))
      .slice(0, 12)
      .map((line) => line.slice(0, 120));
  const escapeHtml = (value) =>
    String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');

  const runtimeAgeText = (updatedAtRaw) => {
    const updatedAt = Number(updatedAtRaw);
    if (!Number.isFinite(updatedAt) || updatedAt <= 0) return 'No runtime timestamp yet';
    const now = Math.floor(Date.now() / 1000);
    const age = Math.max(0, now - Math.floor(updatedAt));
    return 'Last update ' + String(age) + 's ago';
  };

  const classifyRuntimeLevel = (rawLevel) => {
    const level = normalizeRuntimeLevel(rawLevel);
    if (['offline', 'invisible'].includes(level)) {
      return { tone: 'err', label: 'OFFLINE', level: 'offline' };
    }
    if (level === 'idle') {
      return { tone: 'loading', label: 'IDLE', level: 'idle' };
    }
    if (level === 'dnd') {
      return { tone: 'err', label: 'DND', level: 'dnd' };
    }
    if (['stream', 'starting', 'restart', 'restarting', 'reload', 'reloading', 'unknown'].includes(level)) {
      return { tone: 'loading', label: 'สตรีม', level: 'stream' };
    }
    if (['ded', 'maintenance', 'stopped', 'outage', 'auth_error', 'degraded', 'error', 'err'].includes(level)) {
      return { tone: 'err', label: 'DED', level: 'ded' };
    }
    if (level === 'live') {
      return { tone: 'ok', label: 'LIVE', level: 'live' };
    }
    if (['ok', 'online', 'running'].includes(level)) {
      return { tone: 'ok', label: 'ONLINE', level: 'online' };
    }
    return { tone: 'unknown', label: 'UNKNOWN', level: 'unknown' };
  };

  const readModePolicy = () => {
    const shellMode = normalizeRuntimeLevel(runtimeStatusShell?.getAttribute('data-ownerbot-guild-mode')) || 'all';
    const shellTesterEnabled = ['1', 'true', 'on', 'yes'].includes(String(runtimeStatusShell?.getAttribute('data-ownerbot-tester-enabled') || '').trim().toLowerCase());
    const shellDisplay = normalizeRuntimeLevel(runtimeStatusShell?.getAttribute('data-ownerbot-status-override-display') || '');
    const shellLevel = normalizePresenceLevel(runtimeStatusShell?.getAttribute('data-ownerbot-status-override-level') || '');
    const shellActivity = normalizePresenceActivity(runtimeStatusShell?.getAttribute('data-ownerbot-status-override-activity') || '');
    const legacyDisplayChoice = parseLegacyDisplayChoice(shellDisplay);
    let overrideLevel = normalizePresenceLevel(
      statusOverrideLevelInput?.value || shellLevel || legacyDisplayChoice.level
    );
    let overrideActivity = normalizePresenceActivity(
      statusOverrideActivityInput?.value || shellActivity || legacyDisplayChoice.activity
    );
    if (overrideLevel === 'auto' && overrideActivity !== 'auto') {
      overrideLevel = 'online';
    }
    const overrideMessageRaw = String(statusOverrideMessageInput?.value || runtimeStatusShell?.getAttribute('data-ownerbot-status-override-message') || '');
    const overrideMessages = parseOverrideMessages(overrideMessageRaw);
    const overrideMessage = overrideMessages.length ? overrideMessages[0] : '';
    return {
      guildMode: shellMode,
      testerEnabled: shellTesterEnabled,
      overrideLevel,
      overrideActivity,
      overrideMessages,
      overrideMessage,
    };
  };

  const applyRuntimeStatus = (payloadRaw) => {
    const payload = payloadRaw && typeof payloadRaw === 'object' ? payloadRaw : {};
    latestRuntimePayload = payload;
    let state = classifyRuntimeLevel(payload.level);
    let message = String(payload.message || '').trim();

    if (!message) {
      if (state.level === 'ded') message = 'บอทไม่พร้อมทำงาน กำลังเร่งแก้ไขระบบ';
      else if (state.level === 'idle') message = 'Bot is idle.';
      else if (state.level === 'dnd') message = 'Do not disturb.';
      else if (state.level === 'stream') message = 'บอทกำลังเริ่มระบบ';
      else if (state.level === 'offline') message = 'บอทถูกปิดอยู่';
      else if (state.level === 'live') message = 'บอทยังไม่พร้อมทำงานทุกกิลด์';
      else if (state.level === 'online') message = 'Bot is running normally.';
      else message = 'Runtime state is not available yet.';
    }

    const policy = readModePolicy();
    if (['online', 'idle', 'dnd', 'offline'].includes(policy.overrideLevel)) {
      state = classifyRuntimeLevel(policy.overrideLevel);
      if (policy.overrideLevel === 'offline') {
        state = { tone: 'err', label: 'OFFLINE', level: 'offline' };
      }
      if (policy.overrideMessages.length > 0) {
        message = policy.overrideMessages[0];
      } else if (policy.overrideLevel === 'idle') {
        message = 'Bot is idle.';
      } else if (policy.overrideLevel === 'dnd') {
        message = 'Do not disturb.';
      } else if (policy.overrideLevel === 'offline') {
        message = 'บอทถูกปิดอยู่';
      } else if (policy.overrideActivity !== 'auto') {
        message = 'SkylineBot';
      } else {
        message = 'Bot is running normally.';
      }
    } else if (state.level === 'ded') {
      message = 'บอทไม่พร้อมทำงาน กำลังเร่งแก้ไขระบบ';
    } else if (state.level === 'stream') {
      message = 'บอทกำลังเริ่มระบบ';
    } else if (policy.testerEnabled || policy.guildMode === 'tester') {
      state = { tone: 'err', label: 'DED', level: 'ded' };
      message = 'กำลังปิดปรับปรุง';
    } else if (policy.guildMode === 'whitelist') {
      state = { tone: 'ok', label: 'LIVE', level: 'live' };
      message = 'บอทยังไม่พร้อมทำงานทุกกิลด์';
    }

    runtimeStatusShell.className = 'ownerbot-runtime-status ownerbot-runtime-status-' + String(state.tone || 'unknown');
    runtimeStatusShell.setAttribute('data-runtime-level', String(state.level || 'unknown'));
    if (runtimeStatusLabel) runtimeStatusLabel.textContent = String(state.label || 'UNKNOWN');
    if (runtimeStatusLevel) runtimeStatusLevel.textContent = String(state.level || 'unknown');
    if (runtimeStatusMessage) runtimeStatusMessage.textContent = message;
    if (runtimeStatusMeta) runtimeStatusMeta.textContent = runtimeAgeText(payload.updated_at);
  };

  const setLiveStatus = (text, isError = false) => {
    if (!liveStatus) return;
    liveStatus.textContent = String(text || '').trim();
    liveStatus.style.color = isError ? 'var(--danger, #ff8ea1)' : 'var(--muted)';
  };

  const bindStatusSubmitGuard = () => {
    if (!(statusForm instanceof HTMLFormElement)) return;
    const submitButton = statusForm.querySelector('button[type="submit"]');
    if (!(submitButton instanceof HTMLButtonElement)) return;
    statusForm.addEventListener('submit', () => {
      submitButton.disabled = true;
      submitButton.dataset.originalText = submitButton.textContent || '';
      submitButton.textContent = 'กำลังบันทึก...';
      window.setTimeout(() => {
        // Fallback in case browser does not navigate (network interruption, blocked redirect).
        submitButton.disabled = false;
        submitButton.textContent = submitButton.dataset.originalText || 'บันทึกสถานะบอท';
      }, 8000);
    });
  };

  const applyKpi = (kpiRaw) => {
    const kpi = kpiRaw && typeof kpiRaw === 'object' ? kpiRaw : {};
    Object.keys(kpiNodes).forEach((key) => {
      const node = kpiNodes[key];
      if (!node || !(key in kpi)) return;
      node.textContent = String(kpi[key] ?? '');
    });
  };

  const updateMongoRows = (mongoRaw) => {
    const mongo = mongoRaw && typeof mongoRaw === 'object' ? mongoRaw : {};
    if (mongoHealthyCount) mongoHealthyCount.textContent = String(mongo.healthy_count ?? 0);
    if (mongoTotalCount) mongoTotalCount.textContent = String(mongo.uris_count ?? 0);
    if (mongoQuotaCount) mongoQuotaCount.textContent = String(mongo.quota_warning_count ?? 0);
    if (!(mongoRowsWrap instanceof HTMLElement)) return;

    const rows = Array.isArray(mongo.rows) ? mongo.rows : [];
    if (!rows.length) {
      mongoRowsWrap.innerHTML = '<tr><td colspan="6" class="muted">No Mongo cluster data.</td></tr>';
      return;
    }

    mongoRowsWrap.innerHTML = rows.map((row) => {
      const index = Number(row?.index || 0);
      const host = String(row?.host || '-');
      const status = row?.ok ? 'ONLINE' : 'ERROR';
      const detail = String(row?.detail || '').trim();
      const latency = Number(row?.latency_ms || 0);
      const collections = Number(row?.collections_total || 0);
      const storageMb = Number(row?.storage_size_bytes || 0) / (1024 * 1024);
      const dataMb = Number(row?.data_size_bytes || 0) / (1024 * 1024);
      const label = index > 0 ? ('#' + String(index) + ' ' + host) : host;
      return '<tr>'
        + '<td>' + escapeHtml(label) + '</td>'
        + '<td' + (detail ? (' title="' + escapeHtml(detail) + '"') : '') + '>' + escapeHtml(status) + '</td>'
        + '<td>' + escapeHtml(String(Math.round(latency))) + '</td>'
        + '<td>' + escapeHtml(String(Math.round(collections))) + '</td>'
        + '<td>' + escapeHtml(String(storageMb.toFixed(2))) + '</td>'
        + '<td>' + escapeHtml(String(dataMb.toFixed(2))) + '</td>'
        + '</tr>';
    }).join('');
  };

  const updateRedeemRows = (rowsRaw) => {
    if (!(redeemRowsWrap instanceof HTMLElement)) return;
    const rows = Array.isArray(rowsRaw) ? rowsRaw : [];
    if (!rows.length) {
      redeemRowsWrap.innerHTML = '<tr><td colspan="5" class="muted">No redeem data.</td></tr>';
      return;
    }
    redeemRowsWrap.innerHTML = rows.map((row) => {
      const code = String(row?.code || '-');
      const type = String(row?.type || '-');
      const status = String(row?.status || '-');
      const created = String(row?.created_at || '-');
      const claimedBy = String(row?.claimed_by || '-');
      return '<tr>'
        + '<td><code>' + escapeHtml(code) + '</code></td>'
        + '<td>' + escapeHtml(type) + '</td>'
        + '<td>' + escapeHtml(status) + '</td>'
        + '<td>' + escapeHtml(created) + '</td>'
        + '<td>' + escapeHtml(claimedBy) + '</td>'
        + '</tr>';
    }).join('');
  };

  const charts = {};
  const CHART_IDS = ['ownerbotPlanChart', 'ownerbotMongoSizeChart', 'ownerbotMongoHealthChart'];
  const getChartTargetHeight = () => (window.matchMedia && window.matchMedia('(max-width: 720px)').matches ? 190 : 220);
  const buildMongoLabelPackFromRows = (rowsRaw) => {
    const rows = Array.isArray(rowsRaw) ? rowsRaw : [];
    const fullLabels = [];
    const shortLabels = [];
    rows.forEach((row, position) => {
      const indexRaw = Number(row?.index || 0);
      const index = Number.isFinite(indexRaw) && indexRaw > 0 ? Math.floor(indexRaw) : (position + 1);
      const host = String(row?.host || '-').trim() || '-';
      fullLabels.push('#' + String(index) + ' ' + host);
      shortLabels.push('#' + String(index));
    });
    return { fullLabels, shortLabels };
  };
  const buildMongoLabelPackFromSeed = (labelsRaw) => {
    const labels = Array.isArray(labelsRaw) ? labelsRaw : [];
    const fullLabels = [];
    const shortLabels = [];
    labels.forEach((value, position) => {
      const text = String(value || '').trim();
      const matched = text.match(/^#\s*(\d+)/i);
      const index = matched ? Number(matched[1]) : (position + 1);
      const safeIndex = Number.isFinite(index) && index > 0 ? Math.floor(index) : (position + 1);
      fullLabels.push(text || ('#' + String(safeIndex)));
      shortLabels.push('#' + String(safeIndex));
    });
    return { fullLabels, shortLabels };
  };
  const mongoTooltipTitle = (items) => {
    const first = Array.isArray(items) && items.length ? items[0] : null;
    const chart = first?.chart;
    const index = Number(first?.dataIndex ?? -1);
    const fullLabels = Array.isArray(chart?.$ownerbotFullLabels) ? chart.$ownerbotFullLabels : [];
    if (index >= 0 && index < fullLabels.length) {
      return fullLabels[index];
    }
    return String(first?.label || '-');
  };

  const lockOverviewChartLayout = () => {
    const targetHeight = getChartTargetHeight();
    const grid = document.querySelector('.ownerbot-chart-grid');
    if (grid instanceof HTMLElement) {
      grid.style.alignItems = 'start';
      grid.style.gridAutoRows = 'min-content';
    }
    CHART_IDS.forEach((canvasId) => {
      const canvas = document.getElementById(canvasId);
      if (!(canvas instanceof HTMLCanvasElement)) return;
      const wrap = canvas.closest('.ownerbot-chart-canvas-wrap');
      const card = canvas.closest('.ownerbot-chart-card');
      if (card instanceof HTMLElement) {
        card.style.minHeight = '0';
        card.style.height = 'auto';
        card.style.alignSelf = 'start';
      }
      if (wrap instanceof HTMLElement) {
        wrap.style.position = 'relative';
        wrap.style.width = '100%';
        wrap.style.overflow = 'hidden';
        wrap.style.height = String(targetHeight) + 'px';
        wrap.style.minHeight = String(targetHeight) + 'px';
        wrap.style.maxHeight = String(targetHeight) + 'px';
      }
      canvas.style.display = 'block';
      canvas.style.width = '100%';
      canvas.style.maxWidth = '100%';
      canvas.style.height = String(targetHeight) + 'px';
      canvas.style.minHeight = String(targetHeight) + 'px';
      canvas.style.maxHeight = String(targetHeight) + 'px';
    });
  };

  const resizeChartsToContainer = () => {
    const targetHeight = getChartTargetHeight();
    Object.values(charts).forEach((chart) => {
      if (!chart || !chart.canvas) return;
      const canvas = chart.canvas;
      const parent = canvas.parentElement;
      if (!(parent instanceof HTMLElement)) return;
      const nextWidth = Math.max(260, Math.floor(parent.clientWidth || canvas.clientWidth || 260));
      chart.resize(nextWidth, targetHeight);
    });
  };

  let resizeTimer = null;
  const bindChartResize = () => {
    window.addEventListener('resize', () => {
      if (resizeTimer) {
        window.clearTimeout(resizeTimer);
      }
      resizeTimer = window.setTimeout(() => {
        lockOverviewChartLayout();
        resizeChartsToContainer();
      }, 140);
    });
  };

  const initCharts = () => {
    const ChartRef = window.Chart;
    if (!ChartRef) return;
    lockOverviewChartLayout();
    const chartSeed = overviewSeed?.charts || {};
    const planSeed = chartSeed.plan || {};
    const mongoSizeSeed = chartSeed.mongo_size || {};
    const mongoHealthSeed = chartSeed.mongo_health || {};
    const mongoSizeLabelPack = buildMongoLabelPackFromSeed(mongoSizeSeed.labels);
    const mongoHealthLabelPack = buildMongoLabelPackFromSeed(mongoHealthSeed.labels);

    const planCanvas = document.getElementById('ownerbotPlanChart');
    if (planCanvas instanceof HTMLCanvasElement) {
      charts.plan = new ChartRef(planCanvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: Array.isArray(planSeed.labels) ? planSeed.labels : [],
          datasets: [{
            label: 'Guilds',
            data: Array.isArray(planSeed.values) ? planSeed.values : [],
            backgroundColor: ['#6ea8fe', '#7ee787', '#f6c177', '#f78c6c', '#c3a6ff'],
            borderRadius: 8,
          }],
        },
        options: {
          responsive: false,
          maintainAspectRatio: false,
          animation: false,
          parsing: true,
          normalized: true,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              ticks: {
                maxRotation: 0,
                minRotation: 0,
                autoSkip: true,
                maxTicksLimit: 8,
              },
            },
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
            },
          },
        },
      });
    }

    const sizeCanvas = document.getElementById('ownerbotMongoSizeChart');
    if (sizeCanvas instanceof HTMLCanvasElement) {
      charts.mongoSize = new ChartRef(sizeCanvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: mongoSizeLabelPack.shortLabels,
          datasets: [
            { label: 'Storage MB', data: Array.isArray(mongoSizeSeed.storage_mb) ? mongoSizeSeed.storage_mb : [], backgroundColor: '#6ea8fe' },
            { label: 'Data MB', data: Array.isArray(mongoSizeSeed.data_mb) ? mongoSizeSeed.data_mb : [], backgroundColor: '#7ee787' },
          ],
        },
        options: {
          responsive: false,
          maintainAspectRatio: false,
          animation: false,
          parsing: true,
          normalized: true,
          plugins: {
            tooltip: {
              callbacks: {
                title: mongoTooltipTitle,
              },
            },
          },
          scales: {
            x: {
              ticks: {
                maxRotation: 0,
                minRotation: 0,
                autoSkip: true,
                maxTicksLimit: 6,
              },
            },
            y: {
              beginAtZero: true,
            },
          },
        },
      });
      charts.mongoSize.$ownerbotFullLabels = mongoSizeLabelPack.fullLabels;
    }

    const healthCanvas = document.getElementById('ownerbotMongoHealthChart');
    if (healthCanvas instanceof HTMLCanvasElement) {
      charts.mongoHealth = new ChartRef(healthCanvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: mongoHealthLabelPack.shortLabels,
          datasets: [
            { label: 'Read %', data: Array.isArray(mongoHealthSeed.read_rate) ? mongoHealthSeed.read_rate : [], borderColor: '#6ea8fe', backgroundColor: 'rgba(110,168,254,.2)', tension: 0.35, fill: true },
            { label: 'Write %', data: Array.isArray(mongoHealthSeed.write_rate) ? mongoHealthSeed.write_rate : [], borderColor: '#f78c6c', backgroundColor: 'rgba(247,140,108,.2)', tension: 0.35, fill: true },
          ],
        },
        options: {
          responsive: false,
          maintainAspectRatio: false,
          animation: false,
          parsing: true,
          normalized: true,
          plugins: {
            tooltip: {
              callbacks: {
                title: mongoTooltipTitle,
              },
            },
          },
          scales: {
            x: {
              ticks: {
                maxRotation: 0,
                minRotation: 0,
                autoSkip: true,
                maxTicksLimit: 6,
              },
            },
            y: {
              suggestedMin: 0,
              suggestedMax: 100,
            },
          },
        },
      });
      charts.mongoHealth.$ownerbotFullLabels = mongoHealthLabelPack.fullLabels;
    }
    resizeChartsToContainer();
    bindChartResize();
  };

  const updateCharts = (payloadRaw) => {
    const payload = payloadRaw && typeof payloadRaw === 'object' ? payloadRaw : {};
    const plan = payload.plan_counts && typeof payload.plan_counts === 'object' ? payload.plan_counts : {};
    if (charts.plan) {
      charts.plan.data.datasets[0].data = [
        Number(plan.free || 0),
        Number(plan.silver || 0),
        Number(plan.golden || 0),
        Number(plan.diamond || 0),
        Number(plan.permanent || 0),
      ];
      charts.plan.update('none');
    }

    const rows = Array.isArray(payload?.mongo?.rows) ? payload.mongo.rows : [];
    const mongoLabelPack = buildMongoLabelPackFromRows(rows);
    const storageMb = rows.map((row) => Number(row?.storage_size_bytes || 0) / (1024 * 1024));
    const dataMb = rows.map((row) => Number(row?.data_size_bytes || 0) / (1024 * 1024));
    const readRate = rows.map((row) => Number(row?.read_success_rate || 0) * 100);
    const writeRate = rows.map((row) => Number(row?.write_success_rate || 0) * 100);

    if (charts.mongoSize) {
      charts.mongoSize.data.labels = mongoLabelPack.shortLabels;
      charts.mongoSize.data.datasets[0].data = storageMb;
      charts.mongoSize.data.datasets[1].data = dataMb;
      charts.mongoSize.$ownerbotFullLabels = mongoLabelPack.fullLabels;
      charts.mongoSize.update('none');
    }
    if (charts.mongoHealth) {
      charts.mongoHealth.data.labels = mongoLabelPack.shortLabels;
      charts.mongoHealth.data.datasets[0].data = readRate;
      charts.mongoHealth.data.datasets[1].data = writeRate;
      charts.mongoHealth.$ownerbotFullLabels = mongoLabelPack.fullLabels;
      charts.mongoHealth.update('none');
    }
  };

  const applyLivePayload = (payloadRaw) => {
    const payload = payloadRaw && typeof payloadRaw === 'object' ? payloadRaw : {};
    applyKpi(payload.kpi || {});
    updateMongoRows(payload.mongo || {});
    updateRedeemRows(payload.recent_redeem_rows || []);
    updateCharts(payload);
  };

  const initLivePolling = () => {
    let polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const liveResp = await fetch('/dashboard/admin/ownerbot/live', {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        });

        if (liveResp.status === 401) {
          window.location.href = '/dashboard';
          return;
        }
        if (!liveResp.ok) {
          setLiveStatus('Live update: เชื่อมต่อไม่สำเร็จ กำลังลองใหม่...', true);
          return;
        }

        const payload = await liveResp.json();
        if (!payload || payload.ok !== true) {
          setLiveStatus('Live update: ได้ข้อมูลไม่สมบูรณ์', true);
          return;
        }

        applyRuntimeStatus(payload.runtime || {});
        applyLivePayload(payload);
        setLiveStatus('Live update: พร้อมใช้งาน');
      } catch (_error) {
        setLiveStatus('Live update: เครือข่ายมีปัญหา กำลังลองใหม่...', true);
      } finally {
        polling = false;
      }
    };

    poll();
    window.setInterval(poll, 15000);
  };

  applyRuntimeStatus(overviewSeed.runtime || {});
  applyLivePayload(overviewSeed || {});
  bindOverviewScrollPersistence();
  restoreOverviewScrollState();
  initCharts();
  if (statusOverrideLevelInput instanceof HTMLSelectElement) {
    statusOverrideLevelInput.addEventListener('change', () => applyRuntimeStatus(latestRuntimePayload));
  }
  if (statusOverrideActivityInput instanceof HTMLSelectElement) {
    statusOverrideActivityInput.addEventListener('change', () => applyRuntimeStatus(latestRuntimePayload));
  }
  if (statusOverrideMessageInput instanceof HTMLTextAreaElement) {
    statusOverrideMessageInput.addEventListener('input', () => applyRuntimeStatus(latestRuntimePayload));
  }
  if (
    statusAutoResetButton instanceof HTMLButtonElement
    && statusOverrideLevelInput instanceof HTMLSelectElement
    && statusOverrideActivityInput instanceof HTMLSelectElement
  ) {
    statusAutoResetButton.addEventListener('click', () => {
      statusOverrideLevelInput.value = 'auto';
      statusOverrideActivityInput.value = 'auto';
      if (statusOverrideMessageInput instanceof HTMLTextAreaElement) {
        statusOverrideMessageInput.value = '';
      }
      applyRuntimeStatus(latestRuntimePayload);
    });
  }
  bindStatusSubmitGuard();
  initLivePolling();
})();

