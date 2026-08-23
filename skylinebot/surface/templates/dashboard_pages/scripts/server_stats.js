const maxStatsChannels = {max_stats_channels};
        const toggle = document.getElementById('serverStatsToggle');
        const content = document.getElementById('serverStatsContent');
        const hiddenEnabled = document.getElementById('enabledHidden');
        const counterNode = document.getElementById('serverStatsEnabledCount');
        const statCheckboxes = Array.from(document.querySelectorAll('input[type="checkbox"][name^="stat_"][name$="_enabled"]'));
        const syncStatLimit = () => {{
            const checkedCount = statCheckboxes.filter((box) => box.checked).length;
            if (counterNode) counterNode.textContent = String(checkedCount);
            statCheckboxes.forEach((box) => {{
                if (box.checked) {{
                    box.disabled = false;
                    box.removeAttribute('title');
                    return;
                }}
                if (checkedCount >= maxStatsChannels) {{
                    box.disabled = true;
                    box.title = `แพ็กเกจนี้เปิดได้สูงสุด ${{maxStatsChannels}} ช่อง`;
                }} else {{
                    box.disabled = false;
                    box.removeAttribute('title');
                }}
            }});
        }};
        statCheckboxes.forEach((box) => box.addEventListener('change', syncStatLimit));
        toggle.addEventListener('change', function() {{
            content.style.display = this.checked ? 'block' : 'none';
            hiddenEnabled.value = this.checked ? 'on' : 'off';
        }});
        syncStatLimit();
