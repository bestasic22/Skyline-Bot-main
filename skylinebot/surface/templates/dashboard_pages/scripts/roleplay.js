(() => {{
  const settingsForm = document.getElementById("roleplaySettingsForm");
  if (settingsForm) {{
    const saveBar = document.getElementById("roleplaySaveBar");
    const saveBarText = document.getElementById("roleplaySaveBarText");
    const applyPresetButton = document.getElementById("rpApplyPresetButton");

    const buildSignature = () => {{
      const payload = new FormData(settingsForm);
      payload.delete("action");
      const pairs = [];
      for (const [key, value] of payload.entries()) {{
        pairs.push(String(key) + "=" + String(value));
      }}
      pairs.sort();
      return pairs.join("&");
    }};

    const setDirty = (dirty) => {{
      if (!saveBar) return;
      saveBar.hidden = !dirty;
      if (saveBarText) {{
        saveBarText.textContent = dirty ? "Unsaved changes in roleplay settings." : "All changes saved.";
      }}
    }};

    const canEditField = () => {{
      const allowCustom = settingsForm.querySelector('input[name="allow_custom_config"]');
      return Boolean(allowCustom && allowCustom.checked);
    }};

    const syncConfigLock = () => {{
      const customEditable = canEditField();
      const targets = Array.from(settingsForm.querySelectorAll("input, select, textarea")).filter((el) => {{
        const name = String(el.getAttribute("name") || "");
        if (!name) return false;
        if (name === "action") return false;
        if (name === "allow_custom_config") return false;
        return true;
      }});
      targets.forEach((el) => {{
        const attr = el.getAttribute("data-rp-force-enabled");
        if (attr === "true") return;
        const isPreset = String(el.getAttribute("name") || "") === "preset_key";
        if (!customEditable && !isPreset) {{
          el.setAttribute("disabled", "disabled");
        }} else {{
          el.removeAttribute("disabled");
        }}
      }});
    }};

    let initialSignature = buildSignature();
    const refreshDirty = () => setDirty(buildSignature() !== initialSignature);

    settingsForm.addEventListener("input", refreshDirty);
    settingsForm.addEventListener("change", (event) => {{
      const target = event.target;
      if (target instanceof HTMLInputElement && target.name === "allow_custom_config") {{
        syncConfigLock();
      }}
      refreshDirty();
    }});
    settingsForm.addEventListener("submit", () => {{
      if (saveBarText) saveBarText.textContent = "Saving roleplay settings...";
    }});

    applyPresetButton?.addEventListener("click", (event) => {{
      const ok = window.confirm("Apply City Roleplay starter pack now? This will configure RP defaults, scenarios, and economy guard.");
      if (!ok) {{
        event.preventDefault();
      }}
    }});

    syncConfigLock();
    refreshDirty();
  }}

  const scenarioDeleteForm = document.getElementById("roleplayScenarioDeleteForm");
  scenarioDeleteForm?.addEventListener("submit", (event) => {{
    const select = scenarioDeleteForm.querySelector('select[name="delete_scenario_id"]');
    const value = select instanceof HTMLSelectElement ? String(select.value || "").trim() : "";
    if (!value) {{
      event.preventDefault();
      return;
    }}
    const ok = window.confirm("Delete this custom scenario?");
    if (!ok) {{
      event.preventDefault();
    }}
  }});

  const eventStartForm = document.getElementById("roleplayStartEventForm");
  eventStartForm?.addEventListener("submit", (event) => {{
    const ok = window.confirm("Start a new roleplay event now?");
    if (!ok) {{
      event.preventDefault();
    }}
  }});

  const eventEndForm = document.getElementById("roleplayEndEventForm");
  eventEndForm?.addEventListener("submit", (event) => {{
    const ok = window.confirm("End active event and reward participants?");
    if (!ok) {{
      event.preventDefault();
    }}
  }});

  document.querySelectorAll(".rpDeleteScheduleButton").forEach((btn) => {{
    btn.addEventListener("click", (event) => {{
      const ok = window.confirm("Delete this scheduler rule?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }});

  document.querySelectorAll(".rpRollbackButton").forEach((btn) => {{
    btn.addEventListener("click", (event) => {{
      const ok = window.confirm("Rollback to the snapshot before this action?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }});

  const importFormAction = document.querySelector('form input[name="action"][value="import_config"]');
  if (importFormAction && importFormAction.form) {{
    importFormAction.form.addEventListener("submit", (event) => {{
      const ok = window.confirm("Import RP config and replace current RP setup?");
      if (!ok) {{
        event.preventDefault();
      }}
    }});
  }}
}})();
