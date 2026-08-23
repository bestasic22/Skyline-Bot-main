(() => {{
        const form = document.getElementById('tempChannelsForm');
        if (!form) return;
        const modeInput = document.getElementById('tempInterfaceModeInput');
        const tabTextBtn = document.getElementById('tempTabTextBtn');
        const tabEmbedBtn = document.getElementById('tempTabEmbedBtn');
	        const embedEditor = document.getElementById('tempEmbedEditor');
	        const colorInput = document.getElementById('tempEmbedColorInput');
	        const contentInput = document.getElementById('tempInterfaceContentInput');
	        const contentWrap = document.getElementById('tempInterfaceContentWrap');
	        const sendBtn = document.getElementById('tempSendInterfaceBtn');
	        const authorIconInput = document.getElementById('tempAuthorIconInput');
	        const thumbInput = document.getElementById('tempThumbnailInput');
	        const imageInput = document.getElementById('tempImageInput');
	        const footerIconInput = document.getElementById('tempFooterIconInput');
	        const authorIconFileInput = document.getElementById('tempAuthorIconFileInput');
	        const thumbnailFileInput = document.getElementById('tempThumbnailFileInput');
	        const imageFileInput = document.getElementById('tempImageFileInput');
	        const footerIconFileInput = document.getElementById('tempFooterIconFileInput');
        const authorIconPicker = document.getElementById('tempAuthorIconPicker');
        const thumbPicker = document.getElementById('tempThumbPicker');
        const imagePicker = document.getElementById('tempImagePicker');
        const footerIconPicker = document.getElementById('tempFooterIconPicker');
        const addFieldBtn = document.getElementById('tempAddFieldBtn');
        const fieldsWrap = document.getElementById('tempFieldsWrap');
        const fieldsJsonInput = document.getElementById('tempFieldsJsonInput');
        let fields = [];
        try {{
          const decoded = JSON.parse(fieldsJsonInput?.value || '[]');
          fields = Array.isArray(decoded) ? decoded : [];
        }} catch (_error) {{
          fields = [];
        }}

	        const bindFilePreview = (pickerEl, fileInputEl, hiddenUrlInputEl) => {{
	          if (!pickerEl || !fileInputEl) return;
	          fileInputEl.addEventListener('change', () => {{
	            const file = fileInputEl.files && fileInputEl.files[0] ? fileInputEl.files[0] : null;
	            if (!file) {{
	              pickerEl.removeAttribute('data-local-preview');
	              paintImageButtons();
	              return;
	            }}
	            if (hiddenUrlInputEl) hiddenUrlInputEl.value = '';
	            const reader = new FileReader();
	            reader.onload = () => {{
	              pickerEl.setAttribute('data-local-preview', String(reader.result || ''));
	              paintImageButtons();
	            }};
	            reader.readAsDataURL(file);
	          }});
	        }};

        const paintImageButtons = () => {{
          const setBackground = (el, url) => {{
            if (!el) return;
	            const localPreview = String(el.getAttribute('data-local-preview') || '').trim();
	            const finalUrl = String(localPreview || url || '').trim();
	            if (finalUrl) {{
	              el.style.backgroundImage = `linear-gradient(rgba(0,0,0,.35), rgba(0,0,0,.35)), url(${{finalUrl}})`;
              el.style.backgroundSize = 'cover';
              el.style.backgroundPosition = 'center';
              el.style.color = '#fff';
            }} else {{
              el.style.backgroundImage = '';
              el.style.color = '';
            }}
          }};
          setBackground(authorIconPicker, authorIconInput?.value || '');
          setBackground(thumbPicker, thumbInput?.value || '');
          setBackground(imagePicker, imageInput?.value || '');
          setBackground(footerIconPicker, footerIconInput?.value || '');
        }};
        const syncFields = () => {{
          if (!fieldsJsonInput) return;
          fieldsJsonInput.value = JSON.stringify(fields || []);
        }};
        const renderFields = () => {{
          if (!fieldsWrap) return;
          fieldsWrap.innerHTML = (fields || []).map((field, index) => `
            <article class="embed-field-row">
              <div style="display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;">
                <input data-temp-field-name="${{index}}" type="text" maxlength="256" value="${{String(field?.name || '').replaceAll('"','&quot;')}}" placeholder="หัวข้อ">
                <div style="display:flex;gap:8px;align-items:center;">
	                  <button type="button" class="sb-field-ctrl ${{String(field?.align || 'left') === 'center' ? 'active' : ''}}" data-temp-field-align="${{index}}" title="จัดตำแหน่ง"></button>
                  <button type="button" class="sb-field-ctrl" data-temp-field-remove="${{index}}" title="ลบ" style="color:#ef4444;"></button>
                </div>
              </div>
	              <textarea data-temp-field-value="${{index}}" style="min-height:78px;margin-top:8px;text-align:${{String(field?.align || 'left') === 'center' ? 'center' : 'left'}};" placeholder="">${{String(field?.value || '').replaceAll('<','&lt;').replaceAll('>','&gt;')}}</textarea>
            </article>
          `).join('');
          fieldsWrap.querySelectorAll('[data-temp-field-name],[data-temp-field-value]').forEach((el) => {{
            const update = () => {{
              const idx = Number(el.getAttribute('data-temp-field-name') || el.getAttribute('data-temp-field-value'));
              if (!Number.isFinite(idx) || !fields[idx]) return;
              if (el.hasAttribute('data-temp-field-name')) fields[idx].name = String(el.value || '').slice(0, 256);
              if (el.hasAttribute('data-temp-field-value')) fields[idx].value = String(el.value || '').slice(0, 1024);
              syncFields();
            }};
            el.addEventListener('input', update);
            el.addEventListener('change', update);
          }});
	          fieldsWrap.querySelectorAll('[data-temp-field-align]').forEach((btn) => {{
	            btn.addEventListener('click', () => {{
	              const idx = Number(btn.getAttribute('data-temp-field-align'));
	              if (!Number.isFinite(idx) || !fields[idx]) return;
	              fields[idx].align = String(fields[idx].align || 'left') === 'center' ? 'left' : 'center';
	              renderFields();
	              syncFields();
	            }});
	          }});
          fieldsWrap.querySelectorAll('[data-temp-field-remove]').forEach((btn) => {{
            btn.addEventListener('click', () => {{
              const idx = Number(btn.getAttribute('data-temp-field-remove'));
              if (!Number.isFinite(idx)) return;
              fields.splice(idx, 1);
              renderFields();
              syncFields();
            }});
          }});
        }};

        const setMode = (nextMode) => {{
          const mode = nextMode === 'text' ? 'text' : 'embed';
	          if (modeInput) modeInput.value = mode;
	          if (tabTextBtn) tabTextBtn.className = mode === 'text' ? 'primary-btn' : 'ghost-btn';
	          if (tabEmbedBtn) tabEmbedBtn.className = mode === 'embed' ? 'primary-btn' : 'ghost-btn';
	          if (embedEditor) embedEditor.style.display = mode === 'embed' ? '' : 'none';
	          if (contentWrap) contentWrap.style.display = mode === 'text' ? '' : 'none';
	        }};

        tabTextBtn?.addEventListener('click', () => setMode('text'));
        tabEmbedBtn?.addEventListener('click', () => setMode('embed'));
        setMode((modeInput?.value || 'embed'));

        form.querySelectorAll('[data-step-target]').forEach((btn) => {{
          btn.addEventListener('click', () => {{
            const targetName = String(btn.getAttribute('data-step-target') || '');
            const delta = Number(btn.getAttribute('data-step-delta') || '0');
            if (!targetName || !Number.isFinite(delta)) return;
            const input = form.querySelector(`input[name="${{targetName}}"]`);
            if (!input) return;
            const min = Number(input.min || '0');
            const max = Number(input.max || '999999');
            const current = Number(input.value || '0');
            const next = Math.max(min, Math.min(max, current + delta));
            input.value = String(next);
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          }});
        }});

        document.querySelectorAll('.embed-color-dot').forEach((dot) => {{
          dot.addEventListener('click', () => {{
            const value = String(dot.getAttribute('data-color') || '#5865F2');
            if (colorInput) colorInput.value = value;
            if (embedEditor) embedEditor.style.borderLeftColor = value;
          }});
        }});
        colorInput?.addEventListener('input', () => {{
          if (embedEditor) embedEditor.style.borderLeftColor = colorInput.value || '#5865F2';
        }});
	        authorIconPicker?.addEventListener('click', () => authorIconFileInput?.click());
	        thumbPicker?.addEventListener('click', () => thumbnailFileInput?.click());
	        imagePicker?.addEventListener('click', () => imageFileInput?.click());
	        footerIconPicker?.addEventListener('click', () => footerIconFileInput?.click());
	        bindFilePreview(authorIconPicker, authorIconFileInput, authorIconInput);
	        bindFilePreview(thumbPicker, thumbnailFileInput, thumbInput);
	        bindFilePreview(imagePicker, imageFileInput, imageInput);
	        bindFilePreview(footerIconPicker, footerIconFileInput, footerIconInput);
        addFieldBtn?.addEventListener('click', () => {{
	          fields.push({{
	            id: `field_${{Date.now()}}_${{Math.floor(Math.random() * 1000)}}`,
	            name: 'หัวข้อ',
	            value: '',
	            inline: false,
	            align: 'left',
	          }});
          renderFields();
          syncFields();
        }});
        renderFields();
        syncFields();
        paintImageButtons();

        sendBtn?.addEventListener('click', async () => {{
          if (!sendBtn) return;
          try {{
            sendBtn.disabled = true;
            const body = new URLSearchParams(new FormData(form));
            const response = await fetch(`{send_interface_endpoint}`, {{
              method: 'POST',
              headers: {{
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'X-Requested-With': 'fetch',
              }},
              credentials: 'same-origin',
              body,
            }});
            const payload = await response.json().catch(() => ({{ ok: false, message: 'ไม่สำเร็จ' }}));
            alert(String(payload?.message || (response.ok ? '' : '')));
          }} catch (_error) {{
            alert('ͫ');
          }} finally {{
            sendBtn.disabled = false;
          }}
        }});
      }})();
