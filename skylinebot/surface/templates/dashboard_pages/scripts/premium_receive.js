(() => {{
  const copyButtons = Array.from(document.querySelectorAll(".premium-copy-btn[data-copy]"));
  const hint = document.getElementById("premiumReceiveCopyHint");
  if (!copyButtons.length) return;

  const setHint = (message, tone = "default") => {{
    if (!hint) return;
    hint.textContent = String(message || "");
    hint.classList.remove("hint-success", "hint-error");
    if (tone === "success") hint.classList.add("hint-success");
    if (tone === "error") hint.classList.add("hint-error");
  }};

  const fallbackCopy = (value) => {{
    const textArea = document.createElement("textarea");
    textArea.value = value;
    textArea.setAttribute("readonly", "readonly");
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    textArea.style.pointerEvents = "none";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    let copied = false;
    try {{
      copied = document.execCommand("copy");
    }} catch (_error) {{
      copied = false;
    }}
    document.body.removeChild(textArea);
    return copied;
  }};

  copyButtons.forEach((button) => {{
    const originalHtml = button.innerHTML;
    button.addEventListener("click", async () => {{
      const value = String(button.getAttribute("data-copy") || "").trim();
      if (!value) {{
        setHint("ไม่พบข้อมูลให้คัดลอก", "error");
        return;
      }}
      let copied = false;
      try {{
        if (navigator?.clipboard?.writeText) {{
          await navigator.clipboard.writeText(value);
          copied = true;
        }} else {{
          copied = fallbackCopy(value);
        }}
      }} catch (_error) {{
        copied = fallbackCopy(value);
      }}

      if (copied) {{
        button.innerHTML = '<i class="fa-solid fa-check" aria-hidden="true"></i>คัดลอกแล้ว';
        setHint(`คัดลอกข้อมูลแล้ว: ${{value}}`, "success");
      }} else {{
        button.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i>คัดลอกไม่สำเร็จ';
        setHint("คัดลอกไม่สำเร็จ ลองใหม่อีกครั้ง", "error");
      }}

      window.setTimeout(() => {{
        button.innerHTML = originalHtml;
      }}, 1200);
    }});
  }});
}})();
