(() => {{
        const sendBtn = document.getElementById('promoteSendBtn');
        const promoteEnabled = {"true" if enabled else "false"};
        const promoteConfigured = {"true" if is_configured else "false"};
        const promoteSwitchEnabled = {"true" if promote_switch_enabled else "false"};
        const promoteSuspended = {"true" if promote_is_suspended else "false"};
        let remain = {cooldown_remaining};

        const submitSettingsAction = (form, actionValue) => {{
          if (!form || !actionValue) return;
          let actionInput = form.querySelector('input[name="action"][data-promote-settings-action="1"]');
          if (!actionInput) {{
            actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.setAttribute('data-promote-settings-action', '1');
            form.appendChild(actionInput);
          }}
          actionInput.value = String(actionValue);
          form.submit();
        }};

        const installSettingsControls = () => {{
          const settingsForm = document.querySelector('form[action$="/promote/settings"]');
          if (!settingsForm) return;
          const actionRow = settingsForm.querySelector('.form-actions-inline');
          if (!actionRow || actionRow.getAttribute('data-promote-controls-ready') === '1') return;
          actionRow.setAttribute('data-promote-controls-ready', '1');

          const saveBtn = actionRow.querySelector('button[type="submit"]');
          if (saveBtn) {{
            saveBtn.setAttribute('name', 'action');
            saveBtn.setAttribute('value', 'save_channels');
          }}

          const toggleBtn = document.createElement('button');
          toggleBtn.type = 'button';
          toggleBtn.className = promoteSwitchEnabled ? 'danger-btn' : 'ghost-btn';
          toggleBtn.textContent = promoteSwitchEnabled ? 'ปิดระบบโปรโมต' : 'เปิดระบบโปรโมต';
          toggleBtn.disabled = !promoteConfigured;
          toggleBtn.addEventListener('click', () => {{
            submitSettingsAction(settingsForm, 'toggle_enabled');
          }});

          const resetBtn = document.createElement('button');
          resetBtn.type = 'button';
          resetBtn.className = 'danger-btn';
          resetBtn.textContent = 'ลบ/รีเซ็ตค่า';
          resetBtn.disabled = !promoteConfigured;
          resetBtn.addEventListener('click', () => {{
            if (!window.confirm('ลบการตั้งค่า Promote ทั้งหมดและคืนค่าเริ่มต้น?')) return;
            submitSettingsAction(settingsForm, 'reset');
          }});

          actionRow.appendChild(toggleBtn);
          actionRow.appendChild(resetBtn);
        }};

        const fmt = (sec) => {{
          const total = Math.max(0, Number(sec) || 0);
          const h = Math.floor(total / 3600);
          const m = Math.floor((total % 3600) / 60);
          const s = total % 60;
          const parts = [];
          if (h > 0) parts.push(`${'{'}h{'}'} ชั่วโมง`);
          if (m > 0) parts.push(`${'{'}m{'}'} นาที`);
          if (s > 0 || parts.length === 0) parts.push(`${'{'}s{'}'} วินาที`);
          return parts.join(' ');
        }};

        const updateSendButton = () => {{
          if (!sendBtn) return;
          if (promoteSuspended) {{
            sendBtn.disabled = true;
            sendBtn.textContent = "ระงับการใช้งาน Promote";
            return;
          }}
          if (!promoteEnabled) {{
            sendBtn.disabled = true;
            sendBtn.textContent = "ยังไม่เปิดใช้งาน";
            return;
          }}
          if (remain <= 0) {{
            sendBtn.disabled = false;
            sendBtn.textContent = "{text['send']}";
            return;
          }}
          sendBtn.disabled = true;
          sendBtn.textContent = `ส่งได้ในอีก ${'{'}fmt(remain){'}'}`;
          remain -= 1;
          window.setTimeout(updateSendButton, 1000);
        }};

        installSettingsControls();
        updateSendButton();
      }})();
