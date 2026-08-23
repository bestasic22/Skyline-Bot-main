(() => {{
        const form = document.getElementById('colorSetsForm');
        const grid = document.getElementById('colorSetsGrid');
        const jsonInput = document.getElementById('colorSetsJsonInput');
        const addBtn = document.getElementById('addColorSetBtn');
        const presetGrid = document.getElementById('presetColorSetGrid');
        const appliedSetInput = document.getElementById('appliedSetIdInput');
        const colorActionInput = document.getElementById('colorActionInput');
        const activeSetName = document.getElementById('activeColorSetName');
        const applyNotice = document.getElementById('colorApplyNotice');
        const colorRolesList = document.getElementById('colorRolesList');
        const colorRolesEmpty = document.getElementById('colorRolesEmpty');
        const colorRolesCount = document.getElementById('colorRolesCount');
        const deleteAllColorRolesBtn = document.getElementById('deleteAllColorRolesBtn');
        const modal = document.getElementById('applyColorSetModal');
        const modalTitle = document.getElementById('applyColorSetModalTitle');
        const modalCancelBtn = document.getElementById('applyColorSetCancelBtn');
        const modalConfirmBtn = document.getElementById('applyColorSetConfirmBtn');
        const backgroundStyleSelect = document.getElementById('colorBackgroundStyleSelect');
        const backgroundImageUploadWrap = document.getElementById('colorBackgroundImageUploadWrap');
        const backgroundImageFileInput = document.getElementById('colorBackgroundImageFileInput');
        const backgroundImageUrlInput = document.getElementById('colorBackgroundImageUrlInput');
        const backgroundImageCurrentLink = document.getElementById('colorBackgroundImageCurrentLink');
        const backgroundImageFileName = document.getElementById('colorBackgroundImageFileName');
        const backgroundImageClearBtn = document.getElementById('colorBackgroundImageClearBtn');
        if (!form || !grid || !jsonInput || !addBtn || !presetGrid || !appliedSetInput || !colorActionInput || !activeSetName || !applyNotice || !colorRolesList || !colorRolesEmpty || !colorRolesCount || !deleteAllColorRolesBtn || !modal || !modalTitle || !modalCancelBtn || !modalConfirmBtn) return;
        let rows = [];
        let applyPendingIndex = -1;
        let rolesInGuild = [];
        let roleActionInFlight = false;
        let roleActionType = '';
        try {{
          const decoded = JSON.parse(jsonInput.value || '[]');
          rows = Array.isArray(decoded) ? decoded : [];
        }} catch (_error) {{
          rows = [];
        }}
        try {{
          const decodedRoles = JSON.parse({json.dumps(color_roles_json, ensure_ascii=False)});
          rolesInGuild = Array.isArray(decodedRoles) ? decodedRoles : [];
        }} catch (_error) {{
          rolesInGuild = [];
        }}
        const newSet = () => ({{
          id: `set_${{Date.now()}}_${{Math.floor(Math.random()*1000)}}`,
          name: '',
          enabled: true,
          colors: ['#6B8CFF']
        }});
        const sync = () => {{
          jsonInput.value = JSON.stringify(rows);
        }};
        const escapeHtml = (value) => String(value || '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
        const setModalOpen = (open) => {{
          modal.classList.toggle('open', !!open);
          modal.setAttribute('aria-hidden', open ? 'false' : 'true');
          document.body.classList.toggle('modal-open', !!open);
        }};
        const refreshBackgroundImageControl = () => {{
          const isCustomImageStyle = String(backgroundStyleSelect?.value || '').trim().toLowerCase() === 'custom image';
          if (backgroundImageUploadWrap) {{
            backgroundImageUploadWrap.style.display = isCustomImageStyle ? '' : 'none';
          }}
          if (backgroundImageFileInput) {{
            backgroundImageFileInput.disabled = !isCustomImageStyle;
          }}

          const currentUrl = String(backgroundImageUrlInput?.value || '').trim();
          const selectedFile = backgroundImageFileInput?.files?.[0] || null;

          if (backgroundImageCurrentLink) {{
            if (currentUrl) {{
              backgroundImageCurrentLink.style.display = '';
              backgroundImageCurrentLink.href = currentUrl;
            }} else {{
              backgroundImageCurrentLink.style.display = 'none';
              backgroundImageCurrentLink.removeAttribute('href');
            }}
          }}

          if (backgroundImageFileName) {{
            if (selectedFile) {{
              backgroundImageFileName.textContent = `ไฟล์ที่เลือก: ${{selectedFile.name}}`;
            }} else if (currentUrl) {{
              backgroundImageFileName.textContent = 'ยังไม่ได้เลือกรูปใหม่ (กำลังใช้รูปปัจจุบัน)';
            }} else {{
              backgroundImageFileName.textContent = 'รองรับ png/jpg/jpeg/webp/gif';
            }}
          }}

          if (backgroundImageClearBtn) {{
            backgroundImageClearBtn.disabled = !currentUrl && !selectedFile;
          }}
        }};
        const wireBackgroundImageControls = () => {{
          if (backgroundStyleSelect) {{
            backgroundStyleSelect.addEventListener('change', refreshBackgroundImageControl);
          }}
          if (backgroundImageFileInput) {{
            backgroundImageFileInput.addEventListener('change', refreshBackgroundImageControl);
          }}
          if (backgroundImageClearBtn) {{
            backgroundImageClearBtn.addEventListener('click', () => {{
              if (backgroundImageFileInput) {{
                backgroundImageFileInput.value = '';
              }}
              if (backgroundImageUrlInput) {{
                backgroundImageUrlInput.value = '';
              }}
              refreshBackgroundImageControl();
            }});
          }}
          refreshBackgroundImageControl();
        }};
        const currentAppliedSetId = () => String(appliedSetInput.value || '').trim();
        const setActiveSetName = () => {{
          const id = currentAppliedSetId();
          const row = rows.find((r) => String(r?.id || '') === id);
          activeSetName.textContent = row ? String(row.name || id || '-') : '-';
        }};
        const showApplyNotice = (message, ok = true) => {{
          const text = String(message || '').trim();
          if (!text) {{
            applyNotice.style.display = 'none';
            applyNotice.classList.remove('ok', 'error');
            applyNotice.textContent = '';
            return;
          }}
          applyNotice.style.display = '';
          applyNotice.classList.remove('ok', 'error');
          applyNotice.classList.add(ok ? 'ok' : 'error');
          applyNotice.textContent = text;
        }};
        const setRoleActionState = (busy, action = '') => {{
          roleActionInFlight = !!busy;
          if (roleActionInFlight) {{
            roleActionType = String(action || roleActionType || '').trim().toLowerCase();
          }} else {{
            roleActionType = '';
          }}
          colorRolesList.querySelectorAll('[data-color-role-delete]').forEach((btn) => {{
            btn.disabled = !!busy;
          }});
          deleteAllColorRolesBtn.disabled = !!busy || !Array.isArray(rolesInGuild) || rolesInGuild.length === 0;
          deleteAllColorRolesBtn.textContent = busy && roleActionType === 'delete_all_roles' ? 'กำลังลบ...' : 'ลบทั้งหมด';
        }};
        const requestColorRoleDelete = async (action, roleIdRaw = '') => {{
          const actionName = String(action || '').trim().toLowerCase();
          if (!actionName || roleActionInFlight) return;
          const roleId = String(roleIdRaw || '').trim();
          const isDeleteAll = actionName === 'delete_all_roles';
          if (isDeleteAll && (!Array.isArray(rolesInGuild) || rolesInGuild.length === 0)) return;
          if (!isDeleteAll && !roleId) return;
          const confirmText = isDeleteAll
            ? `ต้องการลบบทบาทสีทั้งหมด ${{rolesInGuild.length}} รายการใช่หรือไม่?`
            : 'ต้องการลบบทบาทสีนี้ใช่หรือไม่?';
          if (!window.confirm(confirmText)) return;
          setRoleActionState(true, actionName);
          colorActionInput.value = actionName;
          const payload = new URLSearchParams(new FormData(form));
          payload.set('color_action', actionName);
          if (roleId) payload.set('target_role_id', roleId);
          try {{
            const response = await fetch('/dashboard/guild/{current_guild["id"]}/colors/apply_set', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' }},
              body: payload.toString(),
            }});
            const result = await response.json().catch(() => ({{}}));
            if (result && Array.isArray(result.roles)) {{
              rolesInGuild = result.roles;
            }}
            renderRoleList();
            showApplyNotice(result?.message || (response.ok ? 'ดำเนินการสำเร็จ' : 'ดำเนินการไม่สำเร็จ'), !!result?.ok);
          }} catch (_error) {{
            showApplyNotice('ดำเนินการไม่สำเร็จ', false);
          }} finally {{
            colorActionInput.value = 'save';
            setRoleActionState(false);
          }}
        }};
        const renderRoleList = (highlightIds = []) => {{
          const safeRows = Array.isArray(rolesInGuild) ? rolesInGuild : [];
          const flashSet = new Set((Array.isArray(highlightIds) ? highlightIds : []).map((v) => String(v || '').trim()).filter(Boolean));
          colorRolesCount.textContent = `${{safeRows.length}} รายการ`;
          deleteAllColorRolesBtn.disabled = roleActionInFlight || safeRows.length === 0;
          deleteAllColorRolesBtn.textContent = roleActionInFlight && roleActionType === 'delete_all_roles' ? 'กำลังลบ...' : 'ลบทั้งหมด';
          if (!safeRows.length) {{
            colorRolesEmpty.style.display = '';
            colorRolesList.innerHTML = '';
            return;
          }}
          colorRolesEmpty.style.display = 'none';
          colorRolesList.innerHTML = safeRows.map((role) => {{
            const roleName = escapeHtml(role?.name || '-');
            const roleIdRaw = String(role?.id || '').trim();
            const roleId = escapeHtml(roleIdRaw || '-');
            const roleColor = /^#[0-9A-Fa-f]{{6}}$/.test(String(role?.color || '')) ? String(role.color) : '#6B8CFF';
            const flashClass = flashSet.has(roleIdRaw) ? ' flash-new-role' : '';
            return `
              <article class="color-role-live-item${{flashClass}}" data-role-id="${{roleId}}">
                <span class="color-role-live-swatch" style="background:${{roleColor}}"></span>
                <div class="color-role-live-main">
                  <span class="color-role-live-name">บทบาท #${{roleName}}</span>
                  <span class="muted">ID: ${{roleId}}  ${{escapeHtml(roleColor)}}</span>
                </div>
                <div class="color-role-live-actions">
                  <button type="button" class="danger-btn color-role-live-delete-btn" data-color-role-delete="${{roleIdRaw}}">ลบ</button>
                </div>
              </article>
            `;
          }}).join('');
          colorRolesList.querySelectorAll('[data-color-role-delete]').forEach((btn) => {{
            btn.addEventListener('click', () => {{
              const roleId = String(btn.getAttribute('data-color-role-delete') || '').trim();
              requestColorRoleDelete('delete_role', roleId);
            }});
          }});
          setRoleActionState(roleActionInFlight, roleActionType);
          if (flashSet.size > 0) {{
            window.setTimeout(() => {{
              colorRolesList.querySelectorAll('.flash-new-role').forEach((node) => node.classList.remove('flash-new-role'));
            }}, 2700);
          }}
        }};
        const renderPresetCards = () => {{
          presetGrid.innerHTML = rows.map((row, index) => {{
            const colors = Array.isArray(row.colors) ? row.colors : [];
            const preview = colors.slice(0, 4).map((c) => `<i style="background:${{escapeHtml(c)}}"></i>`).join('');
            const more = colors.length > 4 ? `<span class="more">${{colors.length - 4}}</span>` : '';
            const isActive = String(row.id || '') === currentAppliedSetId();
            return `
              <article class="color-set-preset-card ${{isActive ? 'active' : ''}}" data-preset-index="${{index}}">
                <strong>${{escapeHtml(row.name || `ชุดสี ${{index+1}}`)}}</strong>
                <span class="muted">${{colors.length}} สี</span>
                <div class="color-set-preview">${{preview}}${{more}}</div>
                <div class="color-set-card-actions">
                  <span class="muted">${{isActive ? 'ใช้งานอยู่' : 'ยังไม่ใช้งาน'}}</span>
                  <button type="button" class="ghost-btn" data-cs-apply="${{index}}">ใช้ชุดสี</button>
                </div>
              </article>
            `;
          }}).join('');
          presetGrid.querySelectorAll('[data-cs-apply]').forEach((btn) => {{
            btn.addEventListener('click', () => {{
              const idx = Number(btn.getAttribute('data-cs-apply'));
              if (!Number.isFinite(idx) || !rows[idx]) return;
              applyPendingIndex = idx;
              modalTitle.textContent = `ใช้ชุดสี '${{String(rows[idx].name || 'ชุดสี').trim()}}'`;
              setModalOpen(true);
            }});
          }});
          setActiveSetName();
        }};
        const render = () => {{
          grid.innerHTML = rows.map((row, index) => {{
            const colors = Array.isArray(row.colors) ? row.colors : ['#6B8CFF'];
            return `
              <article class="screening-cat-card">
                <div class="screening-cat-head">
                  <strong>ชุด ${{index + 1}}</strong>
                  <label class="ux-toggle" style="margin-left:auto;">
                    <input type="checkbox" data-cs-enable="${{index}}" ${{row.enabled ? 'checked' : ''}}>
                    <span class="ux-switch"></span>
                  </label>
                </div>
                <div class="field-item"><label>ชื่อชุดสี</label><input type="text" data-cs-name="${{index}}" value="${{String(row.name || '').replaceAll('"','&quot;')}}" maxlength="50"></div>
                <div class="field-item">
                  <label>สีในชุ</label>
                  <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;">
                    ${{colors.map((c, i) => `<input type="color" data-cs-color="${{index}}" data-cs-color-index="${{i}}" value="${{c}}">`).join('')}}
                  </div>
                  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
                    <button type="button" class="ghost-btn" data-cs-add-color="${{index}}">+ สี</button>
                    <button type="button" class="danger-btn" data-cs-remove="${{index}}">ลบชุด</button>
                  </div>
                </div>
              </article>
            `;
          }}).join('');
          grid.querySelectorAll('[data-cs-enable]').forEach((el) => {{
            el.addEventListener('change', () => {{
              const idx = Number(el.getAttribute('data-cs-enable'));
              if (!Number.isFinite(idx) || !rows[idx]) return;
              rows[idx].enabled = !!el.checked;
              sync();
            }});
          }});
          grid.querySelectorAll('[data-cs-name]').forEach((el) => {{
            el.addEventListener('input', () => {{
              const idx = Number(el.getAttribute('data-cs-name'));
              if (!Number.isFinite(idx) || !rows[idx]) return;
              rows[idx].name = String(el.value || '').slice(0, 50);
              sync();
            }});
          }});
          grid.querySelectorAll('[data-cs-color]').forEach((el) => {{
            el.addEventListener('input', () => {{
              const idx = Number(el.getAttribute('data-cs-color'));
              const colorIdx = Number(el.getAttribute('data-cs-color-index'));
              if (!Number.isFinite(idx) || !rows[idx] || !Number.isFinite(colorIdx)) return;
              if (!Array.isArray(rows[idx].colors)) rows[idx].colors = ['#6B8CFF'];
              rows[idx].colors[colorIdx] = String(el.value || '#6B8CFF').toUpperCase();
              sync();
            }});
          }});
          grid.querySelectorAll('[data-cs-add-color]').forEach((el) => {{
            el.addEventListener('click', () => {{
              const idx = Number(el.getAttribute('data-cs-add-color'));
              if (!Number.isFinite(idx) || !rows[idx]) return;
              if (!Array.isArray(rows[idx].colors)) rows[idx].colors = [];
              if (rows[idx].colors.length >= 12) return;
              rows[idx].colors.push('#6B8CFF');
              render();
              sync();
            }});
          }});
          grid.querySelectorAll('[data-cs-remove]').forEach((el) => {{
            el.addEventListener('click', () => {{
              const idx = Number(el.getAttribute('data-cs-remove'));
              if (!Number.isFinite(idx)) return;
              rows.splice(idx, 1);
              render();
              sync();
            }});
          }});
          renderPresetCards();
        }};
        addBtn.addEventListener('click', () => {{
          colorActionInput.value = 'save';
          rows.unshift(newSet());
          render();
          sync();
        }});
        deleteAllColorRolesBtn.addEventListener('click', () => {{
          requestColorRoleDelete('delete_all_roles');
        }});
        modalCancelBtn.addEventListener('click', () => {{
          applyPendingIndex = -1;
          setModalOpen(false);
        }});
        modalConfirmBtn.addEventListener('click', async () => {{
          if (!Number.isFinite(applyPendingIndex) || applyPendingIndex < 0 || !rows[applyPendingIndex]) {{
            setModalOpen(false);
            return;
          }}
          const target = rows[applyPendingIndex];
          const targetId = String(target.id || '').trim();
          if (targetId) {{
            appliedSetInput.value = targetId;
            rows[applyPendingIndex].enabled = true;
          }}
          sync();
          renderPresetCards();
          colorActionInput.value = 'apply_set';
          modalConfirmBtn.disabled = true;
          modalConfirmBtn.textContent = 'กำลังดำเนินการ...';
          const payload = new FormData(form);
          payload.set('color_action', 'apply_set');
          try {{
            const response = await fetch('/dashboard/guild/{current_guild["id"]}/colors/apply_set', {{
              method: 'POST',
              body: payload,
            }});
            const result = await response.json().catch(() => ({{}}));
            if (result && Array.isArray(result.roles)) {{
              rolesInGuild = result.roles;
              renderRoleList(Array.isArray(result.highlight_role_ids) ? result.highlight_role_ids : []);
            }}
            if (result && result.applied_set_id) {{
              appliedSetInput.value = String(result.applied_set_id);
            }}
            if (result && typeof result.background_image_url === 'string' && backgroundImageUrlInput) {{
              backgroundImageUrlInput.value = String(result.background_image_url || '').trim();
              refreshBackgroundImageControl();
            }}
            renderPresetCards();
            showApplyNotice(result?.message || 'บันทึกสำเร็จ', !!result?.ok);
          }} catch (_error) {{
            showApplyNotice('บันทึกไม่สำเร็จ', false);
          }} finally {{
            colorActionInput.value = 'save';
            modalConfirmBtn.disabled = false;
            modalConfirmBtn.textContent = 'ยืนยัน';
            setModalOpen(false);
            applyPendingIndex = -1;
          }}
        }});
        modal.addEventListener('click', (event) => {{
          if (event.target === modal) {{
            applyPendingIndex = -1;
            setModalOpen(false);
          }}
        }});
        if (!rows.length) rows = {json.dumps(_default_color_sets_settings()["sets"], ensure_ascii=False)};
        if (!currentAppliedSetId() && rows.length) {{
          appliedSetInput.value = String(rows[0].id || '').trim();
        }}
        wireBackgroundImageControls();
        form.addEventListener('submit', () => {{
          if (String(colorActionInput.value || '').trim().toLowerCase() !== 'apply_set') {{
            colorActionInput.value = 'save';
          }}
        }});
        render();
        renderRoleList();
        sync();
      }})();
