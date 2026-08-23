(() => {
  const statusForm = document.querySelector('form[action="/dashboard/admin/ownerbot/status"]');
  if (!(statusForm instanceof HTMLFormElement)) {
    return;
  }
  const levelSelect = statusForm.querySelector('select[name="dashboard_status_override_level"]');
  const activitySelect = statusForm.querySelector('select[name="dashboard_status_override_activity"]');
  const messageInput = statusForm.querySelector('textarea[name="dashboard_status_override_message"]');
  const autoResetButton = statusForm.querySelector('button[name="dashboard_status_force_auto"]');

  if (
    autoResetButton instanceof HTMLButtonElement
    && levelSelect instanceof HTMLSelectElement
    && activitySelect instanceof HTMLSelectElement
  ) {
    autoResetButton.addEventListener('click', () => {
      levelSelect.value = 'auto';
      activitySelect.value = 'auto';
      if (messageInput instanceof HTMLTextAreaElement) {
        messageInput.value = '';
      }
    });
  }
})();

