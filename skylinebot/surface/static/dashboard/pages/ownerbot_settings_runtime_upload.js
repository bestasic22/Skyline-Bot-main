(() => {
  const uploadChannelForm = document.querySelector('form[action="/dashboard/admin/ownerbot/upload-channels"]');
  const uploadGuildSelect = uploadChannelForm?.querySelector('select[name="storage_guild_id"]');
  const uploadCreateForm = document.querySelector('form[action="/dashboard/admin/ownerbot/upload-channels/create"]');
  const uploadCreateGuildInput = uploadCreateForm?.querySelector('input[name="storage_guild_id"]');

  if (!(uploadGuildSelect instanceof HTMLSelectElement) || !(uploadCreateGuildInput instanceof HTMLInputElement)) {
    return;
  }

  const syncGuild = () => {
    uploadCreateGuildInput.value = String(uploadGuildSelect.value || '').trim();
  };

  uploadGuildSelect.addEventListener('change', syncGuild);
  syncGuild();
})();

