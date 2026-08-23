(() => {{
  const promptpayNumberRaw = {promptpay_number_js};
  const truemoneyPhoneRaw = {truemoney_phone_js};
  const methodThemeMap = {method_theme_map_json};

  const promptpayNumber = String(promptpayNumberRaw || '').trim();
  const truemoneyPhone = String(truemoneyPhoneRaw || '').trim();

  const donateWrap = document.querySelector('.donate-public-wrap');
  const slipInput = document.getElementById('publicDonateSlipFile');
  const slipLabel = document.getElementById('publicDonateSlipFileLabel');

  const slipForm = document.getElementById('donateSlipForm');
  const slipMethod = document.getElementById('donateSlipMethod');
  const slipAmountInput = document.getElementById('donateSlipAmountInput');
  const transferLinkInput = document.getElementById('donateTransferLinkInput');
  const donorAvatarInput = slipForm ? slipForm.querySelector('input[name="donor_avatar_url"]') : null;
  const evidenceTypeSelect = document.getElementById('donateEvidenceTypeSelect');
  const evidenceTypeHint = document.getElementById('donateEvidenceTypeHint');

  const qrAmountInput = document.getElementById('donateQrAmount');
  const qrMethodInput = document.getElementById('donateQrMethod');
  const qrWrap = document.getElementById('donateQrWrap');
  const qrImage = document.getElementById('donateQrImage');

  const flowMethodButtons = document.querySelectorAll('.donate-flow-method');
  const jumpMethodButtons = document.querySelectorAll('.donate-jump-method');
  const methodSelectButtons = document.querySelectorAll('.donate-method-select-btn');
  const methodCards = document.querySelectorAll('.donate-method-item');
  const methodSelectedValueInput = document.getElementById('donateMethodSelectedValue');

  const promptpayPanel = document.getElementById('donateFlowPromptPayPanel');
  const truemoneyPanel = document.getElementById('donateFlowTrueMoneyPanel');
  const selectedMethodInput = document.getElementById('donateFlowSelectedMethod');

  const giftLinkInput = document.getElementById('donateGiftLinkInput');
  const giftValidateBtn = document.getElementById('donateGiftValidateBtn');
  const giftApplyBtn = document.getElementById('donateGiftApplyBtn');
  const giftValidationHint = document.getElementById('donateGiftValidationHint');

  const qrSaveBtn = document.getElementById('donateQrSaveBtn');
  const methodFlowWrap = document.getElementById('donateMethodFlowWrap');
  const actionHint = document.getElementById('donateFlowActionHint');
  const requiredList = document.getElementById('donateFlowRequiredList');

  const truemoneyGiftRegex = new RegExp('^https?://gift\\.truemoney\\.com/campaign/\\?v=[A-Za-z0-9_-]{{8,}}$', 'i');
  const availableMethods = Array.from(flowMethodButtons || [])
    .map((btn) => String(btn.getAttribute('data-method') || '').toLowerCase())
    .filter(Boolean);

  const requiredByMethod = {{
    promptpay: ['ยอดเงิน (THB)', 'สร้างหรือสแกน QR', 'ส่งสลิป/หลักฐานการโอน'],
    truemoney: ['ยอดเงิน (THB)', 'สร้าง QR หรือใส่ Gift Link', 'ส่งสลิปหรือ Gift Link'],
    bank: ['ยอดเงินที่โอน', 'โอนตามบัญชีที่แสดง', 'แนบสลิปธนาคาร'],
    slipverify: ['ยอดเงินที่โอน', 'แนบสลิปหรือ Gift Link อย่างน้อย 1 รายการ'],
    default: ['ยอดเงินที่โอน', 'แนบหลักฐานการโอนอย่างน้อย 1 รายการ'],
  }};

  const digitsOnly = (value) => String(value || '').replace(/\D+/g, '');

  const phoneByMethod = (method) => {{
    const key = String(method || '').trim().toLowerCase();
    if (key === 'promptpay') return digitsOnly(promptpayNumber);
    if (key === 'truemoney') return digitsOnly(truemoneyPhone || promptpayNumber);
    return '';
  }};

  const hasQrForMethod = (method) => Boolean(phoneByMethod(method));
  const isValidTrueMoneyGiftLink = (rawLink) => {{
    const link = String(rawLink || '').trim();
    return !!link && truemoneyGiftRegex.test(link);
  }};
  const isValidHttpUrl = (rawUrl) => /^https?:\/\/\S+$/i.test(String(rawUrl || '').trim());
  const normalizeEvidenceType = (rawType) => {{
    const value = String(rawType || '').trim().toLowerCase();
    if (value === 'gift' || value === 'truemoney') return 'gift';
    if (value === 'slip' || value === 'file') return 'slip';
    return 'auto';
  }};

  const setButtonDisabled = (button, disabled) => {{
    if (!button) return;
    button.disabled = !!disabled;
    button.classList.toggle('is-disabled', !!disabled);
    button.style.opacity = disabled ? '.6' : '';
    button.style.cursor = disabled ? 'not-allowed' : '';
  }};

  const setButtonReason = (button, reason) => {{
    if (!button) return;
    const text = String(reason || '').trim();
    if (text) {{
      button.title = text;
      button.setAttribute('aria-label', text);
    }} else {{
      button.removeAttribute('title');
      button.removeAttribute('aria-label');
    }}
  }};

  const renderGiftHint = (rawLink) => {{
    if (!giftValidationHint) return;
    const link = String(rawLink || '').trim();
    giftValidationHint.classList.remove('ok', 'warn');
    if (!link) {{
      giftValidationHint.textContent = 'วางลิงก์ของขวัญ TrueMoney แล้วกดตรวจสอบก่อนใช้งาน';
      return;
    }}
    if (isValidTrueMoneyGiftLink(link)) {{
      giftValidationHint.textContent = 'ลิงก์ถูกต้อง สามารถนำไปใช้ในฟอร์มส่งสลิปได้';
      giftValidationHint.classList.add('ok');
      return;
    }}
    giftValidationHint.textContent = 'ลิงก์ไม่ถูกต้อง ต้องเป็น gift.truemoney.com/campaign/?v=...';
    giftValidationHint.classList.add('warn');
  }};

  const renderEvidenceHint = () => {{
    if (!evidenceTypeHint) return;
    const evidenceType = normalizeEvidenceType(evidenceTypeSelect?.value || 'auto');
    if (evidenceType === 'gift') {{
      evidenceTypeHint.textContent = 'Gift Link mode: please provide a valid TrueMoney gift link.';
      return;
    }}
    if (evidenceType === 'slip') {{
      evidenceTypeHint.textContent = 'Slip mode: please upload a slip image file.';
      return;
    }}
    evidenceTypeHint.textContent = 'Auto mode: submit either a Gift Link or a Slip file.';
  }};

  const syncMethodToForm = (method) => {{
    const m = String(method || '').trim().toLowerCase();
    if (!m) return;
    if (slipMethod) slipMethod.value = m;
    if (qrMethodInput && (m === 'promptpay' || m === 'truemoney')) {{
      qrMethodInput.value = m;
    }}
  }};

  const applyMethodTheme = (method) => {{
    if (!donateWrap) return;
    const key = String(method || '').trim().toLowerCase();
    const tone = methodThemeMap && methodThemeMap[key] ? methodThemeMap[key] : null;
    if (!tone) return;
    const c1 = String(tone.color || '').trim();
    const c2 = String(tone.color2 || '').trim();
    if (c1) donateWrap.style.setProperty('--donate-accent', c1);
    if (c2) donateWrap.style.setProperty('--donate-accent-2', c2);
  }};

  const applyMethodCardFilter = (method) => {{
    const selected = String(method || '').trim().toLowerCase();
    let hasVisible = false;
    methodCards.forEach((card) => {{
      const cardMethod = String(card.getAttribute('data-method') || '').trim().toLowerCase();
      const show = !selected || cardMethod === selected;
      card.style.display = show ? '' : 'none';
      if (show) hasVisible = true;
    }});
    if (!hasVisible && selected) {{
      methodCards.forEach((card) => {{
        card.style.display = '';
      }});
    }}

    methodSelectButtons.forEach((btn) => {{
      const btnMethod = String(btn.getAttribute('data-method') || '').trim().toLowerCase();
      btn.classList.toggle('active', !!selected && btnMethod === selected);
    }});

    if (methodSelectedValueInput) methodSelectedValueInput.value = selected;
    applyMethodTheme(selected);
  }};

  const updateRequiredList = (method) => {{
    if (!requiredList) return;
    const key = String(method || '').trim().toLowerCase();
    const rows = requiredByMethod[key] || requiredByMethod.default;
    requiredList.innerHTML = rows.map((text) => `<li>${{String(text || '')}}</li>`).join('');
  }};

  const getActiveMethod = () => String(selectedMethodInput?.value || '').trim().toLowerCase();
  const getQrMethod = () => String(qrMethodInput?.value || '').trim().toLowerCase();
  const currentAmountValue = () => Number(qrAmountInput?.value || 0);
  const hasAmountValue = () => Number.isFinite(currentAmountValue()) && currentAmountValue() > 0;

  const showQr = (url) => {{
    if (!qrWrap || !qrImage) return;
    if (!url) {{
      qrWrap.style.display = 'none';
      qrImage.removeAttribute('src');
      return;
    }}
    qrImage.src = url;
    qrWrap.style.display = 'block';
  }};

  const renderQrPreview = () => {{
    if (!qrAmountInput || !qrMethodInput) return;
    const method = getQrMethod();
    const amount = currentAmountValue();
    syncMethodToForm(method);

    const phone = phoneByMethod(method);
    if (!phone || !Number.isFinite(amount) || amount <= 0) {{
      showQr('');
      return;
    }}

    const fixedAmount = Math.round(amount * 100) / 100;
    const qrUrl = `https://promptpay.io/${{encodeURIComponent(phone)}}/${{encodeURIComponent(String(fixedAmount))}}.png`;
    showQr(qrUrl);

    if (slipAmountInput) {{
      slipAmountInput.value = String(Math.max(1, Math.round(fixedAmount)));
    }}
  }};

  const updateActionButtons = () => {{
    const activeMethod = getActiveMethod();
    const qrMethod = getQrMethod() || activeMethod;
    const qrReady = hasQrForMethod(qrMethod);
    const hasAmount = hasAmountValue();
    const canGenerate = (activeMethod === 'promptpay' || activeMethod === 'truemoney') && qrReady && hasAmount;

    setButtonDisabled(qrSaveBtn, !canGenerate);

    let reason = '';
    if (!(activeMethod === 'promptpay' || activeMethod === 'truemoney')) {{
      reason = 'ช่องทางนี้ไม่ได้ใช้การสร้าง QR';
    }} else if (!qrReady) {{
      reason = 'ยังไม่มีหมายเลขสำหรับสร้าง QR ของช่องทางนี้';
    }} else if (!hasAmount) {{
      reason = 'กรอกจำนวนเงินก่อนสร้าง QR';
    }} else {{
      reason = 'พร้อมสร้าง QR';
    }}
    setButtonReason(qrSaveBtn, reason);

    if (actionHint) {{
      actionHint.classList.remove('ok', 'warn');
      if (activeMethod === 'bank') {{
        actionHint.textContent = 'ช่องทาง Bank ไม่ต้องสร้าง QR ให้โอนตามข้อมูลบัญชีและส่งสลิปได้เลย';
      }} else if (activeMethod === 'slipverify') {{
        actionHint.textContent = 'สามารถส่งสลิปหรือหลักฐานในฟอร์มด้านล่างได้ทันที';
      }} else if (!qrReady) {{
        actionHint.textContent = 'ช่องทางนี้ยังไม่พร้อมสร้าง QR เพราะยังไม่มีหมายเลขที่ตั้งค่าไว้';
        actionHint.classList.add('warn');
      }} else if (!hasAmount) {{
        actionHint.textContent = 'กรอกจำนวนเงินก่อนสร้าง QR';
        actionHint.classList.add('warn');
      }} else {{
        actionHint.textContent = 'กด Generate QR Code เพื่อสร้าง QR ของช่องทางที่เลือก';
        actionHint.classList.add('ok');
      }}
    }}
  }};

  const switchMethodPanels = (method) => {{
    const m = String(method || '').trim().toLowerCase();
    if (selectedMethodInput) selectedMethodInput.value = m;
    applyMethodCardFilter(m);
    updateRequiredList(m);

    const isQrMethod = m === 'promptpay' || m === 'truemoney';
    if (promptpayPanel) promptpayPanel.style.display = isQrMethod ? '' : 'none';
    if (truemoneyPanel) truemoneyPanel.style.display = m === 'truemoney' ? '' : 'none';

    if (m) syncMethodToForm(m);

    flowMethodButtons.forEach((btn) => {{
      const active = String(btn.getAttribute('data-method') || '').toLowerCase() === m;
      btn.classList.toggle('active', active);
    }});

    jumpMethodButtons.forEach((btn) => {{
      const active = String(btn.getAttribute('data-method') || '').toLowerCase() === m;
      btn.classList.toggle('active', active);
    }});

    if (!isQrMethod) {{
      showQr('');
    }} else if (qrMethodInput && (m === 'promptpay' || m === 'truemoney')) {{
      qrMethodInput.value = m;
      renderQrPreview();
    }}

    updateActionButtons();
  }};

  document.querySelectorAll('.donate-copy-btn').forEach((btn) => {{
    const originalLabel = btn.textContent || '';
    btn.addEventListener('click', async () => {{
      const value = btn.getAttribute('data-copy') || '';
      if (!value) return;
      try {{
        await navigator.clipboard.writeText(value);
        btn.textContent = 'คัดลอกแล้ว';
        window.setTimeout(() => {{
          btn.textContent = originalLabel;
        }}, 1200);
      }} catch (_error) {{
      }}
    }});
  }});

  if (slipInput && slipLabel) {{
    slipInput.addEventListener('change', () => {{
      const file = slipInput.files && slipInput.files[0];
      slipLabel.textContent = file ? `เลือกไฟล์: ${{file.name}}` : 'รองรับ png/jpg/jpeg/webp';
    }});
  }}

  flowMethodButtons.forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const method = btn.getAttribute('data-method') || '';
      switchMethodPanels(method);
      if (String(method).toLowerCase() === 'slipverify' && slipForm) {{
        slipForm.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }}
    }});
  }});

  jumpMethodButtons.forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const method = btn.getAttribute('data-method') || '';
      switchMethodPanels(method);
      if (methodFlowWrap) {{
        methodFlowWrap.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }}
    }});
  }});

  methodSelectButtons.forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const method = String(btn.getAttribute('data-method') || '').trim().toLowerCase();
      if (!method) return;
      switchMethodPanels(method);
      if (method === 'slipverify' && slipForm) {{
        slipForm.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }}
    }});
  }});

  qrSaveBtn?.addEventListener('click', () => {{
    const activeMethod = getActiveMethod();
    const qrMethod = getQrMethod() || activeMethod;
    if (!(activeMethod === 'promptpay' || activeMethod === 'truemoney')) {{
      alert('ช่องทางนี้ไม่ได้ใช้การสร้าง QR');
      return;
    }}
    if (!hasQrForMethod(qrMethod)) {{
      alert('ยังไม่พบหมายเลขสำหรับสร้าง QR ของช่องทางนี้');
      return;
    }}

    const amount = currentAmountValue();
    if (!Number.isFinite(amount) || amount <= 0) {{
      alert('กรุณากรอกจำนวนเงินให้ถูกต้อง');
      qrAmountInput?.focus();
      return;
    }}

    renderQrPreview();
    updateActionButtons();
  }});

  giftValidateBtn?.addEventListener('click', () => {{
    const link = String(giftLinkInput?.value || '').trim();
    renderGiftHint(link);
    if (!link) {{
      alert('กรุณากรอกลิงก์ของขวัญ TrueMoney');
      giftLinkInput?.focus();
      return;
    }}
    if (!isValidTrueMoneyGiftLink(link)) {{
      alert('ลิงก์ไม่ถูกต้อง ต้องเป็น gift.truemoney.com/campaign/?v=...');
      giftLinkInput?.focus();
      return;
    }}
    alert('ลิงก์ของขวัญถูกต้อง');
  }});

  giftApplyBtn?.addEventListener('click', () => {{
    const link = String(giftLinkInput?.value || '').trim();
    if (!link) {{
      alert('กรุณากรอกลิงก์ของขวัญ TrueMoney');
      giftLinkInput?.focus();
      return;
    }}
    if (!isValidTrueMoneyGiftLink(link)) {{
      alert('ลิงก์ไม่ถูกต้อง ต้องเป็น gift.truemoney.com/campaign/?v=...');
      giftLinkInput?.focus();
      return;
    }}

    renderGiftHint(link);
    if (transferLinkInput) transferLinkInput.value = link;
    syncMethodToForm('truemoney');

    if (slipForm) {{
      slipForm.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }} else {{
      alert('ยังไม่เปิดฟอร์มส่งสลิปสำหรับหน้านี้');
    }}
  }});

  giftLinkInput?.addEventListener('input', () => {{
    renderGiftHint(giftLinkInput.value || '');
  }});

  evidenceTypeSelect?.addEventListener('change', () => {{
    renderEvidenceHint();
  }});

  qrAmountInput?.addEventListener('input', () => {{
    if (slipAmountInput) {{
      slipAmountInput.value = String(qrAmountInput.value || '');
    }}
    renderQrPreview();
    updateActionButtons();
  }});

  qrMethodInput?.addEventListener('change', () => {{
    const selected = String(qrMethodInput?.value || '').toLowerCase();
    if (selected === 'promptpay' || selected === 'truemoney') {{
      switchMethodPanels(selected);
    }}
    renderQrPreview();
    updateActionButtons();
  }});

  const initialMethod = String(
    methodSelectedValueInput?.value || selectedMethodInput?.value || slipMethod?.value || availableMethods[0] || ''
  ).toLowerCase();
  if (initialMethod) {{
    switchMethodPanels(initialMethod);
  }} else {{
    applyMethodCardFilter('');
    updateRequiredList('default');
  }}

  renderQrPreview();
  updateActionButtons();
  renderGiftHint(giftLinkInput?.value || '');
  renderEvidenceHint();

  if (slipForm) {{
    slipForm.addEventListener('submit', (event) => {{
      const amountInput = slipForm.querySelector('input[name="amount"]');
      const amount = Number(amountInput?.value || 0);
      if (!Number.isFinite(amount) || amount <= 0) {{
        event.preventDefault();
        alert('จำนวนเงินต้องมากกว่า 0');
        return;
      }}

      const paymentMethod = String(slipMethod?.value || getActiveMethod() || '').toLowerCase();
      const evidenceType = normalizeEvidenceType(evidenceTypeSelect?.value || 'auto');
      const transferLink = String(slipForm.querySelector('input[name="transfer_link"]')?.value || '').trim();
      const hasFile = !!(slipInput && slipInput.files && slipInput.files.length > 0);
      const donorAvatarUrl = String(donorAvatarInput?.value || '').trim();

      if (donorAvatarUrl && !isValidHttpUrl(donorAvatarUrl)) {{
        event.preventDefault();
        alert('Donor Avatar URL must start with http:// or https://');
        donorAvatarInput?.focus();
        return;
      }}

      if (evidenceType === 'gift') {{
        if (!transferLink) {{
          event.preventDefault();
          alert('Please provide a TrueMoney Gift Link.');
          transferLinkInput?.focus();
          return;
        }}
        if (!isValidTrueMoneyGiftLink(transferLink)) {{
          event.preventDefault();
          alert('TrueMoney link is invalid (gift.truemoney.com/campaign/?v=...)');
          transferLinkInput?.focus();
          return;
        }}
        if (slipMethod && Array.from(slipMethod.options || []).some((opt) => String(opt?.value || '').toLowerCase() === 'truemoney')) {{
          slipMethod.value = 'truemoney';
        }}
      }}

      if (evidenceType === 'slip' && !hasFile) {{
        event.preventDefault();
        alert('Please upload a slip file.');
        slipInput?.focus();
        return;
      }}
      if (!hasFile && !transferLink) {{
        event.preventDefault();
        alert('กรุณาแนบสลิปหรือใส่ลิงก์อ้างอิงอย่างน้อย 1 รายการ');
        return;
      }}

      if (paymentMethod === 'truemoney' && transferLink && !isValidTrueMoneyGiftLink(transferLink)) {{
        event.preventDefault();
        alert('ลิงก์ TrueMoney ไม่ถูกต้อง (ต้องเป็น gift.truemoney.com/campaign/?v=...)');
        return;
      }}
    }});
  }}
}})();
