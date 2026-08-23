(() => {{
        const dropzone = document.getElementById('donateDropzone');
        const form = document.getElementById('donateSettingsForm');
        const fileInput = document.getElementById('donateImageFileInput');
        const fileName = document.getElementById('donateFileName');
        const imageUrlInput = document.getElementById('donateImageUrlInput');
        const imagePreviewWrap = document.getElementById('donateImagePreviewWrap');
        const imagePreview = document.getElementById('donateImagePreview');
        const embedPreviewCard = document.getElementById('donateEmbedPreviewCard');
        const embedPreviewDesc = document.getElementById('donateEmbedPreviewDesc');
        const embedPreviewMethods = document.getElementById('donateEmbedPreviewMethods');
        const descDiscordInput = form?.querySelector('textarea[name="desc_discord"]');
        const colorInput = form?.querySelector('input[name="color"]');
        const slipEngineSelect = form?.querySelector('select[name="slipcheck_verify_engine"]');
        const slipEngineGroups = Array.from(form?.querySelectorAll('[data-slip-engine-group]') || []);

        document.querySelectorAll('[data-copy-link]').forEach((btn) => {{
          const originalText = btn.textContent || 'Copy URL';
          btn.addEventListener('click', async () => {{
            const value = String(btn.getAttribute('data-copy-link') || '').trim();
            if (!value) return;
            try {{
              await navigator.clipboard.writeText(value);
              btn.textContent = 'Copied';
              setTimeout(() => {{
                btn.textContent = originalText;
              }}, 1200);
            }} catch (_error) {{
            }}
          }});
        }});

        const renderDonatePreview = () => {{
          if (embedPreviewDesc && descDiscordInput) {{
            embedPreviewDesc.textContent = (descDiscordInput.value || '').trim() || 'Donation description';
          }}
          if (embedPreviewCard && colorInput) {{
            const color = (colorInput.value || '#6b8cff').trim();
            embedPreviewCard.style.borderLeftColor = color;
          }}
          if (embedPreviewMethods) {{
            const tags = [];
            if (form?.querySelector('input[name="method_truemoney"]')?.checked) tags.push(' TrueMoney');
            if (form?.querySelector('input[name="method_promptpay"]')?.checked) tags.push(' PromptPay');
            if (form?.querySelector('input[name="method_bank"]')?.checked) tags.push(' Bank');
            if (form?.querySelector('input[name="method_slipverify"]')?.checked) tags.push(' SlipVerify');
            if (!tags.length) tags.push('No payment method enabled');
            embedPreviewMethods.innerHTML = tags.map((text) => `<span class="mini-stat">${{text}}</span>`).join('');
          }}
        }};

        const setImagePreview = (src) => {{
          if (!imagePreview || !imagePreviewWrap) return;
          const value = String(src || '').trim();
          if (!value) {{
            imagePreviewWrap.style.display = 'none';
            imagePreview.removeAttribute('src');
            return;
          }}
          imagePreview.src = value;
          imagePreviewWrap.style.display = '';
        }};

        const syncSlipEngineGroups = () => {{
          const selectedRaw = String(slipEngineSelect?.value || 'slipok').trim().toLowerCase();
          const selected = selectedRaw === 'skylinebotslip' ? 'skylinebotslip' : 'slipok';
          slipEngineGroups.forEach((group) => {{
            const mode = String(group.getAttribute('data-slip-engine-group') || '').trim().toLowerCase();
            group.style.display = mode === selected ? '' : 'none';
          }});
        }};

        document.querySelectorAll('input[data-donate-toggle]').forEach((toggle) => {{
          const details = toggle.closest('details');
          if (!details) return;
          const sync = () => {{ details.open = !!toggle.checked; }};
          const holder = toggle.closest('label');
          if (holder) {{
            holder.addEventListener('click', (event) => {{
              event.stopPropagation();
            }});
            holder.addEventListener('mousedown', (event) => {{
              event.stopPropagation();
            }});
          }}
          toggle.addEventListener('click', (event) => {{
            event.stopPropagation();
          }});
          toggle.addEventListener('change', sync);
          sync();
        }});

        if (dropzone && fileInput && fileName) {{
          const setFile = (file) => {{
            if (!file) return;
            const dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;
            fileName.textContent = `File: ${{file.name}}`;
            if (window.URL && window.URL.createObjectURL) {{
              const objectUrl = URL.createObjectURL(file);
              setImagePreview(objectUrl);
            }}
          }};
          dropzone.addEventListener('click', () => fileInput.click());
          fileInput.addEventListener('change', () => {{
            const file = fileInput.files && fileInput.files[0];
            if (file) {{
              fileName.textContent = `File: ${{file.name}}`;
              if (window.URL && window.URL.createObjectURL) {{
                const objectUrl = URL.createObjectURL(file);
                setImagePreview(objectUrl);
              }}
            }}
          }});
          dropzone.addEventListener('dragover', (e) => {{ e.preventDefault(); dropzone.style.borderColor = 'rgba(107,140,255,.95)'; }});
          dropzone.addEventListener('dragleave', () => {{ dropzone.style.borderColor = 'rgba(255,110,199,.7)'; }});
          dropzone.addEventListener('drop', (e) => {{
            e.preventDefault();
            dropzone.style.borderColor = 'rgba(255,110,199,.7)';
            const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
            if (file) setFile(file);
          }});
        }}

        if (imageUrlInput) {{
          imageUrlInput.addEventListener('input', () => {{
            if (!(fileInput && fileInput.files && fileInput.files.length)) {{
              setImagePreview(imageUrlInput.value);
            }}
          }});
        }}

        descDiscordInput?.addEventListener('input', renderDonatePreview);
        colorInput?.addEventListener('input', renderDonatePreview);
        form?.querySelectorAll('input[data-donate-toggle]').forEach((el) => el.addEventListener('change', renderDonatePreview));
        slipEngineSelect?.addEventListener('change', syncSlipEngineGroups);
        syncSlipEngineGroups();
        renderDonatePreview();

        if (!form) return;
        form.addEventListener('submit', (event) => {{
          const errors = [];
          const digitsOnly = (value) => String(value || '').replace(/\D+/g, '');
          const tmEnabled = !!form.querySelector('input[name="method_truemoney"]')?.checked;
          const ppEnabled = !!form.querySelector('input[name="method_promptpay"]')?.checked;
          const bankEnabled = !!form.querySelector('input[name="method_bank"]')?.checked;
          const slipEnabled = !!form.querySelector('input[name="method_slipverify"]')?.checked;
          const goalEnabled = !!form.querySelector('input[name="method_goal"]')?.checked;
          const slipEngine = String(form.querySelector('select[name="slipcheck_verify_engine"]')?.value || 'slipok').trim().toLowerCase();

          const truemoney = form.querySelector('input[name="truemoney_phone"]')?.value || '';
          if (tmEnabled && digitsOnly(truemoney).length !== 10) {{
            errors.push('TrueMoney phone must be 10 digits');
          }}

          const promptpay = form.querySelector('input[name="promptpay_number"]')?.value || '';
          const promptpayLen = digitsOnly(promptpay).length;
          if (ppEnabled && !(promptpayLen === 10 || promptpayLen === 13)) {{
            errors.push('PromptPay number must be 10 or 13 digits');
          }}

          const bankAccount = form.querySelector('input[name="bank_account_number"]')?.value || '';
          const bankDigits = digitsOnly(bankAccount).length;
          if (bankEnabled && (bankDigits < 6 || bankDigits > 20)) {{
            errors.push('Bank account must be 6-20 digits');
          }}

          const autoApprove = Number(form.querySelector('input[name="slipcheck_auto_approve_confidence"]')?.value || 0);
          if (slipEnabled && (!Number.isFinite(autoApprove) || autoApprove < 50 || autoApprove > 100)) {{
            errors.push('Auto Approve Confidence must be between 50 and 100');
          }}

          if (slipEnabled && slipEngine === 'slipok') {{
            const slipApi = (form.querySelector('input[name="slipok_api_url"]')?.value || '').trim();
            const slipKey = (form.querySelector('input[name="slipok_key"]')?.value || '').trim();
            if (!slipApi || !slipKey) {{
              errors.push('Please set SlipOK API URL and API Key');
            }} else {{
              try {{
                const u = new URL(slipApi);
                if (!/^https?:$/.test(u.protocol)) throw new Error('invalid');
              }} catch (_error) {{
                errors.push('SlipOK API URL is invalid');
              }}
            }}
          }}

          if (slipEnabled && slipEngine === 'skylinebotslip') {{
            const receiverAccount = digitsOnly(form.querySelector('input[name="slipcheck_expected_receiver_account"]')?.value || '');
            if (receiverAccount.length < 6 || receiverAccount.length > 30) {{
              errors.push('Receiver account must be 6-30 digits');
            }}
            const receiverName = (form.querySelector('input[name="slipcheck_expected_receiver_name"]')?.value || '').trim();
            const receiverFirstTh = (form.querySelector('input[name="slipcheck_expected_receiver_first_name_th"]')?.value || '').trim();
            const receiverLastTh = (form.querySelector('input[name="slipcheck_expected_receiver_last_name_th"]')?.value || '').trim();
            const receiverFirstEn = (form.querySelector('input[name="slipcheck_expected_receiver_first_name_en"]')?.value || '').trim();
            const receiverLastEn = (form.querySelector('input[name="slipcheck_expected_receiver_last_name_en"]')?.value || '').trim();
            const hasNameData = !!(
              receiverName
              || (receiverFirstTh && receiverLastTh)
              || (receiverFirstEn && receiverLastEn)
            );
            if (!hasNameData) {{
              errors.push('Please fill receiver name (full name or first/last name)');
            }}
          }}

          const imageUrl = (form.querySelector('input[name="image_url"]')?.value || '').trim();
          const hasFile = !!(fileInput && fileInput.files && fileInput.files.length > 0);
          if (imageUrl && !hasFile) {{
            try {{
              const u = new URL(imageUrl);
              if (!/^https?:$/.test(u.protocol)) throw new Error('invalid');
            }} catch (_error) {{
              errors.push('Image URL is invalid');
            }}
          }}

          const start = Number(form.querySelector('input[name="goal_start_amount"]')?.value || 0);
          const end = Number(form.querySelector('input[name="goal_end_amount"]')?.value || 0);
          if (goalEnabled) {{
            if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < 0) {{
              errors.push('Goal amounts must be >= 0');
            }} else if (end < start) {{
              errors.push('Goal end amount must be greater than or equal to start amount');
            }}
          }}

          if (errors.length > 0) {{
            event.preventDefault();
            alert(errors.join('\n'));
          }}
        }});

        const slipBody = document.getElementById('donateSlipTableBody');
        const syncMeta = document.getElementById('donateSlipSyncMeta');
        if (slipBody) {{
          if (window.__donateSlipSyncStop) {{
            try {{ window.__donateSlipSyncStop(); }} catch (_e) {{}}
          }}
          const syncUrl = '/dashboard/guild/{current_guild["id"]}/donate/slips.json';
          let syncing = false;
          let timerId = null;
          let started = false;
          let lastEtag = '';

          const syncTable = async () => {{
            if (document.hidden) return;
            if (syncing) return;
            syncing = true;
            try {{
              const headers = {{ 'X-Requested-With': 'XMLHttpRequest' }};
              if (lastEtag) {{
                headers['If-None-Match'] = lastEtag;
              }}
              const response = await fetch(syncUrl, {{
                method: 'GET',
                headers,
              }});
              if (response.status === 304) {{
                if (syncMeta) {{
                  const now = new Date();
                  syncMeta.textContent = `Last sync ${{now.toLocaleTimeString('th-TH')}} (no change)`;
                }}
                return;
              }}
              if (!response.ok) return;
              const incomingEtag = response.headers.get('ETag');
              if (incomingEtag) {{
                lastEtag = incomingEtag;
              }}
              const payload = await response.json();
              if (!payload || !payload.ok) return;
              if (typeof payload.rows_html === 'string') {{
                slipBody.innerHTML = payload.rows_html;
              }}
              if (syncMeta) {{
                const now = new Date();
                syncMeta.textContent = `Last sync ${{now.toLocaleTimeString('th-TH')}} | total ${{payload.count || 0}}`;
              }}
            }} catch (_error) {{
            }} finally {{
              syncing = false;
            }}
          }};

          const startPolling = () => {{
            if (started) return;
            started = true;
            timerId = setInterval(syncTable, 15000);
            setTimeout(syncTable, 1200);
          }};

          const stopPolling = () => {{
            started = false;
            if (timerId) {{
              clearInterval(timerId);
              timerId = null;
            }}
          }};

          const onVisibilityChange = () => {{
            if (document.hidden) {{
              stopPolling();
            }} else {{
              startPolling();
              syncTable();
            }}
          }};

          document.addEventListener('visibilitychange', onVisibilityChange);
          window.addEventListener('beforeunload', stopPolling);
          window.__donateSlipSyncStop = () => {{
            stopPolling();
            document.removeEventListener('visibilitychange', onVisibilityChange);
            window.removeEventListener('beforeunload', stopPolling);
          }};
          startPolling();
        }}
      }})();
