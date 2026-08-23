(() => {{
        const overviewRoot = document.querySelector('[data-overview-root]');
        const overviewRanges = {overview_payload_json};
        const DEFAULT_RANGE = "7d";
        const rangeSelect = document.getElementById("overviewRangeSelect");
        const chartStates = new Map();

        const parseRgb = (raw) => {{
          const matched = String(raw || '').match(/[\\d.]+/g) || [];
          if (matched.length < 3) return [21, 36, 64];
          return [Number(matched[0]) || 0, Number(matched[1]) || 0, Number(matched[2]) || 0];
        }};

        const hexToRgb = (hex) => {{
          const cleaned = String(hex || '').replace('#', '').trim();
          if (cleaned.length !== 6) return [95, 151, 255];
          return [
            parseInt(cleaned.slice(0, 2), 16) || 0,
            parseInt(cleaned.slice(2, 4), 16) || 0,
            parseInt(cleaned.slice(4, 6), 16) || 0,
          ];
        }};

        const colorWithAlpha = (hex, alpha) => {{
          const [r, g, b] = hexToRgb(hex);
          return `rgba(${{r}}, ${{g}}, ${{b}}, ${{alpha}})`;
        }};

        const clamp = (value, min, max) => Math.min(max, Math.max(min, Number(value) || 0));

        const escapeHtml = (value) =>
          String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');

        const resolvePalette = () => {{
          const sampleNode = (overviewRoot && (overviewRoot.querySelector('.panel-sub') || overviewRoot.querySelector('.panel'))) || overviewRoot;
          const bg = sampleNode ? window.getComputedStyle(sampleNode).backgroundColor : "rgb(21,36,64)";
          const [r, g, b] = parseRgb(bg);
          const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
          const isLight = luminance >= 0.62;
          const palette = isLight
            ? {{
                main: "#1f3762",
                muted: "#4e6695",
                axis: "rgba(43,67,118,.72)",
                grid: "rgba(67,95,150,.24)"
              }}
            : {{
                main: "#edf3ff",
                muted: "rgba(230,237,255,.72)",
                axis: "rgba(235,241,255,.70)",
                grid: "rgba(255,255,255,.14)"
              }};
          if (overviewRoot) {{
            overviewRoot.style.setProperty('--overview-text-main', palette.main);
            overviewRoot.style.setProperty('--overview-text-muted', palette.muted);
          }}
          return palette;
        }};

        const chartMeta = {{
          overviewJoinChart: {{ label: "Joins / Leaves", color: "#5f97ff" }},
          overviewMemberChart: {{ label: "Member Count", color: "#8e6dff" }},
          overviewMessageChart: {{ label: "Messages (non-bot)", color: "#ea4ca3" }},
        }};

        let palette = resolvePalette();

        const drawSmoothPath = (ctx, plotPoints, minY, maxY, options = {{}}) => {{
          const moveToStart = options.moveToStart !== false;
          if (!plotPoints.length) return;
          if (moveToStart) {{
            ctx.moveTo(plotPoints[0].x, plotPoints[0].y);
          }} else if (plotPoints.length === 1) {{
            ctx.lineTo(plotPoints[0].x, plotPoints[0].y);
          }}
          if (plotPoints.length === 1) return;
          if (plotPoints.length === 2) {{
            ctx.lineTo(plotPoints[1].x, plotPoints[1].y);
            return;
          }}
          for (let index = 0; index < plotPoints.length - 1; index += 1) {{
            const p0 = plotPoints[index - 1] || plotPoints[index];
            const p1 = plotPoints[index];
            const p2 = plotPoints[index + 1];
            const p3 = plotPoints[index + 2] || p2;

            const cp1x = p1.x + (p2.x - p0.x) / 6;
            const cp1y = clamp(p1.y + (p2.y - p0.y) / 6, minY, maxY);
            const cp2x = p2.x - (p3.x - p1.x) / 6;
            const cp2y = clamp(p2.y - (p3.y - p1.y) / 6, minY, maxY);

            ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
          }}
        }};

        const ensureLegend = (canvas, label, color, latestValue) => {{
          const host = canvas.closest('.panel-sub') || canvas.parentElement;
          if (!(host instanceof HTMLElement)) return;
          let legend = host.querySelector('[data-overview-legend]');
          if (!(legend instanceof HTMLElement)) {{
            legend = document.createElement('div');
            legend.className = 'overview-chart-legend';
            legend.setAttribute('data-overview-legend', '1');
            host.appendChild(legend);
          }}
          legend.innerHTML = `
            <span class="overview-chart-legend-item">
              <span class="overview-chart-legend-dot" style="background:${{escapeHtml(color)}}"></span>
              <span class="overview-chart-legend-label">${{escapeHtml(label)}}</span>
              <span class="overview-chart-legend-value">${{Number(latestValue || 0).toLocaleString()}}</span>
            </span>
          `;
        }};

        const ensureTooltip = (canvas) => {{
          const host = canvas.closest('.panel-sub') || canvas.parentElement;
          if (!(host instanceof HTMLElement)) return null;
          if (window.getComputedStyle(host).position === 'static') {{
            host.style.position = 'relative';
          }}
          let tooltip = host.querySelector('[data-overview-tooltip]');
          if (!(tooltip instanceof HTMLElement)) {{
            tooltip = document.createElement('div');
            tooltip.className = 'overview-chart-tooltip';
            tooltip.setAttribute('data-overview-tooltip', '1');
            host.appendChild(tooltip);
          }}
          return tooltip;
        }};

        const hideTooltip = (canvas) => {{
          const tooltip = ensureTooltip(canvas);
          if (!(tooltip instanceof HTMLElement)) return;
          tooltip.classList.remove('is-visible');
        }};

        const bindTooltip = (canvasId) => {{
          const canvas = document.getElementById(canvasId);
          if (!(canvas instanceof HTMLCanvasElement)) return;
          if (canvas.dataset.tooltipBound === "1") return;

          canvas.dataset.tooltipBound = "1";
          canvas.addEventListener('mouseleave', () => hideTooltip(canvas));
          canvas.addEventListener('mousemove', (event) => {{
            const state = chartStates.get(canvasId);
            if (!state || !Array.isArray(state.plotPoints) || !state.plotPoints.length) {{
              hideTooltip(canvas);
              return;
            }}
            const rect = canvas.getBoundingClientRect();
            const localX = event.clientX - rect.left;
            const nearest = state.plotPoints.reduce((best, point, index) => {{
              const distance = Math.abs(point.x - localX);
              if (!best || distance < best.distance) {{
                return {{ point, index, distance }};
              }}
              return best;
            }}, null);

            if (!nearest || nearest.distance > Math.max(18, rect.width / Math.max(6, state.plotPoints.length))) {{
              hideTooltip(canvas);
              return;
            }}

            const tooltip = ensureTooltip(canvas);
            if (!(tooltip instanceof HTMLElement)) return;
            const labelText = state.labels[nearest.index] || "-";
            const value = Number(state.values[nearest.index] || 0).toLocaleString();
            tooltip.innerHTML = `
              <div class="overview-chart-tooltip-title">${{escapeHtml(state.label)}}</div>
              <div class="overview-chart-tooltip-body">
                <span>${{escapeHtml(labelText)}}</span>
                <strong style="color:${{escapeHtml(state.color)}}">${{escapeHtml(value)}}</strong>
              </div>
            `;

            tooltip.style.left = '0px';
            tooltip.style.top = '0px';
            tooltip.style.transform = 'translate(-9999px, -9999px)';
            tooltip.classList.add('is-visible');
            const tipRect = tooltip.getBoundingClientRect();
            const maxLeft = Math.max(8, rect.width - tipRect.width - 8);
            const maxTop = Math.max(8, rect.height - tipRect.height - 8);
            const left = Math.min(Math.max(8, nearest.point.x + 12), maxLeft);
            const top = Math.min(Math.max(8, nearest.point.y - tipRect.height - 10), maxTop);
            tooltip.style.transform = `translate(${{Math.round(left)}}px, ${{Math.round(top)}}px)`;
          }});
        }};

        const drawLineChart = (canvasId, labels, data, color, labelText, options = {{}}) => {{
          const canvas = document.getElementById(canvasId);
          if (!(canvas instanceof HTMLCanvasElement)) return;
          const ctx = canvas.getContext('2d');
          if (!ctx) return;

          const parentWidth = canvas.parentElement?.getBoundingClientRect?.().width || 0;
          const fallbackWidth = canvas.getBoundingClientRect?.().width || canvas.clientWidth || 640;
          const logicalWidth = parentWidth > 0 ? parentWidth : fallbackWidth;
          const width = Math.max(1, Math.floor(logicalWidth));
          let baseHeight = Number(canvas.dataset.baseHeight || 0);
          if (!Number.isFinite(baseHeight) || baseHeight <= 0) {{
            baseHeight = Number(canvas.getAttribute('height') || canvas.clientHeight || 180);
            if (!Number.isFinite(baseHeight) || baseHeight <= 0) baseHeight = 180;
            canvas.dataset.baseHeight = String(Math.round(baseHeight));
          }}
          const height = Math.max(120, Math.round(baseHeight));
          const dpr = Math.max(1, Number(window.devicePixelRatio || 1));

          canvas.style.display = 'block';
          canvas.style.maxWidth = '100%';
          canvas.style.width = '100%';
          canvas.style.height = `${{Math.round(height)}}px`;

          canvas.width = Math.round(width * dpr);
          canvas.height = Math.round(height * dpr);
          ctx.setTransform(1, 0, 0, 1, 0, 0);
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          ctx.clearRect(0, 0, width, height);

          const pointCount = Math.max(2, (Array.isArray(labels) && labels.length) ? labels.length : (Array.isArray(data) ? data.length : 7));
          const values = Array.from({{ length: pointCount }}, (_, index) => Number((Array.isArray(data) ? data[index] : 0) || 0));
          const xLabels = Array.from({{ length: pointCount }}, (_, index) => String((Array.isArray(labels) ? labels[index] : "") || ""));
          const max = Math.max(1, ...values);
          const sumValue = values.reduce((sum, value) => sum + (Number(value) || 0), 0);
          const candidateLegendValue = Number(options?.legendValue);
          const legendValue = Number.isFinite(candidateLegendValue) ? candidateLegendValue : sumValue;

          const left = 48;
          const top = 18;
          const bottom = height - 34;
          const right = width - 14;

          const plotPoints = values.map((value, index) => {{
            const x = left + ((right - left) * (index / Math.max(1, values.length - 1)));
            const y = bottom - ((bottom - top) * (value / max));
            return {{ x, y }};
          }});

          ctx.strokeStyle = palette.axis;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(left, top);
          ctx.lineTo(left, bottom);
          ctx.lineTo(right, bottom);
          ctx.stroke();

          ctx.strokeStyle = palette.grid;
          ctx.lineWidth = 1;
          for (let tick = 1; tick <= 3; tick += 1) {{
            const y = top + ((bottom - top) * (tick / 4));
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(right, y);
            ctx.stroke();
          }}

          ctx.beginPath();
          ctx.moveTo(plotPoints[0].x, bottom);
          ctx.lineTo(plotPoints[0].x, plotPoints[0].y);
          drawSmoothPath(ctx, plotPoints, top, bottom, {{ moveToStart: false }});
          ctx.lineTo(plotPoints[plotPoints.length - 1].x, bottom);
          ctx.closePath();
          const areaGradient = ctx.createLinearGradient(0, top, 0, bottom);
          areaGradient.addColorStop(0, colorWithAlpha(color, 0.24));
          areaGradient.addColorStop(1, colorWithAlpha(color, 0.03));
          ctx.fillStyle = areaGradient;
          ctx.fill();

          ctx.strokeStyle = color;
          ctx.lineWidth = 2.3;
          ctx.beginPath();
          drawSmoothPath(ctx, plotPoints, top, bottom);
          ctx.stroke();

          ctx.fillStyle = color;
          plotPoints.forEach((point) => {{
            ctx.beginPath();
            ctx.arc(point.x, point.y, 3, 0, Math.PI * 2);
            ctx.fill();
          }});

          ctx.fillStyle = palette.axis;
          ctx.font = '11px Manrope, sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          const availableWidth = Math.max(1, right - left);
          const minLabelSpacing = 46;
          const maxVisibleLabels = Math.max(2, Math.floor(availableWidth / minLabelSpacing) + 1);
          const step = Math.max(1, Math.ceil((xLabels.length - 1) / Math.max(1, maxVisibleLabels - 1)));
          xLabels.forEach((label, index) => {{
            const isFirst = index === 0;
            const isLast = index === xLabels.length - 1;
            if (!isFirst && !isLast && (index % step) !== 0) return;
            const x = left + ((right - left) * (index / Math.max(1, xLabels.length - 1)));
            ctx.fillText(label, x, bottom + 10);
          }});

          ctx.textAlign = 'right';
          ctx.textBaseline = 'middle';
          ctx.fillText(String(max), left - 10, top);
          ctx.fillText("0", left - 10, bottom);

          chartStates.set(canvasId, {{
            label: labelText,
            color,
            labels: xLabels,
            values,
            plotPoints,
          }});
          ensureLegend(canvas, labelText, color, legendValue);
          bindTooltip(canvasId);
        }};

        const renderRange = (rangeKey) => {{
          palette = resolvePalette();
          const selected = overviewRanges[String(rangeKey || DEFAULT_RANGE)] || overviewRanges[DEFAULT_RANGE] || {{}};
          const labels = Array.isArray(selected.labels) ? selected.labels : [];
          const joinData = Array.isArray(selected.join_series) ? selected.join_series : [];
          const memberData = Array.isArray(selected.member_series) ? selected.member_series : [];
          const messageData = Array.isArray(selected.message_series) ? selected.message_series : [];
          const joinsTotal = Number(selected.joins_total);
          const messagesTotal = Number(selected.messages_total);

          drawLineChart(
            'overviewJoinChart',
            labels,
            joinData,
            chartMeta.overviewJoinChart.color,
            chartMeta.overviewJoinChart.label,
            {{
              legendValue: Number.isFinite(joinsTotal)
                ? joinsTotal
                : joinData.reduce((sum, value) => sum + (Number(value) || 0), 0),
            }}
          );
          drawLineChart(
            'overviewMemberChart',
            labels,
            memberData,
            chartMeta.overviewMemberChart.color,
            chartMeta.overviewMemberChart.label,
            {{
              legendValue: memberData.length ? Number(memberData[memberData.length - 1] || 0) : 0,
            }}
          );
          drawLineChart(
            'overviewMessageChart',
            labels,
            messageData,
            chartMeta.overviewMessageChart.color,
            chartMeta.overviewMessageChart.label,
            {{
              legendValue: Number.isFinite(messagesTotal)
                ? messagesTotal
                : messageData.reduce((sum, value) => sum + (Number(value) || 0), 0),
            }}
          );
        }};

        if (rangeSelect) {{
          rangeSelect.value = DEFAULT_RANGE;
          rangeSelect.addEventListener('change', () => renderRange(rangeSelect.value || DEFAULT_RANGE));
        }}

        const renderCurrentRange = () => renderRange((rangeSelect && rangeSelect.value) || DEFAULT_RANGE);
        let resizeRaf = 0;
        window.addEventListener('resize', () => {{
          if (resizeRaf) window.cancelAnimationFrame(resizeRaf);
          resizeRaf = window.requestAnimationFrame(() => {{
            resizeRaf = 0;
            renderCurrentRange();
          }});
        }});
        renderCurrentRange();
      }})();
