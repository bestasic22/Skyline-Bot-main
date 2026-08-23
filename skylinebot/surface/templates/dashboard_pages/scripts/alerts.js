(() => {{
  const form = document.getElementById("alertsSettingsForm");
  if (!form) return;

  const seed = JSON.parse({json.dumps(platform_seed_json)});
  const managedKeys = JSON.parse({json.dumps(managed_platform_keys_json)});
  const channelOptions = {json.dumps(channel_options_html)};
  const allKeys = ["twitch", "youtube", "tiktok", "github", "facebook", "x"];
  const keys = Array.isArray(managedKeys) && managedKeys.length
    ? managedKeys.filter((key) => allKeys.includes(key))
    : allKeys;

  const platformLabel = {{
    twitch: "Twitch",
    youtube: "YouTube",
    tiktok: "TikTok",
    github: "GitHub",
    facebook: "Facebook",
    x: "X",
  }};
  const sourcePlaceholder = {{
    twitch: "เช่น https://www.twitch.tv/your_channel",
    youtube: "เช่น https://www.youtube.com/@channel",
    tiktok: "เช่น https://www.tiktok.com/@username",
    github: "เช่น https://github.com/owner/repo",
    facebook: "เช่น https://www.facebook.com/page.name",
    x: "เช่น https://x.com/username",
  }};

  const state = {{
    twitch: Array.isArray(seed.twitch) ? seed.twitch : [],
    youtube: Array.isArray(seed.youtube) ? seed.youtube : [],
    tiktok: Array.isArray(seed.tiktok) ? seed.tiktok : [],
    github: Array.isArray(seed.github) ? seed.github : [],
    facebook: Array.isArray(seed.facebook) ? seed.facebook : [],
    x: Array.isArray(seed.x) ? seed.x : [],
  }};
  keys.forEach((key) => {{
    if (!Array.isArray(state[key])) state[key] = [];
  }});

  const esc = (value) => String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;");

  const syncRow = (el) => {{
    const key =
      el.getAttribute("data-entry-url") ||
      el.getAttribute("data-entry-desc") ||
      el.getAttribute("data-entry-btn") ||
      el.getAttribute("data-entry-channel");
    const idx = Number(el.getAttribute("data-entry-index") || -1);
    if (!key || !Number.isFinite(idx) || idx < 0 || !state[key] || !state[key][idx]) return;
    const wrap = document.getElementById(`entries_${{key}}`);
    if (!wrap) return;
    state[key][idx].source_url = wrap.querySelector(`input[data-entry-url="${{key}}"][data-entry-index="${{idx}}"]`)?.value || "";
    state[key][idx].description = wrap.querySelector(`textarea[data-entry-desc="${{key}}"][data-entry-index="${{idx}}"]`)?.value || "";
    state[key][idx].button_text = wrap.querySelector(`input[data-entry-btn="${{key}}"][data-entry-index="${{idx}}"]`)?.value || "";
    state[key][idx].channel_id = wrap.querySelector(`select[data-entry-channel="${{key}}"][data-entry-index="${{idx}}"]`)?.value || "";
  }};

  const renderEntries = (key) => {{
    const wrap = document.getElementById(`entries_${{key}}`);
    if (!wrap) return;
    const rows = state[key] || [];
    wrap.innerHTML = rows.map((row, idx) => `
      <div class="panel-sub" style="margin:8px 0;padding:10px;">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px;">
          <strong>รายการ ${{idx + 1}}</strong>
          <button type="button" class="danger-btn" style="padding:4px 10px;" data-remove-entry="${{key}}" data-remove-index="${{idx}}">ลบ</button>
        </div>
        <div class="field-item" style="margin-bottom:8px;">
          <label>ลิงก์ต้นทาง / แหล่งข้อมูล</label>
          <input type="text" data-entry-url="${{key}}" data-entry-index="${{idx}}" value="${{esc(row.source_url || "")}}" placeholder="${{esc(sourcePlaceholder[key] || "วางลิงก์ที่ต้องการติดตาม")}}">
        </div>
        <div class="field-item" style="margin-bottom:8px;">
          <label>คำอธิบาย</label>
          <textarea data-entry-desc="${{key}}" data-entry-index="${{idx}}" style="min-height:70px;" placeholder="อธิบายแหล่งที่มาสั้น ๆ">${{esc(row.description || "")}}</textarea>
        </div>
        <div class="field-group" style="margin-bottom:0;">
          <div class="field-item">
            <label>ข้อความปุ่ม (สูงสุด 45 ตัวอักษร)</label>
            <input type="text" maxlength="45" data-entry-btn="${{key}}" data-entry-index="${{idx}}" value="${{esc(row.button_text || "ดูรายละเอียด")}}" placeholder="ดูรายละเอียด">
          </div>
          <div class="field-item">
            <label>ห้องแจ้งเตือน</label>
            <select data-entry-channel="${{key}}" data-entry-index="${{idx}}">${{channelOptions}}</select>
          </div>
        </div>
      </div>
    `).join("");

    rows.forEach((row, idx) => {{
      const select = wrap.querySelector(`select[data-entry-channel="${{key}}"][data-entry-index="${{idx}}"]`);
      if (select) select.value = String(row.channel_id || "");
    }});

    wrap.querySelectorAll("button[data-remove-entry]").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        const removeKey = btn.getAttribute("data-remove-entry");
        const index = Number(btn.getAttribute("data-remove-index") || -1);
        if (!removeKey || !Number.isFinite(index) || index < 0) return;
        state[removeKey].splice(index, 1);
        renderEntries(removeKey);
      }});
    }});

    wrap.querySelectorAll("input[data-entry-url], textarea[data-entry-desc], input[data-entry-btn], select[data-entry-channel]").forEach((el) => {{
      el.addEventListener("input", () => syncRow(el));
      el.addEventListener("change", () => syncRow(el));
    }});
  }};

  keys.forEach((key) => renderEntries(key));

  form.querySelectorAll("button[data-add-entry]").forEach((btn) => {{
    btn.addEventListener("click", () => {{
      const key = btn.getAttribute("data-add-entry");
      if (!key || !state[key]) return;
      state[key].push({{
        source_url: "",
        description: "",
        button_text: "ดูรายละเอียด",
        channel_id: "",
      }});
      renderEntries(key);
    }});
  }});

  const toggleDetails = () => {{
    form.querySelectorAll("input[data-alert-toggle]").forEach((toggle) => {{
      const details = toggle.closest("details");
      if (!details) return;
      details.open = !!toggle.checked;
    }});
  }};

  form.querySelectorAll("input[data-alert-toggle]").forEach((toggle) => {{
    const holder = toggle.closest("label");
    if (holder) {{
      holder.addEventListener("click", (event) => event.stopPropagation());
      holder.addEventListener("mousedown", (event) => event.stopPropagation());
    }}
    toggle.addEventListener("click", (event) => event.stopPropagation());
    toggle.addEventListener("change", toggleDetails);
  }});

  form.addEventListener("submit", (event) => {{
    const enabled = form.querySelector('input[name="enabled"]')?.checked;
    const channel = (form.querySelector('select[name="notify_channel_id"]')?.value || "").trim();
    if (enabled && !channel) {{
      event.preventDefault();
      alert("โปรดเลือกช่องแจ้งเตือนหลักก่อนบันทึก");
      return;
    }}

    const cooldown = Number(form.querySelector('input[name="cooldown_seconds"]')?.value || 0);
    if (!Number.isFinite(cooldown) || cooldown < 10 || cooldown > 3600) {{
      event.preventDefault();
      alert("คูลดาวน์ต้องอยู่ระหว่าง 10 ถึง 3600 วินาที");
      return;
    }}

    const errors = [];
    for (const key of keys) {{
      const rows = state[key] || [];
      const cleaned = [];

      rows.forEach((row, idx) => {{
        const url = String(row.source_url || "").trim();
        const desc = String(row.description || "").trim();
        const btnText = String(row.button_text || "ดูรายละเอียด").trim();
        const room = String(row.channel_id || "").trim();

        if (!url && !desc && !room) return;
        if (!url) {{
          errors.push(`${{platformLabel[key] || key}} รายการ ${{idx + 1}}: กรุณากรอกลิงก์`);
          return;
        }}
        try {{
          const parsed = new URL(url);
          if (!/^https?:$/.test(parsed.protocol)) throw new Error("invalid");
        }} catch (_error) {{
          errors.push(`${{platformLabel[key] || key}} รายการ ${{idx + 1}}: ลิงก์ไม่ถูกต้อง`);
          return;
        }}
        if (btnText.length > 45) {{
          errors.push(`${{platformLabel[key] || key}} รายการ ${{idx + 1}}: ข้อความปุ่มเกิน 45 ตัวอักษร`);
          return;
        }}
        if (!room && !channel) {{
          errors.push(`${{platformLabel[key] || key}} รายการ ${{idx + 1}}: โปรดเลือกห้องแจ้งเตือน`);
          return;
        }}
        cleaned.push({{
          source_url: url.slice(0, 300),
          description: desc.slice(0, 400),
          button_text: (btnText || "ดูรายละเอียด").slice(0, 45),
          channel_id: room,
        }});
      }});

      state[key] = cleaned;
      const hidden = form.querySelector(`#entries_json_${{key}}`);
      if (hidden) hidden.value = JSON.stringify(cleaned);
    }}

    if (errors.length > 0) {{
      event.preventDefault();
      alert(errors.join("\\n"));
      return;
    }}
  }});

  toggleDetails();
}})();
