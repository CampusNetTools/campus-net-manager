(() => {
  const statusBadge = document.getElementById("browser-status");
  const statusText = document.getElementById("browser-status-text");
  const statusHeading = document.getElementById("status-heading");
  const statusDetail = document.getElementById("status-detail");
  const statusDot = document.getElementById("status-dot");
  const refreshButton = document.getElementById("refresh-status");
  const checklistStatus = document.getElementById("checklist-status");

  function updateBrowserStatus() {
    const online = navigator.onLine;
    const label = online ? "浏览器报告在线" : "浏览器报告离线";
    statusBadge.classList.toggle("is-online", online);
    statusBadge.classList.toggle("is-offline", !online);
    statusText.textContent = label;
    statusHeading.textContent = label;
    statusDot.classList.toggle("is-online", online);
    statusDot.classList.toggle("is-offline", !online);
    statusDetail.textContent = `最近读取：${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }

  refreshButton.addEventListener("click", updateBrowserStatus);
  window.addEventListener("online", updateBrowserStatus);
  window.addEventListener("offline", updateBrowserStatus);
  updateBrowserStatus();

  const tabs = [...document.querySelectorAll("[data-device]")];
  const panels = [...document.querySelectorAll("[data-panel]")];

  function selectDevice(device, focusTab = false) {
    tabs.forEach((tab) => {
      const selected = tab.dataset.device === device;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focusTab) tab.focus();
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== device;
    });
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectDevice(tab.dataset.device));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const next = (index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
      selectDevice(tabs[next].dataset.device, true);
    });
  });

  const checks = [...document.querySelectorAll("[data-check]")];
  const storageKey = "cnm-pwa-reading-checklist-v1";

  function readChecklist() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      checks.forEach((check) => {
        check.checked = saved[check.dataset.check] === true;
      });
    } catch {
      checks.forEach((check) => { check.checked = false; });
    }
  }

  function saveChecklist() {
    const saved = Object.fromEntries(checks.map((check) => [check.dataset.check, check.checked]));
    try {
      localStorage.setItem(storageKey, JSON.stringify(saved));
      const complete = checks.filter((check) => check.checked).length;
      checklistStatus.textContent = `已完成 ${complete}/${checks.length} 项；只保存在此设备浏览器。`;
    } catch {
      checklistStatus.textContent = "浏览器未允许本地存储；本次清单不会保存。";
    }
  }

  readChecklist();
  saveChecklist();
  checks.forEach((check) => check.addEventListener("change", saveChecklist));

  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js", { scope: "./" }).catch(() => {
        // The page stays usable when offline caching is unavailable.
      });
    });
  }
})();
