(() => {
  const providerSelect = document.getElementById('ownerbotGlobalAiProvider');
  const modelSelect = document.getElementById('ownerbotGlobalAiModel');
  const guideRowsRoot = document.getElementById('ownerbotAiModelGuideRows');

  if (!(providerSelect instanceof HTMLSelectElement)) {
    return;
  }

  const normalize = (value) => String(value || '').trim().toLowerCase();

  const applyProvider = () => {
    const provider = normalize(providerSelect.value);

    if (modelSelect instanceof HTMLSelectElement) {
      const options = Array.from(modelSelect.options || []);
      let firstVisible = '';
      options.forEach((option) => {
        if (!(option instanceof HTMLOptionElement)) {
          return;
        }
        const optionProvider = normalize(option.getAttribute('data-provider'));
        const visible = optionProvider === provider;
        option.hidden = !visible;
        if (visible && !firstVisible) {
          firstVisible = option.value;
        }
      });
      const selectedOption = modelSelect.selectedOptions && modelSelect.selectedOptions[0];
      if (!(selectedOption instanceof HTMLOptionElement) || selectedOption.hidden) {
        modelSelect.value = firstVisible || '';
      }
    }

    if (guideRowsRoot instanceof HTMLElement) {
      const rows = Array.from(guideRowsRoot.querySelectorAll('tr[data-provider]'));
      rows.forEach((row) => {
        if (!(row instanceof HTMLElement)) {
          return;
        }
        const rowProvider = normalize(row.getAttribute('data-provider'));
        row.style.display = rowProvider === provider ? '' : 'none';
      });
    }
  };

  providerSelect.addEventListener('change', applyProvider);
  applyProvider();
})();

