const __BOOT = (() => {
  const node = document.getElementById("dashboard-bootstrap");
  if (!node) return {};
  const raw = String(node.textContent || "{}");
  const tryParse = (value) => {
    try {
      return JSON.parse(String(value || "{}"));
    } catch (_error) {
      return null;
    }
  };
  const parsed = tryParse(raw);
  if (parsed && typeof parsed === "object") {
    return parsed;
  }
  // Backward-compatible fallback for pages that still inject HTML-escaped JSON.
  const textarea = document.createElement("textarea");
  textarea.innerHTML = raw;
  const decoded = textarea.value;
  const parsedDecoded = tryParse(decoded);
  if (parsedDecoded && typeof parsedDecoded === "object") {
    return parsedDecoded;
  }
  try {
    return JSON.parse(raw);
  } catch (_error) {
    return {};
  }
})();

(() => {
      const body = document.body;
      const topbar = document.querySelector(".topbar");
      const themeToggleButtons = Array.from(document.querySelectorAll('[data-dashboard-action="toggle-theme"]'));
      const langToggleButtons = Array.from(document.querySelectorAll('[data-dashboard-action="toggle-lang"]'));
      const safeStorageGet = (key) => {
        try {
          return localStorage.getItem(key);
        } catch (_error) {
          return null;
        }
      };
      const safeStorageSet = (key, value) => {
        try {
          localStorage.setItem(key, value);
        } catch (_error) {
        }
      };
      const normalizeLangCode = (value) => {
        const normalized = String(value || "").trim().toLowerCase();
        return normalized === "en" ? "en" : normalized === "th" ? "th" : "";
      };
      const readLanguageCookie = () => {
        try {
          const parts = String(document.cookie || "").split(";");
          for (const rawPart of parts) {
            const part = String(rawPart || "").trim();
            if (!part) continue;
            if (!part.toLowerCase().startsWith("skyline_lang=")) continue;
            return normalizeLangCode(part.slice("skyline_lang=".length));
          }
        } catch (_error) {
        }
        return "";
      };
      const setLanguageCookie = (lang) => {
        const resolved = String(lang || "").trim().toLowerCase() === "en" ? "en" : "th";
        try {
          document.cookie = `skyline_lang=${resolved}; path=/; max-age=31536000; SameSite=Lax`;
        } catch (_error) {
        }
      };
      const decorateLanguageToggleButton = (button) => {
        if (!(button instanceof HTMLElement)) {
          return null;
        }
        button.classList.add("lang-toggle-btn");
        button.setAttribute("type", "button");
        const currentRawText = String(button.textContent || "").trim().toUpperCase();
        const initialLabel = currentRawText === "TH" ? "TH" : "EN";
        button.textContent = "";

        const icon = document.createElement("i");
        icon.className = "bi bi-translate lang-toggle-icon";
        icon.setAttribute("aria-hidden", "true");

        const label = document.createElement("span");
        label.className = "lang-toggle-label";
        label.textContent = initialLabel;

        button.append(icon, label);
        return label;
      };
      const ensureFloatingLanguageToggleButton = () => {
        if (langToggleButtons.length || !(body instanceof HTMLElement)) {
          return;
        }
        const button = document.createElement("button");
        button.className = "ux-btn lang-toggle-btn floating-lang-toggle";
        button.setAttribute("data-dashboard-action", "toggle-lang");
        button.setAttribute("data-no-auto-i18n", "1");
        button.setAttribute("aria-label", "Switch language");
        button.setAttribute("title", "Switch language");
        decorateLanguageToggleButton(button);
        body.appendChild(button);
        langToggleButtons.push(button);
      };
      const lazyScriptCache = new Map();
      const ensureLazyScript = (url, readyCheck) => {
        const src = String(url || "").trim();
        if (!src) {
          return Promise.reject(new Error("missing-script-url"));
        }
        if (typeof readyCheck === "function") {
          try {
            if (readyCheck()) {
              return Promise.resolve();
            }
          } catch (_error) {}
        }
        const cached = lazyScriptCache.get(src);
        if (cached) {
          return cached;
        }
        const promise = new Promise((resolve, reject) => {
          const existing = document.querySelector(`script[src="${src.replace(/"/g, '\\"')}"]`);
          const script = existing instanceof HTMLScriptElement ? existing : document.createElement("script");
          script.src = src;
          script.defer = true;
          script.onload = () => resolve();
          script.onerror = () => reject(new Error(`load-failed:${src}`));
          if (!existing) {
            document.head.appendChild(script);
          }
        });
        lazyScriptCache.set(src, promise);
        return promise;
      };
      const stripKnownStrayLayoutText = () => {
        const knownTexts = new Set(["dashboard-content flex-1 min-h-0 p-0"]);
        const scanRoots = [document.body, document.querySelector(".dashboard-main"), document.querySelector(".dashboard-content")];
        scanRoots.forEach((root) => {
          if (!(root instanceof HTMLElement)) return;
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
          const toRemove = [];
          while (walker.nextNode()) {
            const node = walker.currentNode;
            if (!(node instanceof Text)) continue;
            const normalized = String(node.textContent || "").replace(/\s+/g, " ").trim();
            if (!knownTexts.has(normalized)) continue;
            toRemove.push(node);
          }
          toRemove.forEach((node) => node.remove());
        });
      };
      const storedTheme = safeStorageGet("skyline_theme") || "dark";
      const rawDefaultLang = String(__BOOT.defaultServerLang || "th").toLowerCase();
      const defaultLang = rawDefaultLang === "en" ? "en" : "th";
      const storedLang = normalizeLangCode(safeStorageGet("skyline_lang")) || "";
      const cookieLang = readLanguageCookie();
      const documentLang = normalizeLangCode(document.documentElement.lang);
      const initialLang = documentLang || cookieLang || storedLang || defaultLang;
      let currentLanguage = initialLang;
      const accentThemeClasses = ["accent-cyan", "accent-emerald", "accent-rose", "accent-amber"];
      const i18nRegistry = (window.SKYLINE_DASHBOARD_I18N && typeof window.SKYLINE_DASHBOARD_I18N === "object")
        ? window.SKYLINE_DASHBOARD_I18N
        : {};
      const i18n = {
        th: (i18nRegistry.th && typeof i18nRegistry.th === "object") ? i18nRegistry.th : {},
        en: (i18nRegistry.en && typeof i18nRegistry.en === "object") ? i18nRegistry.en : {},
      };
      const resolveI18nVersionQuery = () => {
        try {
          const scripts = Array.from(document.querySelectorAll('script[src*="/dashboard/static/dashboard/i18n/"]'));
          for (const node of scripts) {
            if (!(node instanceof HTMLScriptElement)) continue;
            const src = String(node.getAttribute("src") || node.src || "").trim();
            if (!src) continue;
            const queryIndex = src.indexOf("?");
            if (queryIndex < 0) continue;
            const query = src.slice(queryIndex + 1).trim();
            if (!query) continue;
            return `?${query}`;
          }
        } catch (_error) {
        }
        return "";
      };
      const resolveI18nScriptUrl = (lang) => {
        const resolvedLang = String(lang || "").trim().toLowerCase() === "en" ? "en" : "th";
        const versionQuery = resolveI18nVersionQuery();
        return `/dashboard/static/dashboard/i18n/${resolvedLang}.js${versionQuery}`;
      };
      const hasI18nDictionary = (lang) => {
        const resolvedLang = String(lang || "").trim().toLowerCase() === "en" ? "en" : "th";
        const dict = i18n[resolvedLang];
        return !!(dict && typeof dict === "object" && Object.keys(dict).length);
      };
      const ensureI18nDictionary = (lang) => {
        const resolvedLang = String(lang || "").trim().toLowerCase() === "en" ? "en" : "th";
        if (hasI18nDictionary(resolvedLang)) {
          return Promise.resolve();
        }
        return ensureLazyScript(
          resolveI18nScriptUrl(resolvedLang),
          () => hasI18nDictionary(resolvedLang)
        ).then(() => {
          const loaded = i18nRegistry[resolvedLang];
          if (loaded && typeof loaded === "object") {
            i18n[resolvedLang] = loaded;
          }
        });
      };
      const stripLangPrefixFromPath = (path) =>
        String(path || "/").replace(/^\/(?:th|en)(?=\/|$)/i, "") || "/";
      const syncLanguageUrlPrefix = (lang) => {
        const resolvedLang = String(lang || "").trim().toLowerCase() === "en" ? "en" : "th";
        try {
          const currentPath = window.location && window.location.pathname ? window.location.pathname : "/";
          const suffixPath = stripLangPrefixFromPath(currentPath);
          const normalizedSuffix = suffixPath.startsWith("/") ? suffixPath : `/${suffixPath}`;
          const targetPath = `/${resolvedLang}${normalizedSuffix}`;
          const search = window.location && window.location.search ? window.location.search : "";
          const hash = window.location && window.location.hash ? window.location.hash : "";
          const currentFull = `${currentPath}${search}${hash}`;
          const targetFull = `${targetPath}${search}${hash}`;
          if (currentFull !== targetFull && window.history && typeof window.history.replaceState === "function") {
            window.history.replaceState(window.history.state || null, "", targetFull);
          }
        } catch (_error) {
        }
      };
      const hasMarkup = (value) => /<\/?[a-z][^>]*>/i.test(String(value || ""));
      const stripMarkup = (value) =>
        String(value || "")
          .replace(/<[^>]*>/g, " ")
          .replace(/\s+/g, " ")
          .trim();
      const applyTranslatedText = (node, translated) => {
        if (!(node instanceof HTMLElement)) return;
        const rawText = String(translated || "");
        if (!rawText) return;

        const containsMarkup = hasMarkup(rawText);
        if (!node.children.length) {
          if (containsMarkup) {
            node.innerHTML = rawText;
          } else {
            node.textContent = rawText;
          }
          return;
        }

        const normalizedText = containsMarkup ? stripMarkup(rawText) : rawText;
        if (!normalizedText) return;

        const textNodes = Array.from(node.childNodes).filter(
          (child) => child && child.nodeType === Node.TEXT_NODE
        );
        let applied = false;
        textNodes.forEach((textNode) => {
          const current = String(textNode.textContent || "");
          if (!applied && current.trim()) {
            const leading = (current.match(/^\s*/) || [""])[0];
            const trailing = (current.match(/\s*$/) || [""])[0];
            textNode.textContent = `${leading}${normalizedText}${trailing}`;
            applied = true;
            return;
          }
          textNode.textContent = "";
        });

        if (!applied) {
          node.appendChild(document.createTextNode(` ${normalizedText}`));
        }
      };
      const escapeRegExp = (value) => String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const decodeHtml = (value) => {
        const textarea = document.createElement("textarea");
        textarea.innerHTML = String(value || "");
        return String(textarea.value || "");
      };
      const stripMarkupToText = (value) =>
        decodeHtml(String(value || "").replace(/<[^>]*>/g, " ")).replace(/\s+/g, " ").trim();
      const strictWordMap = Object.freeze({
        th: Object.freeze({
          "dashboard": "แดชบอร์ด",
          "overview": "ภาพรวม",
          "commands": "คำสั่ง",
          "docs": "เอกสาร",
          "leaderboard": "อันดับ",
          "donate": "โดเนท",
          "terms": "ข้อกำหนด",
          "privacy policy": "นโยบายความเป็นส่วนตัว",
          "contact": "ติดต่อ",
          "bot status": "สถานะบอท",
          "uptime status": "สถานะอัปไทม์",
          "redeem": "แลกโค้ด",
          "premium": "พรีเมียม",
          "free": "ฟรี",
          "save settings": "บันทึกการตั้งค่า",
          "save changes": "บันทึกการเปลี่ยนแปลง",
          "save": "บันทึก",
          "reset": "รีเซ็ต",
          "open page": "เปิดหน้า",
          "open chat": "เปิดแชท",
          "open": "เปิด",
          "close": "ปิด",
          "next": "ถัดไป",
          "previous": "ก่อนหน้า",
          "back": "กลับ",
          "add": "เพิ่ม",
          "remove": "ลบ",
          "delete all": "ลบทั้งหมด",
          "delete": "ลบ",
          "clear all": "ล้างทั้งหมด",
          "clear": "ล้าง",
          "filter": "ตัวกรอง",
          "all": "ทั้งหมด",
          "new": "ใหม่",
          "run": "เรียกใช้",
          "create": "สร้าง",
          "cancel": "ยกเลิก",
          "confirm": "ยืนยัน",
          "copy": "คัดลอก",
          "logout": "ออกจากระบบ",
          "login with discord": "เข้าสู่ระบบด้วย Discord",
          "join discord": "เข้าร่วมดิสคอร์ด",
          "contact team": "ติดต่อทีม",
          "report issue": "รายงานปัญหา",
          "invite bot": "เชิญบอท",
          "verify": "ยืนยันตัวตน",
          "web verify": "ยืนยันผ่านเว็บ",
          "history": "ประวัติ",
          "topup history": "ประวัติการเติมเงิน",
          "premium history": "ประวัติพรีเมียม",
          "apply": "นำไปใช้",
          "upgrade plan": "อัปเกรดแพ็กเกจ",
          "status": "สถานะ",
          "mode": "โหมด",
          "theme": "ธีม",
          "server": "เซิร์ฟเวอร์",
          "guild": "กิลด์",
          "channel": "ช่อง",
          "channels": "ช่อง",
          "role": "บทบาท",
          "roles": "บทบาท",
          "support": "ซัพพอร์ต",
          "verification": "ยืนยันตัวตน",
          "single role": "บทบาทเดียว",
          "multiple roles": "หลายบทบาท",
          "ticket support": "ซัพพอร์ตทิกเก็ต",
          "tickets support": "ซัพพอร์ตทิกเก็ต",
          "image ocr verification": "ตรวจสอบ OCR จากภาพ",
          "choose skylinebot plan": "เลือก Plan SkylineBOT",
          "choose the best package for your server with full feature and donation privilege comparisons.": "เลือกแพ็กเกจให้เหมาะกับเซิร์ฟเวอร์ของคุณ พร้อมตารางเทียบฟีเจอร์และสิทธิ์โดเนตแบบครบถ้วน",
          "feature comparison table": "ตารางเทียบฟีเจอร์",
          "command access by package": "ตารางคำสั่งตามแพ็กเกจ",
          "donation support system": "ระบบโดเนตสนับสนุน",
          "how to subscribe and upgrade": "วิธีสมัครและอัปเกรด",
          "choose the package that fits your server size.": "เลือกแพ็กเกจที่เหมาะกับขนาดเซิร์ฟเวอร์ของคุณ",
          "open the subscribe plan page, choose a guild, then subscribe to the package you want instantly.": "เปิดหน้า Subscribe Plan แล้วเลือกกิลด์ จากนั้นกดสมัครแพ็กเกจที่ต้องการได้ทันที",
          "after confirmation, premium features will be enabled immediately in that server's dashboard.": "หลังยืนยันสิทธิ์ ฟีเจอร์ Premium จะเปิดใน Dashboard ของเซิร์ฟเวอร์นั้นทันที",
          "back to dashboard": "กลับหน้าแดชบอร์ด",
          "view website info": "ดูข้อมูลเว็บไซต์",
          "subscribe package": "สมัครแพ็กเกจ",
          "please log in first to subscribe a server package.": "กรุณาเข้าสู่ระบบก่อนเพื่อสมัครแพ็กเกจเซิร์ฟเวอร์",
          "login": "เข้าสู่ระบบ",
          "subscribe per guild": "สมัครแพ็กเกจรายกิลด์",
          "select your target guild first, then subscribe to the package you want.": "เลือกกิลด์เป้าหมายก่อน จากนั้นกดสมัครแพ็กเกจที่ต้องการได้ทันที",
          "target guild": "กิลด์เป้าหมาย",
          "current package:": "แพ็กเกจปัจจุบัน:",
          "next package queue:": "คิวแพ็กเกจถัดไป:",
          "expires:": "หมดอายุ:",
          "auto renew:": "ต่ออายุอัตโนมัติ:",
          "cancel renewal for selected guild": "ยกเลิกการต่ออายุกิลด์ที่เลือก",
          "no manageable guild found for your account": "ยังไม่พบกิลด์ที่คุณมีสิทธิ์จัดการ",
          "current plan": "แผนปัจจุบัน",
          "not enabled": "ยังไม่เปิดใช้งาน",
          "active": "เปิดใช้งาน",
          "pending activation": "รอเปิดใช้งาน",
          "separate package for users (not guild package), price": "แพ็กเกจแยกสำหรับผู้ใช้ (ไม่ใช่แพ็กเกจกิลด์) ราคา",
          "subscribe app user plan": "สมัคร App User Plan",
          "cancel app user plan renewal": "ยกเลิกการต่ออายุ App User Plan",
          "on": "เปิด",
          "off": "ปิด",
          "off (permanent)": "ปิด (ถาวร)",
          "no renewal needed": "ไม่ต้องต่ออายุ",
          "play music from links": "เล่นเพลงผ่านลิงก์",
          "default volume adjustment": "ปรับระดับเสียงเริ่มต้น",
          "custom role limit": "จำนวนบทบาทที่กำหนดเอง",
          "auto responder limit": "จำนวน Auto Responder",
          "welcome autorole limit": "จำนวนบทบาทต้อนรับอัตโนมัติ",
          "server stats channel limit": "จำนวนห้องสถิติ (Server Stats)",
          "advanced anti-nuke mode (custom)": "โหมด Anti-Nuke ขั้นสูง (Custom)",
          "maximum anti-nuke punishment": "บทลงโทษ Anti-Nuke สูงสุด",
          "advanced automod mode (custom)": "โหมด AutoMod ขั้นสูง (Custom)",
          "maximum automod punishment": "บทลงโทษ AutoMod สูงสุด",
          "level system": "ระบบเลเวล",
          "voice xp levels": "เลเวลจากเสียง",
          "reaction xp levels": "เลเวลจากรีแอคชัน",
          "maximum level rewards": "จำนวนรางวัลเลเวลสูงสุด",
          "support level": "ระดับการซัพพอร์ต",
          "standard": "มาตรฐาน",
          "fast": "รวดเร็ว",
          "highest priority": "เร่งด่วนสูงสุด",
          "search + links": "ค้นหา+ลิงก์",
          "search only (no links)": "ค้นหาได้ (ลิงก์ไม่ได้)",
          "editable": "แก้ไขได้",
          "view only": "ดูได้อย่างเดียว",
          "granted package": "แพ็กเกจที่ได้รับ",
          "support price": "ราคาสนับสนุน",
          "maximum shop products": "จำนวนสินค้า Shop สูงสุด",
          "pay with truemoney gift": "ชำระด้วย TrueMoney Gift",
          "pay with shipok / slipok": "ชำระด้วย SHIPOK / SlipOK",
          "automatic slip verification": "ตรวจสลิปอัตโนมัติ",
          "automatic delivery (auto delivery)": "ส่งของอัตโนมัติ (Auto Delivery)",
          "deliver product via dm/text": "ส่งสินค้าแบบ DM/Text",
          "deliver product via role": "ส่งสินค้าแบบ Role",
          "auto-open ticket when delivery fails": "เปิด Ticket อัตโนมัติเมื่อส่งไม่สำเร็จ",
          "custom roles limit": "ขีดจำกัด Custom Roles",
          "auto responder limit cap": "ขีดจำกัด Auto Responder",
          "unlock core premium features for growing servers.": "ปลดล็อกฟีเจอร์พรีเมียมหลักสำหรับเซิร์ฟเวอร์ที่เริ่มเติบโต",
          "increase usage limits for high-activity communities.": "เพิ่มขีดจำกัดการใช้งานสำหรับชุมชนที่ใช้งานหนาแน่น",
          "unlock maximum limits and full system privileges.": "ปลดล็อกสิทธิ์และขีดจำกัดสูงสุดของระบบ",
          "pay once for permanent access on the selected guild.": "ชำระครั้งเดียว ใช้งานสิทธิ์ถาวรสำหรับกิลด์ที่เลือก",
          "best for communities that are just getting started.": "เหมาะสำหรับชุมชนที่เพิ่งเริ่ม",
          "unlock core systems and raise key limits.": "ปลดล็อกระบบสำคัญและเพิ่มขีดจำกัดหลัก",
          "great for busy, serious servers.": "เหมาะกับเซิร์ฟเวอร์ที่ใช้งานหนักและจริงจัง",
          "maximum limits and full access across all systems.": "ขีดจำกัดสูงสุดและสิทธิ์ครบทุกระบบ",
          "full access across all systems, including future premium features.": "สิทธิ์ครบทุกระบบ รวมฟีเจอร์พรีเมียมใหม่ในอนาคต",
          "subscribe silver package": "สมัครแพ็กเกจ Silver",
          "subscribe gole package": "สมัครแพ็กเกจ Gole",
          "subscribe diamond package": "สมัครแพ็กเกจ Diamond",
          "subscribe permanent package": "สมัครแพ็กเกจ Permanent",
          "thb": "บาท",
          "month": "เดือน",
          "days": "วัน",
          "lifetime": "ตลอดชีพ",
          "permanent": "ถาวร",
        }),
        en: Object.freeze({
          "แดชบอร์ด": "Dashboard",
          "ภาพรวม": "Overview",
          "คำสั่ง": "Commands",
          "เอกสาร": "Docs",
          "อันดับ": "Leaderboard",
          "โดเนท": "Donate",
          "ข้อกำหนด": "Terms",
          "นโยบายความเป็นส่วนตัว": "Privacy Policy",
          "ติดต่อ": "Contact",
          "สถานะบอท": "Bot Status",
          "สถานะอัปไทม์": "Uptime Status",
          "แลกโค้ด": "Redeem",
          "พรีเมียม": "Premium",
          "ฟรี": "Free",
          "บันทึกการตั้งค่า": "Save settings",
          "บันทึกการเปลี่ยนแปลง": "Save changes",
          "บันทึก": "Save",
          "รีเซ็ต": "Reset",
          "เปิดหน้า": "Open page",
          "เปิดแชท": "Open chat",
          "เปิด": "Open",
          "ปิด": "Close",
          "ถัดไป": "Next",
          "ก่อนหน้า": "Previous",
          "กลับ": "Back",
          "เพิ่ม": "Add",
          "ลบทั้งหมด": "Delete all",
          "ลบ": "Delete",
          "ล้างทั้งหมด": "Clear all",
          "ล้าง": "Clear",
          "ตัวกรอง": "Filter",
          "ทั้งหมด": "All",
          "ใหม่": "New",
          "เรียกใช้": "Run",
          "สร้าง": "Create",
          "ยกเลิก": "Cancel",
          "ยืนยัน": "Confirm",
          "คัดลอก": "Copy",
          "ออกจากระบบ": "Logout",
          "เข้าสู่ระบบด้วย Discord": "Login with Discord",
          "เข้าร่วมดิสคอร์ด": "Join Discord",
          "ติดต่อทีม": "Contact Team",
          "รายงานปัญหา": "Report Issue",
          "เชิญบอท": "Invite Bot",
          "ยืนยันผ่านเว็บ": "Web Verify",
          "ประวัติ": "History",
          "ประวัติการเติมเงิน": "Topup History",
          "ประวัติพรีเมียม": "Premium History",
          "นำไปใช้": "Apply",
          "อัปเกรดแพ็กเกจ": "Upgrade Plan",
          "สถานะ": "Status",
          "โหมด": "Mode",
          "ธีม": "Theme",
          "เซิร์ฟเวอร์": "Server",
          "กิลด์": "Guild",
          "ช่อง": "Channel",
          "บทบาท": "Role",
          "ซัพพอร์ต": "Support",
          "ยืนยันตัวตน": "Verification",
          "บทบาทเดียว": "Single role",
          "หลายบทบาท": "Multiple roles",
          "ซัพพอร์ตทิกเก็ต": "Ticket Support",
          "ตรวจสอบ OCR จากภาพ": "Image OCR Verification",
          "เลือก Plan SkylineBOT": "Choose SkylineBOT Plan",
          "เลือกแพ็กเกจให้เหมาะกับเซิร์ฟเวอร์ของคุณ พร้อมตารางเทียบฟีเจอร์และสิทธิ์โดเนตแบบครบถ้วน": "Choose the best package for your server with full feature and donation privilege comparisons.",
          "ตารางเทียบฟีเจอร์": "Feature Comparison Table",
          "ตารางคำสั่งตามแพ็กเกจ": "Command Access by Package",
          "ระบบโดเนตสนับสนุน": "Donation Support System",
          "วิธีสมัครและอัปเกรด": "How to Subscribe and Upgrade",
          "เลือกแพ็กเกจที่เหมาะกับขนาดเซิร์ฟเวอร์ของคุณ": "Choose the package that fits your server size.",
          "เปิดหน้า Subscribe Plan แล้วเลือกกิลด์ จากนั้นกดสมัครแพ็กเกจที่ต้องการได้ทันที": "Open the Subscribe Plan page, choose a guild, then subscribe to the package you want instantly.",
          "หลังยืนยันสิทธิ์ ฟีเจอร์ Premium จะเปิดใน Dashboard ของเซิร์ฟเวอร์นั้นทันที": "After confirmation, Premium features will be enabled immediately in that server's dashboard.",
          "กลับหน้าแดชบอร์ด": "Back to dashboard",
          "ดูข้อมูลเว็บไซต์": "View website info",
          "สมัครแพ็กเกจ": "Subscribe package",
          "กรุณาเข้าสู่ระบบก่อนเพื่อสมัครแพ็กเกจเซิร์ฟเวอร์": "Please log in first to subscribe a server package.",
          "เข้าสู่ระบบ": "Login",
          "สมัครแพ็กเกจรายกิลด์": "Subscribe per guild",
          "เลือกกิลด์เป้าหมายก่อน จากนั้นกดสมัครแพ็กเกจที่ต้องการได้ทันที": "Select your target guild first, then subscribe to the package you want.",
          "กิลด์เป้าหมาย": "Target guild",
          "แพ็กเกจปัจจุบัน:": "Current package:",
          "คิวแพ็กเกจถัดไป:": "Next package queue:",
          "หมดอายุ:": "Expires:",
          "ต่ออายุอัตโนมัติ:": "Auto renew:",
          "ยกเลิกการต่ออายุกิลด์ที่เลือก": "Cancel renewal for selected guild",
          "ยังไม่พบกิลด์ที่คุณมีสิทธิ์จัดการ": "No manageable guild found for your account",
          "แผนปัจจุบัน": "Current plan",
          "ยังไม่เปิดใช้งาน": "Not enabled",
          "เปิดใช้งาน": "Active",
          "รอเปิดใช้งาน": "Pending activation",
          "แพ็กเกจแยกสำหรับผู้ใช้ (ไม่ใช่แพ็กเกจกิลด์) ราคา": "Separate package for users (not guild package), price",
          "สมัคร App User Plan": "Subscribe App User Plan",
          "ยกเลิกการต่ออายุ App User Plan": "Cancel App User Plan renewal",
          "เปิด": "On",
          "ปิด": "Off",
          "ปิด (ถาวร)": "Off (Permanent)",
          "ไม่ต้องต่ออายุ": "No renewal needed",
          "เล่นเพลงผ่านลิงก์": "Play music from links",
          "ปรับระดับเสียงเริ่มต้น": "Default volume adjustment",
          "จำนวนบทบาทที่กำหนดเอง": "Custom role limit",
          "จำนวน Auto Responder": "Auto responder limit",
          "จำนวนบทบาทต้อนรับอัตโนมัติ": "Welcome autorole limit",
          "จำนวนห้องสถิติ (Server Stats)": "Server stats channel limit",
          "โหมด Anti-Nuke ขั้นสูง (Custom)": "Advanced Anti-Nuke mode (Custom)",
          "บทลงโทษ Anti-Nuke สูงสุด": "Maximum Anti-Nuke punishment",
          "โหมด AutoMod ขั้นสูง (Custom)": "Advanced AutoMod mode (Custom)",
          "บทลงโทษ AutoMod สูงสุด": "Maximum AutoMod punishment",
          "ระบบเลเวล": "Level system",
          "เลเวลจากเสียง": "Voice XP levels",
          "เลเวลจากรีแอคชัน": "Reaction XP levels",
          "จำนวนรางวัลเลเวลสูงสุด": "Maximum level rewards",
          "ระดับการซัพพอร์ต": "Support level",
          "มาตรฐาน": "Standard",
          "รวดเร็ว": "Fast",
          "เร่งด่วนสูงสุด": "Highest priority",
          "ค้นหา+ลิงก์": "Search + links",
          "ค้นหาได้ (ลิงก์ไม่ได้)": "Search only (no links)",
          "แก้ไขได้": "Editable",
          "ดูได้อย่างเดียว": "View only",
          "แพ็กเกจที่ได้รับ": "Granted package",
          "ราคาสนับสนุน": "Support price",
          "จำนวนสินค้า Shop สูงสุด": "Maximum shop products",
          "ชำระด้วย TrueMoney Gift": "Pay with TrueMoney Gift",
          "ชำระด้วย SHIPOK / SlipOK": "Pay with SHIPOK / SlipOK",
          "ตรวจสลิปอัตโนมัติ": "Automatic slip verification",
          "ส่งของอัตโนมัติ (Auto Delivery)": "Automatic delivery (Auto Delivery)",
          "ส่งสินค้าแบบ DM/Text": "Deliver product via DM/Text",
          "ส่งสินค้าแบบ Role": "Deliver product via Role",
          "เปิด Ticket อัตโนมัติเมื่อส่งไม่สำเร็จ": "Auto-open ticket when delivery fails",
          "ขีดจำกัด Custom Roles": "Custom Roles limit",
          "ขีดจำกัด Auto Responder": "Auto Responder limit cap",
          "ปลดล็อกฟีเจอร์พรีเมียมหลักสำหรับเซิร์ฟเวอร์ที่เริ่มเติบโต": "Unlock core premium features for growing servers.",
          "เพิ่มขีดจำกัดการใช้งานสำหรับชุมชนที่ใช้งานหนาแน่น": "Increase usage limits for high-activity communities.",
          "ปลดล็อกสิทธิ์และขีดจำกัดสูงสุดของระบบ": "Unlock maximum limits and full system privileges.",
          "ชำระครั้งเดียว ใช้งานสิทธิ์ถาวรสำหรับกิลด์ที่เลือก": "Pay once for permanent access on the selected guild.",
          "เหมาะสำหรับชุมชนที่เพิ่งเริ่ม": "Best for communities that are just getting started.",
          "ปลดล็อกระบบสำคัญและเพิ่มขีดจำกัดหลัก": "Unlock core systems and raise key limits.",
          "เหมาะกับเซิร์ฟเวอร์ที่ใช้งานหนักและจริงจัง": "Great for busy, serious servers.",
          "ขีดจำกัดสูงสุดและสิทธิ์ครบทุกระบบ": "Maximum limits and full access across all systems.",
          "สิทธิ์ครบทุกระบบ รวมฟีเจอร์พรีเมียมใหม่ในอนาคต": "Full access across all systems, including future premium features.",
          "สมัครแพ็กเกจ Silver": "Subscribe Silver package",
          "สมัครแพ็กเกจ Gole": "Subscribe Gole package",
          "สมัครแพ็กเกจ Diamond": "Subscribe Diamond package",
          "สมัครแพ็กเกจ Permanent": "Subscribe Permanent package",
          "บาท": "THB",
          "เดือน": "month",
          "วัน": "days",
          "ตลอดชีพ": "Lifetime",
          "ถาวร": "Permanent",
        }),
      });
      let strictPhrasePairsCache = null;
      const strictPhrasePairs = () => {
        if (Array.isArray(strictPhrasePairsCache)) {
          return strictPhrasePairsCache;
        }
        const pairs = [];
        const seen = new Set();
        const thDict = i18n.th || {};
        const enDict = i18n.en || {};
        Object.keys(thDict).forEach((key) => {
          const thText = stripMarkupToText(thDict[key]);
          const enText = stripMarkupToText(enDict[key]);
          if (!thText || !enText || thText === enText) return;
          const pairKey = `${thText}\u0000${enText}`;
          if (seen.has(pairKey)) return;
          seen.add(pairKey);
          pairs.push({ th: thText, en: enText });
        });
        strictPhrasePairsCache = pairs.sort(
          (left, right) => Math.max(right.th.length, right.en.length) - Math.max(left.th.length, left.en.length)
        );
        return strictPhrasePairsCache;
      };
      const containsThai = (value) => /[\u0E00-\u0E7F]/.test(String(value || ""));
      const containsEnglish = (value) => /[A-Za-z]/.test(String(value || ""));
      const normalizeMixedPairSide = (value) =>
        String(value || "")
          .replace(/\s+/g, " ")
          .replace(/^[\s\-–—|/,:]+|[\s\-–—|/,:]+$/g, "")
          .trim();
      const normalizeMixedLanguageLoose = (value, lang) => {
        let next = String(value || "");
        if (!next) return next;
        const pickLangText = (thaiText, englishText) =>
          lang === "th"
            ? normalizeMixedPairSide(thaiText)
            : normalizeMixedPairSide(englishText);

        // Thai (English) / English (Thai)
        next = next.replace(
          /([ก-๙][^()\n]{0,180}?)\s*\(\s*([A-Za-z][^()\n]{0,180}?)\s*\)/g,
          (_all, thaiText, englishText) => pickLangText(thaiText, englishText)
        );
        next = next.replace(
          /([A-Za-z][^()\n]{0,180}?)\s*\(\s*([ก-๙][^()\n]{0,180}?)\s*\)/g,
          (_all, englishText, thaiText) => pickLangText(thaiText, englishText)
        );

        // Thai / English and English / Thai.
        next = next.replace(
          /([ก-๙][^/\|\n]{0,180}?)\s*(?:\/|\||-|–|:)\s*([A-Za-z][^/\|\n]{0,180}?)(?=$|[,.!?;)\]])/g,
          (_all, thaiText, englishText) => pickLangText(thaiText, englishText)
        );
        next = next.replace(
          /([A-Za-z][^/\|\n]{0,180}?)\s*(?:\/|\||-|–|:)\s*([ก-๙][^/\|\n]{0,180}?)(?=$|[,.!?;)\]])/g,
          (_all, englishText, thaiText) => pickLangText(thaiText, englishText)
        );

        return next;
      };
      const replaceLoosePhrase = (payload, source, target) => {
        const from = String(source || "").trim();
        const to = String(target || "").trim();
        if (!from || !to) return payload;
        const looksAscii = /^[A-Za-z0-9 ]+$/.test(from);
        const looksThai = /[\u0E00-\u0E7F]/.test(from);
        let pattern;
        if (looksAscii) {
          pattern = new RegExp(`\\b${escapeRegExp(from)}\\b`, "gi");
        } else if (looksThai) {
          // Avoid partial replacement inside Thai words, e.g. replacing "ปิด" in "เปิด".
          try {
            pattern = new RegExp(`(?<![\\u0E00-\\u0E7F])${escapeRegExp(from)}(?![\\u0E00-\\u0E7F])`, "g");
          } catch (_error) {
            pattern = new RegExp(escapeRegExp(from), "g");
          }
        } else {
          pattern = new RegExp(escapeRegExp(from), "g");
        }
        return String(payload || "").replace(pattern, to);
      };
      const replaceLooseWords = (payload, lang) => {
        let next = String(payload || "");
        const sourceMap = strictWordMap[lang] || {};
        Object.keys(sourceMap)
          .sort((a, b) => b.length - a.length)
          .forEach((source) => {
            next = replaceLoosePhrase(next, source, sourceMap[source]);
          });
        return next;
      };
      const translateLooseText = (value, lang) => {
        const raw = String(value || "");
        if (!raw.trim()) return raw;

        const leading = (raw.match(/^\s*/) || [""])[0];
        const trailing = (raw.match(/\s*$/) || [""])[0];
        const core = raw.slice(leading.length, raw.length - trailing.length);
        if (!core) return raw;

        let translated = normalizeMixedLanguageLoose(core, lang);
        strictPhrasePairs().forEach((pair) => {
          const source = lang === "th" ? pair.en : pair.th;
          const target = lang === "th" ? pair.th : pair.en;
          translated = replaceLoosePhrase(translated, source, target);
        });
        translated = replaceLooseWords(translated, lang);
        translated = normalizeMixedLanguageLoose(translated, lang);

        if (lang === "th" && containsEnglish(translated)) {
          translated = replaceLooseWords(translated, "th");
        } else if (lang === "en" && containsThai(translated)) {
          translated = replaceLooseWords(translated, "en");
        }
        translated = normalizeMixedLanguageLoose(translated, lang);

        return `${leading}${translated}${trailing}`;
      };
      const translateLooseMarkup = (value, lang) => {
        const raw = String(value || "");
        if (!raw.trim()) return raw;
        if (!hasMarkup(raw)) {
          return translateLooseText(raw, lang);
        }
        const template = document.createElement("template");
        template.innerHTML = raw;
        const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) {
          const current = walker.currentNode;
          if (current instanceof Text) {
            nodes.push(current);
          }
        }
        nodes.forEach((node) => {
          const currentText = String(node.textContent || "");
          if (!currentText.trim()) return;
          node.textContent = translateLooseText(currentText, lang);
        });
        return template.innerHTML;
      };
      const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
      const resolveI18nValue = (dict, fallback, key, lang) => {
        const hasPrimary = hasOwn(dict, key) && typeof dict[key] === "string";
        if (hasPrimary) {
          return String(dict[key]);
        }
        const hasFallback = hasOwn(fallback, key) && typeof fallback[key] === "string";
        if (!hasFallback) {
          return "";
        }
        const fallbackValue = String(fallback[key]);
        if (lang !== "en") {
          return fallbackValue;
        }
        return translateLooseMarkup(fallbackValue, "en");
      };
      const resolveLooseLang = (lang) => {
        const normalized = String(lang || "").trim().toLowerCase();
        return normalized === "en" ? "en" : "th";
      };
      const translateLooseValue = (value, lang) => {
        const targetLang = resolveLooseLang(lang || currentLanguage);
        return translateLooseText(String(value ?? ""), targetLang);
      };
      const isLooseProtectedElement = (element) => {
        if (!(element instanceof HTMLElement)) return true;
        if (element.closest("[data-no-auto-i18n='1']")) return true;
        if (
          element.closest(
            ".guild-card-copy h3, .guild-card-copy [data-guild-name], .topbar-account-trigger-name, .profile-account-trigger-name, .dash-tag, .sidebar-server p, .server-rail-item, .guild-row, .guild-name, .server-name, [data-guild-name], [data-user-name], [data-server-name], [data-no-translate-name='1']"
          )
        ) {
          return true;
        }
        if (element instanceof HTMLOptionElement || element.closest("option")) {
          const select = element.closest("select");
          if (select instanceof HTMLSelectElement) {
            const selectHint = `${select.id || ""} ${select.name || ""} ${select.className || ""}`.toLowerCase();
            if (
              select.closest("[data-no-auto-i18n='1']") ||
              /guild|server|member|user|owner|admin|channel|role|playlist|queue|voice|product|item/.test(selectHint)
            ) {
              return true;
            }
          }
        }
        return false;
      };
      const shouldSkipLooseNode = (node) => {
        if (!(node instanceof Text)) return true;
        const parent = node.parentElement;
        if (!(parent instanceof HTMLElement)) return true;
        if (parent.closest("[data-i18n]")) return true;
        if (isLooseProtectedElement(parent)) return true;
        const tag = String(parent.tagName || "").toUpperCase();
        if (["SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA"].includes(tag)) return true;
        return false;
      };
      let isApplyingLooseI18n = false;
      const localizeUnkeyedDashboardText = (lang, root = document.body) => {
        const scanRoot = root instanceof HTMLElement || root instanceof Document ? root : document.body;
        if (!scanRoot) return;
        if (isApplyingLooseI18n) return;
        isApplyingLooseI18n = true;
        try {
          const walker = document.createTreeWalker(scanRoot, NodeFilter.SHOW_TEXT);
          const textNodes = [];
          while (walker.nextNode()) {
            const current = walker.currentNode;
            if (!(current instanceof Text)) continue;
            if (shouldSkipLooseNode(current)) continue;
            textNodes.push(current);
          }
          textNodes.forEach((textNode) => {
            const currentText = String(textNode.textContent || "");
            if (!currentText.trim()) return;
            const translated = translateLooseText(currentText, lang);
            if (translated !== currentText) {
              textNode.textContent = translated;
            }
          });

          const translatableAttrs = ["placeholder", "title", "aria-label"];
          scanRoot.querySelectorAll("input, textarea, button, a, label, [placeholder], [title], [aria-label]").forEach((el) => {
            if (!(el instanceof HTMLElement)) return;
            if (isLooseProtectedElement(el)) return;
            translatableAttrs.forEach((attrName) => {
              const value = el.getAttribute(attrName);
              if (!value || !String(value).trim()) return;
              const translated = translateLooseText(value, lang);
              if (translated !== value) {
                el.setAttribute(attrName, translated);
              }
            });
            if (el instanceof HTMLInputElement) {
              const inputType = String(el.type || "").toLowerCase();
              if (["button", "submit", "reset"].includes(inputType)) {
                const value = String(el.value || "");
                if (value.trim()) {
                  const translated = translateLooseText(value, lang);
                  if (translated !== value) {
                    el.value = translated;
                  }
                }
              }
            }
          });
        } finally {
          isApplyingLooseI18n = false;
        }
      };
      let looseI18nTimer = 0;
      let looseI18nRaf = 0;
      let looseI18nQueued = false;
      let looseI18nObserver = null;
      const shouldApplyLooseI18n = (lang) => {
        const enabled = Boolean(__BOOT.enableLooseI18n || (__BOOT.perf && __BOOT.perf.looseI18n));
        if (!enabled) return false;
        const normalized = String(lang || "").toLowerCase();
        return normalized === "th" || normalized === "en";
      };
      const scheduleLooseI18n = (root = document.body) => {
        if (!shouldApplyLooseI18n(currentLanguage)) {
          return;
        }
        if (looseI18nQueued) {
          return;
        }
        looseI18nQueued = true;
        const flush = () => {
          looseI18nQueued = false;
          localizeUnkeyedDashboardText(currentLanguage, root);
        };
        if (typeof window.requestIdleCallback === "function") {
          window.requestIdleCallback(flush, { timeout: 900 });
          return;
        }
        try {
          looseI18nRaf = window.requestAnimationFrame(() => {
            looseI18nRaf = 0;
            flush();
          });
          return;
        } catch (_error) {
        }
        if (looseI18nRaf) {
          try {
            window.cancelAnimationFrame(looseI18nRaf);
          } catch (_error) {
          }
          looseI18nRaf = 0;
        }
        if (looseI18nTimer) {
          window.clearTimeout(looseI18nTimer);
        }
        looseI18nTimer = window.setTimeout(() => {
          looseI18nTimer = 0;
          try {
            looseI18nRaf = window.requestAnimationFrame(() => {
              looseI18nRaf = 0;
              localizeUnkeyedDashboardText(currentLanguage);
            });
          } catch (_error) {
            localizeUnkeyedDashboardText(currentLanguage);
          }
        }, 0);
      };
      const stopLooseI18nObserver = () => {
        if (looseI18nObserver) {
          try {
            looseI18nObserver.disconnect();
          } catch (_error) {
          }
          looseI18nObserver = null;
        }
        if (looseI18nTimer) {
          window.clearTimeout(looseI18nTimer);
          looseI18nTimer = 0;
        }
        if (looseI18nRaf) {
          try {
            window.cancelAnimationFrame(looseI18nRaf);
          } catch (_error) {
          }
          looseI18nRaf = 0;
        }
        looseI18nQueued = false;
      };
      const ensureLooseI18nObserver = () => {
        if (!window.MutationObserver || looseI18nObserver || !(document.body instanceof HTMLElement)) {
          return;
        }
        looseI18nObserver = new MutationObserver(() => {
          if (isApplyingLooseI18n || !shouldApplyLooseI18n(currentLanguage)) return;
          scheduleLooseI18n(document.querySelector(".dashboard-dynamic-content") || document.body);
        });
        looseI18nObserver.observe(document.querySelector(".dashboard-dynamic-content") || document.body, {
          childList: true,
          subtree: true,
          characterData: false,
        });
      };
      let dialogWrapped = false;
      const wrapNativeDialogs = () => {
        if (dialogWrapped) return;
        dialogWrapped = true;
        const originalAlert = typeof window.alert === "function" ? window.alert.bind(window) : null;
        const originalConfirm = typeof window.confirm === "function" ? window.confirm.bind(window) : null;
        const originalPrompt = typeof window.prompt === "function" ? window.prompt.bind(window) : null;
        if (originalAlert) {
          window.alert = (message) => originalAlert(translateLooseValue(message, currentLanguage));
        }
        if (originalConfirm) {
          window.confirm = (message) => originalConfirm(translateLooseValue(message, currentLanguage));
        }
        if (originalPrompt) {
          window.prompt = (message, defaultValue) => {
            const translatedMessage = translateLooseValue(message, currentLanguage);
            const translatedDefault = translateLooseValue(defaultValue, currentLanguage);
            return originalPrompt(translatedMessage, translatedDefault);
          };
        }
      };
      const exposeLooseTranslator = () => {
        try {
          window.dashboardTranslateLoose = (value, langOverride) =>
            translateLooseValue(value, resolveLooseLang(langOverride || currentLanguage));
          window.dashboardTranslateLooseMarkup = (value, langOverride) =>
            translateLooseMarkup(String(value ?? ""), resolveLooseLang(langOverride || currentLanguage));
        } catch (_error) {
        }
      };
      const renderThemeToggleButton = (theme) => {
        const useLightTheme = theme === "light";
        const iconClass = useLightTheme ? "bi bi-moon-stars-fill" : "bi bi-sun-fill";
        const actionLabel = useLightTheme ? "Switch to dark mode" : "Switch to light mode";
        themeToggleButtons.forEach((button) => {
          button.setAttribute("aria-label", actionLabel);
          button.setAttribute("title", actionLabel);
          button.innerHTML = `<i class="${iconClass}" aria-hidden="true"></i>`;
        });
      };
      const resetAccentTheme = () => {
        accentThemeClasses.forEach((className) => body.classList.remove(className));
        safeStorageSet("skyline_accent", "default");
      };
      const applyTheme = (theme) => {
        body.classList.toggle("light-theme", theme === "light");
        document.documentElement.style.colorScheme = theme === "light" ? "light" : "dark";
        renderThemeToggleButton(theme);
        try {
          window.dispatchEvent(new CustomEvent("dashboard:theme-change", { detail: { theme } }));
        } catch (_error) {
        }
      };
      const trustedCarousel = document.getElementById("trustedCarousel");
      const trustedServerGrid = document.getElementById("trustedServerGrid");
      const trustedServerRowPrimary = document.getElementById("trustedServerRowPrimary");
      const trustedServerRowSecondary = document.getElementById("trustedServerRowSecondary");
      let trustedSyncHandle = 0;
      const syncTrustedCarousel = () => {
        trustedSyncHandle = 0;
        if (!trustedCarousel || !trustedServerGrid || !trustedServerRowPrimary || !trustedServerRowSecondary) {
          return;
        }
        const distance = Math.ceil(trustedServerRowPrimary.getBoundingClientRect().width || 0);
        if (distance <= 0) {
          return;
        }
        const speedPxPerSecond = 26;
        const duration = Math.max(40, Math.min(120, distance / speedPxPerSecond));
        trustedCarousel.style.setProperty("--trusted-loop-distance", `${distance}px`);
        trustedCarousel.style.setProperty("--trusted-loop-duration", `${duration}s`);
      };
      const scheduleTrustedCarouselSync = () => {
        if (trustedSyncHandle) {
          window.cancelAnimationFrame(trustedSyncHandle);
        }
        trustedSyncHandle = window.requestAnimationFrame(syncTrustedCarousel);
      };
      const applyLanguageCore = (resolvedLang) => {
        currentLanguage = resolvedLang;
        document.documentElement.lang = resolvedLang;
        safeStorageSet("skyline_lang", resolvedLang);
        setLanguageCookie(resolvedLang);
        syncLanguageUrlPrefix(resolvedLang);

        const dict = i18n[resolvedLang] || {};
        const fallback = (i18n.th && Object.keys(i18n.th).length) ? i18n.th : dict;
        document.querySelectorAll("[data-i18n]").forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          const key = String(node.dataset.i18n || "").trim();
          if (!key) return;
          const translated = resolveI18nValue(dict, fallback, key, resolvedLang);
          if (typeof translated !== "string" || !translated.trim()) return;
          applyTranslatedText(node, translated);
        });

        document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          const key = String(node.getAttribute("data-i18n-placeholder") || "").trim();
          if (!key) return;
          const translated = resolveI18nValue(dict, fallback, key, resolvedLang);
          if (typeof translated !== "string" || !translated.trim()) return;
          node.setAttribute("placeholder", translated);
        });
        document.querySelectorAll("[data-i18n-title]").forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          const key = String(node.getAttribute("data-i18n-title") || "").trim();
          if (!key) return;
          const translated = resolveI18nValue(dict, fallback, key, resolvedLang);
          if (typeof translated !== "string" || !translated.trim()) return;
          node.setAttribute("title", translated);
        });
        document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          const key = String(node.getAttribute("data-i18n-aria-label") || "").trim();
          if (!key) return;
          const translated = resolveI18nValue(dict, fallback, key, resolvedLang);
          if (typeof translated !== "string" || !translated.trim()) return;
          node.setAttribute("aria-label", translated);
        });

        renderThemeToggleButton(body.classList.contains("light-theme") ? "light" : "dark");
        langToggleButtons.forEach((button) => {
          const nextLang = resolvedLang === "th" ? "en" : "th";
          const label = decorateLanguageToggleButton(button);
          if (label instanceof HTMLElement) {
            label.textContent = nextLang.toUpperCase();
          } else {
            button.textContent = nextLang.toUpperCase();
          }
          const switchLabel = nextLang === "en" ? "Switch to English" : "Switch to Thai";
          button.setAttribute("aria-label", switchLabel);
          button.setAttribute("title", switchLabel);
        });
        if (shouldApplyLooseI18n(resolvedLang)) {
          localizeUnkeyedDashboardText(resolvedLang);
          ensureLooseI18nObserver();
          scheduleLooseI18n();
        } else {
          stopLooseI18nObserver();
        }
        scheduleTrustedCarouselSync();
        try {
          window.dispatchEvent(new CustomEvent("dashboard:language-change", { detail: { language: resolvedLang } }));
        } catch (_error) {
        }
      };
      const applyLanguage = (lang) => {
        const normalized = String(lang || "").toLowerCase();
        const resolvedLang = normalized === "en" ? "en" : "th";
        ensureI18nDictionary(resolvedLang)
          .catch(() => {})
          .finally(() => {
            applyLanguageCore(resolvedLang);
          });
      };
      resetAccentTheme();
      stripKnownStrayLayoutText();
      ensureFloatingLanguageToggleButton();
      applyTheme(storedTheme);
      exposeLooseTranslator();
      wrapNativeDialogs();
      applyLanguage(initialLang);
      scheduleTrustedCarouselSync();
      window.addEventListener("resize", scheduleTrustedCarouselSync);
      window.setTimeout(scheduleTrustedCarouselSync, 180);
      themeToggleButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const next = body.classList.contains("light-theme") ? "dark" : "light";
          safeStorageSet("skyline_theme", next);
          applyTheme(next);
        });
      });
      langToggleButtons.forEach((button) => {
        button.addEventListener("click", () => {
          applyLanguage(currentLanguage === "th" ? "en" : "th");
        });
      });

      const REAL_GUILD_HISTORY = Array.isArray(__BOOT.guildGrowthEvents) ? __BOOT.guildGrowthEvents : [];
      const readGuildCountFromDom = () => {
        const el = document.getElementById("currentGuildCount");
        if (!el) return 0;
        const raw = String(el.textContent || "").replace(/[^0-9]/g, "");
        const value = Number(raw || "0");
        return Number.isFinite(value) ? Math.max(0, value) : 0;
      };
      const REAL_GUILD_COUNT = Math.max(0, Number(__BOOT.guildCount || 0)) || readGuildCountFromDom();
      const BOT_CREATED_TS = Number(__BOOT.botCreatedTsMs || Date.now());
      const CHART_PERIOD_PALETTES = {
        week: { line: '#22d3ee', fill: 'rgba(34, 211, 238, 0.28)' },
        month: { line: '#34d399', fill: 'rgba(52, 211, 153, 0.28)' },
        year: { line: '#f59e0b', fill: 'rgba(245, 158, 11, 0.30)' },
        all: { line: '#ec4899', fill: 'rgba(236, 72, 153, 0.30)' }
      };

      function buildGrowthData(period) {
        const nowTs = Date.now();
        const nowDate = new Date(nowTs);
        const botBirthTs = Number.isFinite(Number(BOT_CREATED_TS)) ? Math.max(0, Number(BOT_CREATED_TS)) : nowTs;
        const botBirthDate = new Date(botBirthTs);
        const chartLocale = currentLanguage === "en" ? "en-US" : "th-TH";

        const rawHistory = Array.isArray(REAL_GUILD_HISTORY) ? REAL_GUILD_HISTORY : [];
        const currentGuildCeiling = Math.max(0, Math.round(Number(REAL_GUILD_COUNT || 0)));
        const parsedHistory = rawHistory
          .map((item) => ({
            ts: Number(item && item.ts),
            count: (() => {
              const rawCount = Math.max(0, Math.round(Number(item && item.count)));
              if (currentGuildCeiling > 0) {
                return Math.min(rawCount, currentGuildCeiling);
              }
              return rawCount;
            })(),
          }))
          .filter((item) => Number.isFinite(item.ts) && Number.isFinite(item.count))
          .sort((a, b) => a.ts - b.ts);

        const history = [];
        for (const item of parsedHistory) {
          const last = history[history.length - 1];
          if (last && Number(last.ts) === Number(item.ts)) {
            history[history.length - 1] = item;
          } else {
            history.push(item);
          }
        }

        if (!history.length) {
          history.push({ ts: nowTs, count: Math.max(0, REAL_GUILD_COUNT) });
        }
        if (history[0].ts > botBirthTs) {
          history.unshift({ ts: botBirthTs, count: 0 });
        }
        const lastHistory = history[history.length - 1];
        if (!lastHistory || Number(lastHistory.ts) < nowTs) {
          history.push({ ts: nowTs, count: Math.max(0, REAL_GUILD_COUNT) });
        } else {
          history[history.length - 1] = { ts: nowTs, count: Math.max(0, REAL_GUILD_COUNT) };
        }

        const growthEvents = [];
        let runningMaxCount = 0;
        for (const entry of history) {
          const ts = Number(entry && entry.ts);
          const count = Math.max(0, Math.round(Number(entry && entry.count)));
          if (!Number.isFinite(ts)) continue;
          // Ignore temporary drops/recoveries (e.g. cache warm-up) and only count net new highs.
          const normalizedCount = count < runningMaxCount ? runningMaxCount : count;
          const diff = Math.max(0, normalizedCount - runningMaxCount);
          if (diff > 0) {
            growthEvents.push({ ts, value: diff });
          }
          runningMaxCount = normalizedCount;
        }

        const growthInRange = (startTs, endTs) => {
          const start = Number(startTs || 0);
          const end = Number(endTs || 0);
          if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return 0;
          let sum = 0;
          for (const item of growthEvents) {
            const ts = Number(item.ts || 0);
            if (ts < start) continue;
            if (ts > end) break;
            sum += Math.max(0, Number(item.value || 0));
          }
          return Math.max(0, Math.round(sum));
        };

        const labels = [];
        const points = [];
        const addPoint = (label, startTs, endTs) => {
          labels.push(String(label || ""));
          points.push(growthInRange(startTs, endTs));
        };
        const monthLabel = (year, month, withYear = false) => {
          const monthText = new Date(year, month, 1).toLocaleDateString(chartLocale, { month: "short" });
          if (!withYear) return monthText;
          const yearText = new Date(year, month, 1).toLocaleDateString(chartLocale, { year: "2-digit" });
          return `${monthText} ${yearText}`;
        };

        if (period === "week") {
          // Last 4 weeks (28 days), always 4 buckets.
          const dayMs = 24 * 60 * 60 * 1000;
          const todayStartTs = new Date(nowDate.getFullYear(), nowDate.getMonth(), nowDate.getDate()).getTime();
          const rangeStartTs = todayStartTs - (27 * dayMs);
          for (let weekIndex = 0; weekIndex < 4; weekIndex += 1) {
            const bucketStart = rangeStartTs + (weekIndex * 7 * dayMs);
            const bucketEnd = Math.min(nowTs, bucketStart + (7 * dayMs) - 1);
            addPoint(`W${weekIndex + 1}`, bucketStart, bucketEnd);
          }
        } else if (period === "month") {
          // Rolling 12 months, always 12 buckets.
          const thisMonthStart = new Date(nowDate.getFullYear(), nowDate.getMonth(), 1);
          for (let offset = 11; offset >= 0; offset -= 1) {
            const marker = new Date(thisMonthStart.getFullYear(), thisMonthStart.getMonth() - offset, 1);
            const y = marker.getFullYear();
            const m = marker.getMonth();
            const startTs = new Date(y, m, 1, 0, 0, 0, 0).getTime();
            const endTs = Math.min(nowTs, new Date(y, m + 1, 0, 23, 59, 59, 999).getTime());
            const includeYear = y !== nowDate.getFullYear();
            addPoint(monthLabel(y, m, includeYear), startTs, endTs);
          }
        } else if (period === "year") {
          // Current year, every month (12 buckets).
          const currentYear = nowDate.getFullYear();
          for (let month = 0; month < 12; month += 1) {
            const startTs = new Date(currentYear, month, 1, 0, 0, 0, 0).getTime();
            const endTs = new Date(currentYear, month + 1, 0, 23, 59, 59, 999).getTime();
            addPoint(monthLabel(currentYear, month, false), startTs, endTs);
          }
        } else {
          // All-time view = every year since bot creation year.
          const startYear = botBirthDate.getFullYear();
          const endYear = nowDate.getFullYear();
          for (let year = startYear; year <= endYear; year += 1) {
            const yearLabel = new Date(year, 0, 1).toLocaleDateString(chartLocale, { year: "numeric" });
            const startTs = new Date(year, 0, 1, 0, 0, 0, 0).getTime();
            const endTs = Math.min(nowTs, new Date(year, 11, 31, 23, 59, 59, 999).getTime());
            addPoint(yearLabel, startTs, endTs);
          }
        }

        return { labels, points };
      }

      const chartThemeTokens = () => {
        const styles = window.getComputedStyle(document.body);
        const isLight = document.body.classList.contains("light-theme");
        const fallbackGrid = isLight ? "rgba(43, 73, 130, 0.26)" : "rgba(255,255,255,0.34)";
        const fallbackTicks = isLight ? "rgba(25, 47, 92, 0.90)" : "rgba(236,241,255,.85)";
        const fallbackTooltipBg = isLight ? "rgba(245, 250, 255, 0.96)" : "rgba(12, 17, 32, 0.94)";
        const fallbackTooltipBorder = isLight ? "rgba(64, 112, 206, 0.34)" : "rgba(120, 156, 230, 0.34)";
        const pick = (value, fallback) => {
          const normalized = String(value || "").trim();
          return normalized || fallback;
        };
        return {
          gridColor: pick(styles.getPropertyValue("--line"), fallbackGrid),
          tickColor: pick(styles.getPropertyValue("--text"), fallbackTicks),
          tooltipBg: fallbackTooltipBg,
          tooltipText: pick(styles.getPropertyValue("--text"), fallbackTicks),
          tooltipBorder: pick(styles.getPropertyValue("--line-strong"), fallbackTooltipBorder),
        };
      };

      let invChart = null;
      let activeChartPeriod = "month";
      const invitationCtx = document.getElementById('invitationChart');
      if (invitationCtx) {
        const ensureChartLibrary = () =>
          ensureLazyScript(
            "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js",
            () => typeof window.Chart === "function"
          );
        const bootChart = () => {
          const ChartLib = window.Chart;
          if (typeof ChartLib !== "function") return;
          function renderChart(period) {
            activeChartPeriod = String(period || "month");
            const { labels, points } = buildGrowthData(activeChartPeriod);
            const palette = CHART_PERIOD_PALETTES[activeChartPeriod] || CHART_PERIOD_PALETTES.month;
            const theme = chartThemeTokens();
            const maxPoint = points.length ? Math.max(...points) : 0;
            const yPadding = Math.max(1, Math.ceil(maxPoint * 0.18));
            const yMin = 0;
            const yMax = Math.max(2, maxPoint + yPadding);
            if (invChart) {
              invChart.data.labels = labels;
              invChart.data.datasets[0].data = points;
              invChart.data.datasets[0].borderColor = palette.line;
              invChart.data.datasets[0].backgroundColor = palette.fill;
              invChart.options.scales.y.min = yMin;
              invChart.options.scales.y.max = yMax;
              invChart.options.scales.y.grid.color = theme.gridColor;
              invChart.options.scales.y.ticks.color = theme.tickColor;
              invChart.options.scales.x.grid.color = theme.gridColor;
              invChart.options.scales.x.ticks.color = theme.tickColor;
              invChart.options.scales.x.ticks.autoSkip = false;
              invChart.options.scales.x.ticks.maxRotation = 0;
              invChart.options.scales.x.ticks.minRotation = 0;
              invChart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
              invChart.options.plugins.tooltip.titleColor = theme.tooltipText;
              invChart.options.plugins.tooltip.bodyColor = theme.tooltipText;
              invChart.options.plugins.tooltip.borderColor = theme.tooltipBorder;
              invChart.options.plugins.tooltip.borderWidth = 1;
              invChart.update();
            } else {
              invChart = new ChartLib(invitationCtx, {
                type: 'line',
                data: {
                  labels,
                  datasets: [{
                    label: 'Servers Added',
                    data: points,
                    borderColor: palette.line,
                    backgroundColor: palette.fill,
                    fill: true,
                    tension: 0.34,
                    stepped: false,
                    cubicInterpolationMode: 'monotone',
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHitRadius: 14,
                    borderWidth: 2
                  }]
                },
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { display: false },
                    tooltip: {
                      backgroundColor: theme.tooltipBg,
                      titleColor: theme.tooltipText,
                      bodyColor: theme.tooltipText,
                      borderColor: theme.tooltipBorder,
                      borderWidth: 1,
                      callbacks: {
                        label: ctx => `Added: ${ctx.parsed.y}`
                      }
                    }
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      min: yMin,
                      max: yMax,
                      grid: {
                        color: theme.gridColor,
                        borderDash: [4, 4],
                        tickLength: 0,
                        drawBorder: false
                      },
                      ticks: {
                        color: theme.tickColor,
                        precision: 0,
                        callback: (value) => Number.isInteger(value) ? value : ''
                      }
                    },
                    x: {
                      grid: {
                        color: theme.gridColor,
                        borderDash: [4, 4],
                        drawBorder: false
                      },
                      ticks: {
                        color: theme.tickColor,
                        autoSkip: false,
                        maxRotation: 0,
                        minRotation: 0
                      }
                    }
                  }
                }
              });
            }
          }
          renderChart('month');
          window.switchChartPeriod = function(period, btn) {
            document.querySelectorAll('.chart-period-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
            renderChart(period);
          };
          window.addEventListener("dashboard:theme-change", () => {
            renderChart(activeChartPeriod);
          });
          window.addEventListener("dashboard:language-change", () => {
            renderChart(activeChartPeriod);
          });
        };
        ensureChartLibrary().then(bootChart).catch(() => {});
      }

      if (topbar) {
        let topbarRaf = 0;
        let topbarScrolled = null;
        const applyTopbarState = () => {
          topbarRaf = 0;
          const nextScrolled = window.scrollY > 6;
          if (nextScrolled === topbarScrolled) return;
          topbarScrolled = nextScrolled;
          topbar.classList.toggle("scrolled", nextScrolled);
        };
        const queueTopbarStateSync = () => {
          if (topbarRaf) return;
          topbarRaf = window.requestAnimationFrame(applyTopbarState);
        };
        queueTopbarStateSync();
        window.addEventListener("scroll", queueTopbarStateSync, { passive: true });
        window.addEventListener("resize", queueTopbarStateSync, { passive: true });
      }

      const revealTargets = document.querySelectorAll(".panel, .guild-card, .command-category");
      revealTargets.forEach((el) => {
        el.classList.add("reveal-ready", "reveal-in");
      });

      const publicSearch = document.getElementById("publicCommandSearch");
      const publicNoResult = document.getElementById("publicCommandNoResult");
      const publicCategories = Array.from(document.querySelectorAll(".public-command-category"));
      if (publicCategories.length) {
        const storageKey = "skyline_public_commands_open";
        const loadOpenState = () => {
          try {
            const raw = localStorage.getItem(storageKey);
            if (!raw) {
              return;
            }
            const saved = new Set(JSON.parse(raw));
            if (!saved.size) {
              return;
            }
            publicCategories.forEach((category) => {
              const key = category.dataset.categoryKey || "";
              category.open = saved.has(key);
            });
          } catch (_error) {
          }
        };
        const saveOpenState = () => {
          try {
            const opened = publicCategories
              .filter((category) => category.open)
              .map((category) => category.dataset.categoryKey || "")
              .filter(Boolean);
            localStorage.setItem(storageKey, JSON.stringify(opened));
          } catch (_error) {
          }
        };
        loadOpenState();
        publicCategories.forEach((category) => {
          category.addEventListener("toggle", () => {
            if (publicSearch && publicSearch.value.trim()) {
              return;
            }
            saveOpenState();
          });
        });

        if (publicSearch) {
          const applyPublicFilter = () => {
            const query = publicSearch.value.trim().toLowerCase();
            let matchedRows = 0;
            publicCategories.forEach((category) => {
              const rows = Array.from(category.querySelectorAll(".public-command-row"));
              let visible = 0;
              rows.forEach((row) => {
                const haystack = (row.dataset.commandText || "").toLowerCase();
                const match = !query || haystack.includes(query);
                row.style.display = match ? "" : "none";
                if (match) {
                  visible += 1;
                }
              });
              const count = category.querySelector(".category-count");
              if (count) {
                const commandUnit = currentLanguage === "en" ? "commands" : "คำสั่ง";
                count.textContent = query ? `${visible} / ${rows.length} ${commandUnit}` : `${rows.length} ${commandUnit}`;
              }
              category.style.display = (!query || visible > 0) ? "" : "none";
              if (query && visible > 0 && !category.open) {
                category.open = true;
              }
              matchedRows += visible;
            });
            if (publicNoResult) {
              publicNoResult.style.display = query && matchedRows === 0 ? "" : "none";
            }
          };
          publicSearch.addEventListener("input", applyPublicFilter);
        }
      }

      const currentPath = String(window.location.pathname || "");
      const isUserMusicRoute = /^\/dashboard\/music\/\d+/.test(currentPath);
      const guildIdFromPathMatch = currentPath.match(/^\/dashboard\/(?:music|guild)\/(\d+)/);
      const guildId = String(__BOOT.guildId || (guildIdFromPathMatch ? guildIdFromPathMatch[1] : ""));
      const activeTab = String(__BOOT.activeTab || (isUserMusicRoute ? "music" : "")).trim().toLowerCase();
      const liveEndpoint = isUserMusicRoute
        ? `/dashboard/music/${guildId}/live`
        : `/dashboard/guild/${guildId}/live`;
      const liveOptionsEndpoint = isUserMusicRoute
        ? `/dashboard/music/${guildId}/live/options`
        : `/dashboard/guild/${guildId}/live/options`;
      const activeTabForLiveOptions = activeTab || (isUserMusicRoute ? "music" : "overview");
      const musicControlEndpoint = isUserMusicRoute
        ? `/dashboard/music/${guildId}/control`
        : `/dashboard/guild/${guildId}/music/control`;
      const htmlEscape = (value) => String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
      const runWhenIdle = (callback, timeoutMs = 1500) => {
        if (typeof window.requestIdleCallback === "function") {
          window.requestIdleCallback(callback, { timeout: timeoutMs });
        } else {
          window.setTimeout(callback, Math.min(timeoutMs, 1000));
        }
      };

      const channelPrefix = (type) => {
        if (["text", "news", "forum"].includes(type)) return " # ";
        if (["voice", "stage_voice"].includes(type)) return "  ";
        if (type === "category") return "  ";
        return " • ";
      };

      const parseFilterTypes = (raw) => String(raw || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);

      const liveOptionsLocale = () => (currentLanguage === "en" ? "en" : "th");
      const liveOptionsText = (key) => {
        const dict = {
          selectChannel: "Select channel...",
          selectRole: "Select role...",
          addRole: "Add role...",
          missingChannel: "Missing previous channel",
          missingRole: "Missing previous role",
        };
        const base = String(dict[key] || "");
        if (!base) return base;
        if (liveOptionsLocale() === "en") {
          return base;
        }
        return liveOptionsTranslate(base);
      };
      const liveOptionsTranslate = (value) => {
        const textValue = String(value || "");
        if (!textValue) return textValue;
        try {
          if (typeof window.dashboardTranslateLoose === "function") {
            const translated = window.dashboardTranslateLoose(textValue, liveOptionsLocale());
            if (typeof translated === "string" && translated.trim()) {
              return translated;
            }
          }
        } catch (_error) {
        }
        return textValue;
      };

      const updateChannelSelects = (channels) => {
        document.querySelectorAll('select[data-live-options="channel"]').forEach((select) => {
          const previous = String(select.value || "");
          const defaultPlaceholder = liveOptionsText("selectChannel");
          const rawPlaceholder = String(select.dataset.placeholder || (select.options[0]?.textContent || defaultPlaceholder));
          const placeholder = liveOptionsTranslate(rawPlaceholder);
          const filters = parseFilterTypes(select.dataset.liveFilter);
          const allowed = channels.filter((item) => filters.length === 0 || filters.includes(String(item.type || "")));
          const hasPrev = allowed.some((item) => String(item.id) === previous);
          const options = [`<option value="">${htmlEscape(placeholder || defaultPlaceholder)}</option>`];
          allowed.forEach((item) => {
            const selected = String(item.id) === previous ? " selected" : "";
            options.push(`<option value="${htmlEscape(item.id)}"${selected}>${htmlEscape(channelPrefix(item.type) + " " + (item.name || item.id))}</option>`);
          });
          if (previous && !hasPrev) {
            const missingLabel = `${liveOptionsText("missingChannel")} (${previous})`;
            options.push(`<option value="${htmlEscape(previous)}" selected>${htmlEscape(missingLabel)}</option>`);
          }
          select.innerHTML = options.join("");
          if (typeof window.__syncDashboardSearchableSelect === "function") {
            window.__syncDashboardSearchableSelect(select);
          }
        });
      };

      const updateRoleSelects = (roles) => {
        document.querySelectorAll('select[data-live-options="role"]').forEach((select) => {
          const previous = String(select.value || "");
          const defaultPlaceholder = liveOptionsText("selectRole");
          const rawPlaceholder = String(select.dataset.placeholder || (select.options[0]?.textContent || defaultPlaceholder));
          const placeholder = liveOptionsTranslate(rawPlaceholder);
          const hasPrev = roles.some((item) => String(item.id) === previous);
          const options = [`<option value="">${htmlEscape(placeholder || defaultPlaceholder)}</option>`];
          roles.forEach((item) => {
            const selected = String(item.id) === previous ? " selected" : "";
            options.push(`<option value="${htmlEscape(item.id)}"${selected}>@ ${htmlEscape(item.name || item.id)}</option>`);
          });
          if (previous && !hasPrev) {
            const missingLabel = `${liveOptionsText("missingRole")} (${previous})`;
            options.push(`<option value="${htmlEscape(previous)}" selected>${htmlEscape(missingLabel)}</option>`);
          }
          select.innerHTML = options.join("");
          if (typeof window.__syncDashboardSearchableSelect === "function") {
            window.__syncDashboardSearchableSelect(select);
          }
        });
      };

      const updateMultiRoleSelects = (roles) => {
        const roleMap = new Map((roles || []).map((item) => [String(item.id), String(item.name || item.id)]));
        document.querySelectorAll('.multi-role-select[data-live-options="role-multi"]').forEach((wrap) => {
          const roleName = wrap.dataset.roleName || "";
          if (!roleName) return;
          const input = document.getElementById(`input_${roleName}`);
          const tagsContainer = document.getElementById(`tags_${roleName}`);
          const adder = wrap.querySelector("select.tag-adder");
          if (!input || !tagsContainer || !adder) return;

          const selectedIds = Array.from(new Set(
            String(input.value || "")
              .split(",")
              .map((item) => item.trim())
              .filter((item) => item && roleMap.has(item))
          ));
          input.value = selectedIds.join(",");

          tagsContainer.innerHTML = selectedIds
            .map((rid) => `<div class="tag-pill" data-id="${htmlEscape(rid)}">${htmlEscape(roleMap.get(rid) || rid)} <span class="remove" onclick="removeTag(this, '${htmlEscape(roleName)}')">&times;</span></div>`)
            .join("");

          const addRoleText = liveOptionsText("addRole");
          const options = [`<option value="">${htmlEscape(addRoleText)}</option>`];
          roles.forEach((role) => {
            const rid = String(role.id);
            if (selectedIds.includes(rid)) return;
            options.push(`<option value="${htmlEscape(rid)}">@ ${htmlEscape(role.name || rid)}</option>`);
          });
          adder.innerHTML = options.join("");
          if (typeof window.__syncTagSearchForSelect === "function") {
            window.__syncTagSearchForSelect(adder);
          }
        });
      };

      const applyLiveOptions = (payload) => {
        if (!payload || typeof payload !== "object") return;
        const channels = Array.isArray(payload.channels) ? payload.channels : [];
        const roles = Array.isArray(payload.roles) ? payload.roles : [];
        updateChannelSelects(channels);
        updateRoleSelects(roles);
        updateMultiRoleSelects(roles);
      };

      const LIVE_OPTIONS_POLL_INTERVAL_MS = 60000;
      const notifyLiveAccessDenied = (() => {
        let lastWarnAt = 0;
        return () => {
          const now = Date.now();
          if (now - lastWarnAt < 8000) return;
          lastWarnAt = now;
          const isEn = String(document.documentElement.lang || "").toLowerCase().startsWith("en");
          const message = isEn
            ? "Live update access was denied. Please refresh if your permissions changed."
            : "สิทธิ์อัปเดตแบบเรียลไทม์ถูกปฏิเสธ กรุณารีเฟรชหากสิทธิ์เพิ่งมีการเปลี่ยนแปลง";
          if (window.__dashboardFeedback && typeof window.__dashboardFeedback.notify === "function") {
            window.__dashboardFeedback.notify(message, "warning", { dedupeWindowMs: 2000 });
            return;
          }
          if (typeof window.showToast === "function") {
            window.showToast(message, "warning");
          }
        };
      })();
      let __lastOptionsSignature = "";
      let __lastOptionsEtag = "";
      const fetchLiveOptions = async ({ force = false } = {}) => {
        if (!guildId) return;
        if (!force && document.visibilityState !== "visible") return;
        try {
          const liveOptionsUrl = `${liveOptionsEndpoint}?tab=${encodeURIComponent(activeTabForLiveOptions)}`;
          const headers = { "X-Requested-With": "fetch" };
          if (__lastOptionsEtag) {
            headers["If-None-Match"] = __lastOptionsEtag;
          }
          const response = await fetch(liveOptionsUrl, {
            headers,
            credentials: "same-origin",
            cache: "no-cache",
          });
          if (response.status === 304) {
            return;
          }
          if (!response.ok) {
            if (response.status === 403) {
              notifyLiveAccessDenied();
            }
            return;
          }
          const nextEtag = String(response.headers.get("etag") || "").trim();
          if (nextEtag) {
            __lastOptionsEtag = nextEtag;
          }
          const payload = await response.json();
          const signature = String(payload?.signature || "");
          if (signature === __lastOptionsSignature) return;
          __lastOptionsSignature = signature;
          applyLiveOptions(payload);
        } catch (_error) {
        }
      };

      const hasLiveOptionTargets = () =>
        Boolean(
          document.querySelector(
            'select[data-live-options="channel"], select[data-live-options="role"], .multi-role-select[data-live-options="role-multi"]'
          )
        );
      let liveOptionsPollingTimer = 0;
      const startLiveOptionsPolling = () => {
        if (!guildId || liveOptionsPollingTimer || !hasLiveOptionTargets()) return;
        runWhenIdle(() => fetchLiveOptions({ force: true }), 2200);
        liveOptionsPollingTimer = window.setInterval(() => {
          if (!hasLiveOptionTargets()) {
            window.clearInterval(liveOptionsPollingTimer);
            liveOptionsPollingTimer = 0;
            return;
          }
          fetchLiveOptions();
        }, LIVE_OPTIONS_POLL_INTERVAL_MS);
      };

      window.__refreshLiveRoleOptions = () => {
        if (!guildId || !hasLiveOptionTargets()) return;
        fetchLiveOptions({ force: true });
        startLiveOptionsPolling();
      };

      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          fetchLiveOptions({ force: true });
        }
      });

      startLiveOptionsPolling();

      if (!guildId || !["overview", "music", "logs"].includes(activeTab)) {
        return;
      }

      const updateText = (selector, value) => {
        const el = document.querySelector(selector);
        if (el && value !== undefined && value !== null) {
          const next = String(value);
          if (el.textContent === next) return;
          el.textContent = next;
        }
      };

      const updateHTML = (selector, value) => {
        const el = document.querySelector(selector);
        if (el && value !== undefined && value !== null) {
          const next = String(value);
          if (el.innerHTML === next) return;
          el.innerHTML = next;
        }
      };

      const renderMusic = (music, logs) => {
        if (!music) {
          return;
        }
        latestMusicState = music;
        const lang = (document.documentElement.lang || "th").startsWith("en") ? "en" : "th";
        const text = lang === "th"
          ? {
              paused: "หยุดชั่วคราว",
              playing: "กำลังเล่น",
              offline: "ออฟไลน์",
              unknownTrack: "ไม่ทราบชื่อเพลง",
              noTrack: "ยังไม่มีเพลงที่กำลังเล่น",
              unknownAuthor: "ไม่ทราบผู้แต่ง",
              waitVoice: "รอให้บอทเล่นเพลงในห้องเสียงก่อน",
              voice: "ห้องเสียง",
              queue: "คิว",
              volume: "ระดับเสียง",
              loop: "วนซ้ำ",
              on: "เปิด",
              off: "ปิด",
              emptyQueue: "คิวเพลงว่าง",
              remove: "ลบ",
              playNow: "เล่นเลย",
              moveUp: "↑",
              moveDown: "↓",
              emptyQueueTable: "คิวว่างอยู่ตอนนี้",
            }
          : {
              paused: "Paused",
              playing: "Playing",
              offline: "Offline",
              unknownTrack: "Unknown track",
              noTrack: "No track is playing",
              unknownAuthor: "Unknown author",
              waitVoice: "Waiting for playback in voice channel",
              voice: "Voice",
              queue: "Queue",
              volume: "Volume",
              loop: "Loop",
              on: "On",
              off: "Off",
              emptyQueue: "Queue is empty",
              remove: "Remove",
              playNow: "Play Now",
              moveUp: "↑",
              moveDown: "↓",
              emptyQueueTable: "Queue is currently empty",
            };
        const isActive = Boolean(music.active);
        updateText('[data-live="music-state"]', isActive ? (music.paused ? text.paused : text.playing) : text.offline);
        updateText('[data-live="music-title"]', isActive ? (music.title || text.unknownTrack) : text.noTrack);
        updateText('[data-live="music-author"]', isActive ? (music.author || text.unknownAuthor) : text.waitVoice);
        updateText('[data-live="music-channel"]', `${text.voice}: ${music.channel || '-'}`);
        updateText('[data-live="music-time"]', `${music.position || '0s'} / ${music.duration || '0s'}`);
        updateText('[data-live="music-stats"]', `${text.queue}: ${music.queue_size || 0} | ${text.volume}: ${music.volume || 0}%`);
        updateText('[data-live="music-loop-status"]', `${text.loop}: ${music.loop ? text.on : text.off}`);
        document.querySelectorAll('[data-music-loop-btn]').forEach((button) => {
          button.textContent = music.loop ? (lang === "th" ? "วนซ้ำ เปิด" : "Loop On") : (lang === "th" ? "วนซ้ำ ปิด" : "Loop Off");
        });
        document.querySelectorAll('[data-music-autoplay-btn]').forEach((button) => {
          button.textContent = music.autoplay ? (lang === "th" ? "เล่นอัตโนมัติ เปิด" : "Autoplay On") : (lang === "th" ? "เล่นอัตโนมัติ ปิด" : "Autoplay Off");
        });
        const artwork = document.querySelector('[data-live="music-artwork"]');
        if (artwork && music.artwork) {
          artwork.src = music.artwork;
        }
        if (Array.isArray(music.queue_titles)) {
          updateHTML(
            '[data-live="music-queue"]',
            music.queue_titles.length
              ? music.queue_titles.map((title) => `<div class="mini-stat">${String(title || text.unknownTrack).replaceAll('<', '&lt;').replaceAll('>', '&gt;')}</div>`).join("")
              : `<span class="mini-stat">${text.emptyQueue}</span>`
          );
        }
        if (Array.isArray(music.queue_entries)) {
          const queueCardHtml = music.queue_entries.length
            ? music.queue_entries.map((item) => `
                <article class="music-queue-card">
                  <div>
                    <h4>#${item.index} - ${String(item.title || text.unknownTrack).replaceAll('<', '&lt;').replaceAll('>', '&gt;')}</h4>
                    <p>${String(item.duration || '0s')}</p>
                  </div>
                  <div class="music-queue-actions">
                    <button class="queue-playnow-btn" type="button" data-queue-index="${item.index}">${text.playNow}</button>
                    <button class="queue-move-btn" type="button" data-move-direction="up" data-queue-index="${item.index}">${text.moveUp}</button>
                    <button class="queue-move-btn" type="button" data-move-direction="down" data-queue-index="${item.index}">${text.moveDown}</button>
                    <button class="queue-remove-btn" type="button" data-queue-index="${item.index}">${text.remove}</button>
                  </div>
                </article>
              `).join('')
            : `<div class="music-queue-empty">${text.emptyQueueTable}</div>`;
          updateHTML('[data-live="music-queue-cards"]', queueCardHtml);
        }
        const activeNotice = document.querySelector('[data-live="music-active-notice"]');
        if (activeNotice) {
          activeNotice.style.display = isActive ? 'none' : '';
        }
        const volumeInput = document.getElementById('musicVolumeInput');
        if (volumeInput && !Number.isNaN(Number(music.volume))) {
          volumeInput.value = String(music.volume || 0);
        }
        const seekInput = document.getElementById('musicSeekInput');
        if (seekInput) {
          const durationMs = Number(music.duration_ms || 0);
          const positionMs = Number(music.position_ms || 0);
          seekInput.max = String(Math.max(0, durationMs));
          seekInput.value = String(Math.max(0, Math.min(positionMs, durationMs || positionMs)));
          seekInput.disabled = !isActive;
        }
        if (Array.isArray(logs)) {
          updateText('[data-live="music-log-box"]', logs.join("\\n"));
        }
      };
      const renderOverview = (payload) => {
        if (!payload || !payload.overview) {
          return;
        }
        updateText('[data-live=\"overview-guild-health\"]', String(payload.overview.guild_health ?? 0));
        updateText('[data-live=\"overview-security\"]', String(payload.overview.security ?? 0));
        updateText('[data-live=\"overview-moderation\"]', String(payload.overview.moderation ?? 0));
        renderMusic(payload.music, payload.music_logs);
      };

      const renderLogs = (logs) => {
        if (Array.isArray(logs)) {
          updateText('[data-live=\"logs-box\"]', logs.join("\\n"));
        }
      };

      const tick = async () => {
        if (document.visibilityState !== "visible") {
          return;
        }
        try {
          const response = await fetch(`${liveEndpoint}?tab=${activeTab}`, {
            headers: { "X-Requested-With": "fetch" },
            credentials: "same-origin",
            cache: "no-cache",
          });
          if (!response.ok) {
            if (response.status === 403) {
              notifyLiveAccessDenied();
            }
            return;
          }
          const payload = await response.json();
          if (activeTab === "music") {
            renderMusic(payload.music, payload.music_logs);
          } else if (activeTab === "overview") {
            renderOverview(payload);
          } else if (activeTab === "logs") {
            renderLogs(payload.logs);
          }
        } catch (_error) {
        }
      };
      const LIVE_POLL_INTERVAL_MS =
        activeTab === "music" ? 7000 :
        activeTab === "logs" ? 20000 :
        30000;
      let livePollingTimer = 0;
      const startLivePolling = () => {
        if (livePollingTimer) return;
        livePollingTimer = window.setInterval(() => {
          tick();
        }, LIVE_POLL_INTERVAL_MS);
      };

      const musicFeedback = document.querySelector('[data-live="music-feedback"]');
      const musicSearchResults = document.querySelector('[data-live="music-search-results"]');
      let lastSearchQuery = '';
      let lastSearchResults = [];
      let userPlaylists = [];
      let selectedUserPlaylistKey = '';
      let latestMusicState = null;

      const getUserPlaylistByKey = (key) => {
        const lookup = String(key || '').trim().toLowerCase();
        if (!lookup) {
          return null;
        }
        return userPlaylists.find((row) => {
          const slug = String(row.slug || '').trim().toLowerCase();
          const name = String(row.name || '').trim().toLowerCase();
          const id = String(row.id || '').trim().toLowerCase();
          return lookup === slug || lookup === name || lookup === id;
        }) || null;
      };

      const renderUserPlaylistItems = (playlist) => {
        const target = document.querySelector('[data-live="music-user-playlist-items"]');
        if (!target) {
          return;
        }
        if (!playlist || !Array.isArray(playlist.items) || !playlist.items.length) {
          target.innerHTML = '<div class="music-user-playlist-item">No playlist item.</div>';
          return;
        }
        const itemRows = playlist.items.map((item) => {
          const index = Number(item.index || 0);
          const kind = String(item.kind || 'query').trim().toLowerCase();
          const value = htmlEscape(String(item.value || ''));
          const kindLabel = kind === 'url' ? 'URL' : 'Query';
          const kindClass = kind === 'url' ? 'music-user-playlist-item-url' : '';
          return `
            <div class="music-user-playlist-item">
              <strong>#${index}</strong> <span class="${kindClass}">${kindLabel}</span><br>
              ${value}
            </div>
          `;
        }).join('');
        target.innerHTML = itemRows;
      };

      const renderUserPlaylists = (extra, preferredKey = '') => {
        if (!extra || !Array.isArray(extra.playlists)) {
          return;
        }
        userPlaylists = Array.from(extra.playlists);
        const select = document.getElementById('musicUserPlaylistSelect');
        const quotaLabel = document.querySelector('[data-live="music-user-playlist-quota"]');
        let selected = null;

        if (extra.selected_playlist) {
          const selectedPayload = extra.selected_playlist || {};
          const selectedLookup = String(
            selectedPayload.slug || selectedPayload.name || selectedPayload.id || '',
          ).trim();
          selected = getUserPlaylistByKey(selectedLookup);
          if (!selected) {
            selected = selectedPayload;
          }
        }
        if (!selected) {
          const lookup = String(preferredKey || '').trim();
          if (lookup) {
            selected = getUserPlaylistByKey(lookup);
          }
        }
        if (!selected && userPlaylists.length) {
          selected = userPlaylists[0];
        }
        selectedUserPlaylistKey = selected ? String(selected.slug || selected.name || '') : '';

        if (select) {
          const options = ['<option value="">Select playlist...</option>'].concat(
            userPlaylists.map((row) => {
              const slug = htmlEscape(String(row.slug || ''));
              const name = htmlEscape(String(row.name || row.slug || 'playlist'));
              const itemCount = Number(row.item_count || (Array.isArray(row.items) ? row.items.length : 0));
              const isSelected = selected && String(selected.slug || '') === String(row.slug || '');
              return `<option value="${slug}" ${isSelected ? 'selected' : ''}>${name} (${itemCount})</option>`;
            }),
          );
          select.innerHTML = options.join('');
        }

        if (quotaLabel) {
          const used = Number(extra.playlist_quota_used ?? userPlaylists.length);
          const maxQuota = Number(extra.playlist_quota_max ?? extra.max_playlists ?? 10);
          const remain = Number(extra.playlist_quota_remaining ?? Math.max(0, maxQuota - used));
          quotaLabel.textContent = `Playlist quota: ${used}/${maxQuota} (remaining ${remain})`;
        }

        renderUserPlaylistItems(selected);
      };

      const setMusicFeedback = (message, isError = false) => {
        const text = String(message || '').trim();
        if (musicFeedback) {
          musicFeedback.textContent = text;
          musicFeedback.classList.toggle('error', Boolean(isError));
        }
        if (!text) {
          return;
        }
        if (window.__dashboardFeedback && typeof window.__dashboardFeedback.notify === 'function') {
          window.__dashboardFeedback.notify(
            text,
            isError ? 'error' : 'success',
            { dedupeWindowMs: 900 }
          );
          return;
        }
        if (typeof window.showToast === 'function') {
          window.showToast(text, isError ? 'error' : 'success');
        }
      };

      const scrollToMusicSection = (selector) => {
        const node = document.querySelector(selector);
        if (!node) {
          return false;
        }
        node.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return true;
      };

      const renderSearchResults = (query, items) => {
        if (!musicSearchResults) {
          return;
        }
        if (!Array.isArray(items) || !items.length) {
          lastSearchResults = [];
          musicSearchResults.innerHTML = '';
          return;
        }
        lastSearchResults = Array.from(items);
        const rows = items.map((item) => {
          const title = htmlEscape(item.title || 'Unknown');
          const author = htmlEscape(item.author || 'Unknown');
          const duration = htmlEscape(item.duration || '0s');
          const idx = Number(item.index || 0);
          return `
            <article class="music-search-card">
              <div>
                <h4>#${idx} ${title}</h4>
                <p>${author} • ${duration}</p>
              </div>
              <button class="queue-remove-btn" type="button" data-add-result-index="${idx}">+</button>
            </article>
          `;
        }).join('');
        musicSearchResults.innerHTML = `
          <div class="mini-stat">ผลการค้นหา 10 เพลงแรก: <strong>${htmlEscape(query)}</strong></div>
          <div class="music-search-list">${rows}</div>
        `;
      };

      const postMusicAction = async (payload) => {
        const response = await fetch(musicControlEndpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'X-Requested-With': 'fetch',
          },
          credentials: 'same-origin',
          body: new URLSearchParams(payload),
        });
        const parsed = await response.json().catch(() => ({}));
        if (!response.ok) {
          const serverMessage = String(
            (parsed && (parsed.message || parsed.error)) || `HTTP ${response.status}`,
          ).trim();
          return {
            ok: false,
            message: serverMessage || `HTTP ${response.status}`,
            payload: (parsed && parsed.payload) || {},
            extra: (parsed && parsed.extra) || {},
          };
        }
        if (!parsed || typeof parsed !== 'object') {
          return { ok: false, message: 'รูปแบบข้อมูลตอบกลับไม่ถูกต้อง', payload: {}, extra: {} };
        }
        if (typeof parsed.ok !== 'boolean') {
          parsed.ok = true;
        }
        return parsed;
      };

      if (activeTab === 'music') {
        const setupToggle = document.getElementById('setupMusicModeToggle');
        const setupChannelsBlock = document.getElementById('musicSetupChannelsBlock');
        if (setupToggle && setupChannelsBlock) {
          const syncSetupVisibility = () => {
            setupChannelsBlock.style.display = setupToggle.checked ? 'grid' : 'none';
          };
          setupToggle.addEventListener('change', syncSetupVisibility);
          syncSetupVisibility();
        }

        const musicUsageRestrictToggle = document.getElementById('musicUsageRestrictToggle');
        const musicUsageRestrictionsBlock = document.getElementById('musicUsageRestrictionsBlock');
        if (musicUsageRestrictToggle && musicUsageRestrictionsBlock) {
          const syncMusicUsageRestrictions = () => {
            musicUsageRestrictionsBlock.style.display = musicUsageRestrictToggle.checked ? 'grid' : 'none';
          };
          musicUsageRestrictToggle.addEventListener('change', syncMusicUsageRestrictions);
          syncMusicUsageRestrictions();
        }

        document.querySelectorAll('[data-music-action-btn]').forEach((button) => {
          button.addEventListener('click', async () => {
            const action = button.dataset.action;
            if (!action) {
              return;
            }
            try {
              button.disabled = true;
              const result = await postMusicAction({ action });
              setMusicFeedback(result.message || '', !result.ok);
              await tick();
            } catch (_error) {
              setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
            } finally {
              button.disabled = false;
            }
          });
        });

        const addTrackForm = document.getElementById('musicQuickAddForm');
        if (addTrackForm) {
          addTrackForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const queryInput = document.getElementById('musicQueryInput');
            const query = queryInput ? queryInput.value.trim() : '';
            if (!query) {
              setMusicFeedback('กรุณาใส่ชื่อเพลงหรือ URL', true);
              return;
            }
            try {
              const result = await postMusicAction({ action: 'search_tracks', query });
              setMusicFeedback(result.message || '', !result.ok);
              const extra = result.extra || {};
              if (result.ok && Array.isArray(extra.search_results)) {
                lastSearchQuery = String(extra.search_query || query);
                renderSearchResults(lastSearchQuery, extra.search_results);
              } else if (!result.ok) {
                renderSearchResults('', []);
              }
            } catch (_error) {
              setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
            }
          });
        }

        const addPlaylistButton = document.getElementById('musicAddPlaylistBtn');
        if (addPlaylistButton) {
          addPlaylistButton.addEventListener('click', async () => {
            const select = document.getElementById('musicPlaylistSelect');
            const playlistKey = String(select ? (select.value || '') : '').trim();
            if (!playlistKey) {
              setMusicFeedback('กรุณาเลือกเพลย์ลิสต์ก่อน', true);
              return;
            }
            try {
              addPlaylistButton.disabled = true;
              const result = await postMusicAction({ action: 'add_playlist', query: playlistKey });
              setMusicFeedback(result.message || '', !result.ok);
              await tick();
            } catch (_error) {
              setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
            } finally {
              addPlaylistButton.disabled = false;
            }
          });
        }

        const userPlaylistSelect = document.getElementById('musicUserPlaylistSelect');
        const userPlaylistCreateButton = document.getElementById('musicUserPlaylistCreateBtn');
        const userPlaylistDeleteButton = document.getElementById('musicUserPlaylistDeleteBtn');
        const userPlaylistAddItemButton = document.getElementById('musicUserPlaylistAddItemBtn');
        const userPlaylistRefreshButton = document.getElementById('musicUserPlaylistRefreshBtn');
        const userPlaylistRemoveItemsButton = document.getElementById('musicUserPlaylistRemoveItemsBtn');
        const userPlaylistPlayAllButton = document.getElementById('musicUserPlaylistPlayAllBtn');
        const userPlaylistPlaySelectedButton = document.getElementById('musicUserPlaylistPlaySelectedBtn');

        const getSelectedUserPlaylistKey = () => {
          const fromSelect = String(userPlaylistSelect ? (userPlaylistSelect.value || '') : '').trim();
          if (fromSelect) {
            return fromSelect;
          }
          return String(selectedUserPlaylistKey || '').trim();
        };

        const syncUserPlaylists = async (preferredKey = '') => {
          const result = await postMusicAction({
            action: 'playlist_sync',
            playlist: preferredKey || getSelectedUserPlaylistKey(),
          });
          if (result.extra && Array.isArray(result.extra.playlists)) {
            renderUserPlaylists(result.extra, preferredKey || getSelectedUserPlaylistKey());
          }
          return result;
        };

        document.querySelectorAll('[data-music-ui-btn]').forEach((button) => {
          button.addEventListener('click', async () => {
            const uiAction = String(button.dataset.uiAction || '').trim();
            if (!uiAction) {
              return;
            }

            if (uiAction === 'open_queue') {
              if (!scrollToMusicSection('#musicQueueSection')) {
                setMusicFeedback('Queue section not found.', true);
              }
              return;
            }

            if (uiAction === 'open_user_playlists') {
              if (!scrollToMusicSection('#musicUserPlaylistsSection')) {
                setMusicFeedback('Playlist section not found.', true);
              }
              return;
            }

            if (uiAction === 'open_lyrics') {
              const title = String((latestMusicState && latestMusicState.title) || '').trim();
              const author = String((latestMusicState && latestMusicState.author) || '').trim();
              if (!title) {
                setMusicFeedback('No active track for lyrics.', true);
                return;
              }
              const lyricsQuery = `${title} ${author} lyrics`.trim();
              window.open(`https://www.youtube.com/results?search_query=${encodeURIComponent(lyricsQuery)}`, '_blank', 'noopener');
              return;
            }

            if (uiAction === 'save_current_track') {
              const playlist = getSelectedUserPlaylistKey();
              if (!playlist) {
                setMusicFeedback('Please choose playlist first.', true);
                return;
              }
              const title = String((latestMusicState && latestMusicState.title) || '').trim();
              const author = String((latestMusicState && latestMusicState.author) || '').trim();
              const uri = String((latestMusicState && latestMusicState.uri) || '').trim();
              const item = uri || [title, author].filter(Boolean).join(' ').trim();
              if (!item) {
                setMusicFeedback('No active track to save.', true);
                return;
              }
              try {
                button.disabled = true;
                const result = await postMusicAction({
                  action: 'playlist_add_item',
                  playlist,
                  item,
                });
                setMusicFeedback(result.message || '', !result.ok);
                if (result.extra && Array.isArray(result.extra.playlists)) {
                  renderUserPlaylists(result.extra, playlist);
                }
              } catch (_error) {
                setMusicFeedback('Cannot connect to server.', true);
              } finally {
                button.disabled = false;
              }
            }
          });
        });

        if (userPlaylistSelect) {
          userPlaylistSelect.addEventListener('change', () => {
            selectedUserPlaylistKey = String(userPlaylistSelect.value || '').trim();
            renderUserPlaylistItems(getUserPlaylistByKey(selectedUserPlaylistKey));
          });
        }

        if (userPlaylistCreateButton) {
          userPlaylistCreateButton.addEventListener('click', async () => {
            const nameInput = document.getElementById('musicUserPlaylistNameInput');
            const name = String(nameInput ? nameInput.value : '').trim();
            if (!name) {
              setMusicFeedback('Please enter playlist name.', true);
              return;
            }
            try {
              userPlaylistCreateButton.disabled = true;
              const result = await postMusicAction({ action: 'playlist_create', query: name });
              setMusicFeedback(result.message || '', !result.ok);
              if (result.extra && Array.isArray(result.extra.playlists)) {
                const selectedPayload = result.extra.selected_playlist || {};
                const preferred = String(
                  selectedPayload.slug || selectedPayload.name || selectedPayload.id || name,
                ).trim();
                renderUserPlaylists(result.extra, preferred);
              }
              if (result.ok && nameInput) {
                nameInput.value = '';
              }
            } catch (_error) {
              setMusicFeedback('Cannot connect to server.', true);
            } finally {
              userPlaylistCreateButton.disabled = false;
            }
          });
        }

        if (userPlaylistDeleteButton) {
          userPlaylistDeleteButton.addEventListener('click', async () => {
            const playlist = getSelectedUserPlaylistKey();
            if (!playlist) {
              setMusicFeedback('Please choose playlist.', true);
              return;
            }
            try {
              userPlaylistDeleteButton.disabled = true;
              const result = await postMusicAction({ action: 'playlist_delete', playlist });
              setMusicFeedback(result.message || '', !result.ok);
              if (result.extra && Array.isArray(result.extra.playlists)) {
                renderUserPlaylists(result.extra, '');
              }
            } catch (_error) {
              setMusicFeedback('Cannot connect to server.', true);
            } finally {
              userPlaylistDeleteButton.disabled = false;
            }
          });
        }

        if (userPlaylistAddItemButton) {
          userPlaylistAddItemButton.addEventListener('click', async () => {
            const playlist = getSelectedUserPlaylistKey();
            const itemInput = document.getElementById('musicUserPlaylistItemInput');
            const item = String(itemInput ? itemInput.value : '').trim();
            if (!playlist) {
              setMusicFeedback('Please choose playlist.', true);
              return;
            }
            if (!item) {
              setMusicFeedback('Please provide song name or URL.', true);
              return;
            }
            try {
              userPlaylistAddItemButton.disabled = true;
              const result = await postMusicAction({
                action: 'playlist_add_item',
                playlist,
                item,
              });
              setMusicFeedback(result.message || '', !result.ok);
              if (result.extra && Array.isArray(result.extra.playlists)) {
                renderUserPlaylists(result.extra, playlist);
              }
            } catch (_error) {
              setMusicFeedback('Cannot connect to server.', true);
            } finally {
              userPlaylistAddItemButton.disabled = false;
            }
          });
        }

        if (userPlaylistRefreshButton) {
          userPlaylistRefreshButton.addEventListener('click', async () => {
            try {
              userPlaylistRefreshButton.disabled = true;
              const result = await syncUserPlaylists(getSelectedUserPlaylistKey());
              setMusicFeedback(result.message || '', !result.ok);
            } catch (_error) {
              setMusicFeedback('Cannot connect to server.', true);
            } finally {
              userPlaylistRefreshButton.disabled = false;
            }
          });
        }

        if (userPlaylistRemoveItemsButton) {
          userPlaylistRemoveItemsButton.addEventListener('click', async () => {
            const playlist = getSelectedUserPlaylistKey();
            const pickInput = document.getElementById('musicUserPlaylistPickInput');
            const picks = String(pickInput ? pickInput.value : '').trim();
            if (!playlist) {
              setMusicFeedback('Please choose playlist.', true);
              return;
            }
            if (!picks) {
              setMusicFeedback('Please provide indexes.', true);
              return;
            }
            try {
              userPlaylistRemoveItemsButton.disabled = true;
              const result = await postMusicAction({
                action: 'playlist_remove_items',
                playlist,
                picks,
              });
              setMusicFeedback(result.message || '', !result.ok);
              if (result.extra && Array.isArray(result.extra.playlists)) {
                renderUserPlaylists(result.extra, playlist);
              }
            } catch (_error) {
              setMusicFeedback('Cannot connect to server.', true);
            } finally {
              userPlaylistRemoveItemsButton.disabled = false;
            }
          });
        }

        if (userPlaylistPlayAllButton) {
          userPlaylistPlayAllButton.addEventListener('click', async () => {
            const playlist = getSelectedUserPlaylistKey();
            if (!playlist) {
              setMusicFeedback('Please choose playlist.', true);
              return;
            }
            try {
              userPlaylistPlayAllButton.disabled = true;
              const result = await postMusicAction({
                action: 'playlist_play',
                playlist,
                mode: 'all',
              });
              setMusicFeedback(result.message || '', !result.ok);
              if (result.extra && Array.isArray(result.extra.playlists)) {
                renderUserPlaylists(result.extra, playlist);
              }
              await tick();
            } catch (_error) {
              setMusicFeedback('Cannot connect to server.', true);
            } finally {
              userPlaylistPlayAllButton.disabled = false;
            }
          });
        }

        if (userPlaylistPlaySelectedButton) {
          userPlaylistPlaySelectedButton.addEventListener('click', async () => {
            const playlist = getSelectedUserPlaylistKey();
            const pickInput = document.getElementById('musicUserPlaylistPickInput');
            const picks = String(pickInput ? pickInput.value : '').trim();
            if (!playlist) {
              setMusicFeedback('Please choose playlist.', true);
              return;
            }
            if (!picks) {
              setMusicFeedback('Please provide indexes to play.', true);
              return;
            }
            try {
              userPlaylistPlaySelectedButton.disabled = true;
              const result = await postMusicAction({
                action: 'playlist_play',
                playlist,
                mode: 'selected',
                picks,
              });
              setMusicFeedback(result.message || '', !result.ok);
              if (result.extra && Array.isArray(result.extra.playlists)) {
                renderUserPlaylists(result.extra, playlist);
              }
              await tick();
            } catch (_error) {
              setMusicFeedback('Cannot connect to server.', true);
            } finally {
              userPlaylistPlaySelectedButton.disabled = false;
            }
          });
        }

        (async () => {
          try {
            const initialPlaylistResult = await syncUserPlaylists();
            if (!initialPlaylistResult.ok) {
              setMusicFeedback(initialPlaylistResult.message || '', true);
            }
          } catch (_error) {
            setMusicFeedback('Cannot load playlists now.', true);
          }
        })();

        if (musicSearchResults) {
          musicSearchResults.addEventListener('click', async (event) => {
            const button = event.target.closest('[data-add-result-index]');
            if (!button) {
              return;
            }
            const index = String(button.dataset.addResultIndex || '').trim();
            if (!index || !lastSearchQuery) {
              return;
            }
            try {
              button.disabled = true;
              const result = await postMusicAction({
                action: 'add_track_at',
                query: lastSearchQuery,
                select_index: index,
              });
              setMusicFeedback(result.message || '', !result.ok);
              const extra = result.extra || {};
              if (result.ok && Array.isArray(extra.search_results)) {
                lastSearchQuery = String(extra.search_query || lastSearchQuery);
                renderSearchResults(lastSearchQuery, extra.search_results);
              } else if (result.ok) {
                const pickedIndex = Number(index);
                if (!Number.isNaN(pickedIndex) && pickedIndex > 0) {
                  const shifted = Array.from(lastSearchResults);
                  shifted.splice(pickedIndex - 1, 1);
                  shifted.forEach((item, idx) => {
                    item.index = idx + 1;
                  });
                  renderSearchResults(lastSearchQuery, shifted);
                }
              }
              await tick();
            } catch (_error) {
              setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
            } finally {
              button.disabled = false;
            }
          });
        }

        const seekApplyButton = document.getElementById('musicSeekApplyBtn');
        if (seekApplyButton) {
          seekApplyButton.addEventListener('click', async () => {
            const seekInput = document.getElementById('musicSeekInput');
            const seekMs = Number(seekInput ? seekInput.value : '0');
            if (Number.isNaN(seekMs)) {
              setMusicFeedback('เวลาไม่ถูกต้อง', true);
              return;
            }
            try {
              const result = await postMusicAction({ action: 'seek_to', seek_ms: String(Math.max(0, Math.floor(seekMs))) });
              setMusicFeedback(result.message || '', !result.ok);
              await tick();
            } catch (_error) {
              setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
            }
          });
        }

        const setVolumeButton = document.getElementById('musicSetVolumeBtn');
        if (setVolumeButton) {
          setVolumeButton.addEventListener('click', async () => {
            const volumeInput = document.getElementById('musicVolumeInput');
            const volume = Number(volumeInput ? volumeInput.value : '0');
            if (Number.isNaN(volume)) {
              setMusicFeedback('ระดับเสียงไม่ถูกต้อง', true);
              return;
            }
            try {
              const result = await postMusicAction({ action: 'set_volume', volume: String(volume) });
              setMusicFeedback(result.message || '', !result.ok);
              await tick();
            } catch (_error) {
              setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
            }
          });
        }

        const queueCards = document.querySelector('[data-live="music-queue-cards"]');
        if (queueCards) {
          queueCards.addEventListener('click', async (event) => {
            const playNowButton = event.target.closest('.queue-playnow-btn');
            if (playNowButton) {
              const queueIndex = playNowButton.dataset.queueIndex;
              if (!queueIndex) {
                return;
              }
              try {
                playNowButton.disabled = true;
                const result = await postMusicAction({ action: 'play_queue_now', queue_index: queueIndex });
                setMusicFeedback(result.message || '', !result.ok);
                await tick();
              } catch (_error) {
                setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
              } finally {
                playNowButton.disabled = false;
              }
              return;
            }

            const moveButton = event.target.closest('.queue-move-btn');
            if (moveButton) {
              const queueIndex = moveButton.dataset.queueIndex;
              const direction = String(moveButton.dataset.moveDirection || '').trim().toLowerCase();
              if (!queueIndex || !direction) {
                return;
              }
              const action = direction === 'up' ? 'move_queue_up' : direction === 'down' ? 'move_queue_down' : '';
              if (!action) {
                return;
              }
              try {
                moveButton.disabled = true;
                const result = await postMusicAction({ action, queue_index: queueIndex });
                setMusicFeedback(result.message || '', !result.ok);
                await tick();
              } catch (_error) {
                setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
              } finally {
                moveButton.disabled = false;
              }
              return;
            }

            const button = event.target.closest('.queue-remove-btn');
            if (!button || button.hasAttribute('data-add-result-index')) {
              return;
            }
            const queueIndex = button.dataset.queueIndex;
            if (!queueIndex) {
              return;
            }
            try {
              button.disabled = true;
              const result = await postMusicAction({ action: 'delete_queue', queue_index: queueIndex });
              setMusicFeedback(result.message || '', !result.ok);
              await tick();
            } catch (_error) {
              setMusicFeedback('เชื่อมต่อเซิร์ฟเวอร์ไม่สำเร็จ', true);
            } finally {
              button.disabled = false;
            }
          });
        }
      }
      runWhenIdle(() => tick(), activeTab === "music" ? 1000 : 2200);
      runWhenIdle(() => startLivePolling(), 2600);
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          tick();
        }
      });
    })();
