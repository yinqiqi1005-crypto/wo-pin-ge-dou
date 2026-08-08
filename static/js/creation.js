document.addEventListener("DOMContentLoaded", () => {
  const themeChoices = document.querySelectorAll("[data-theme-choice]");
  themeChoices.forEach((choice) => {
    choice.addEventListener("click", () => {
      const theme = choice.dataset.themeChoice;
      document.documentElement.dataset.theme = theme;
      try { localStorage.setItem("wpgd-theme", theme); } catch (error) { /* Keep the theme for this page. */ }
      const picker = choice.closest("details");
      if (picker) picker.removeAttribute("open");
    });
  });
  document.querySelectorAll("[data-submit-state]").forEach((statefulForm) => {
    statefulForm.addEventListener("submit", () => {
      statefulForm.setAttribute("aria-busy", "true");
      const submitButton = statefulForm.querySelector("button[type=submit], button:not([type])");
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = submitButton.dataset.submittingLabel || "正在处理……";
      }
    });
  });
  document.querySelectorAll("[data-result-tabs]").forEach((tabList) => {
    const tabs = Array.from(tabList.querySelectorAll("[data-tab-target]"));
    const panels = tabs.map((tab) => document.getElementById(tab.dataset.tabTarget));
    if (!tabs.length || panels.some((panel) => !panel)) return;

    tabList.setAttribute("role", "tablist");
    const selectTab = (selectedTab, moveFocus = false) => {
      tabs.forEach((tab, index) => {
        const selected = tab === selectedTab;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-controls", panels[index].id);
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        panels[index].setAttribute("role", "tabpanel");
        panels[index].setAttribute("aria-labelledby", tab.id);
        panels[index].hidden = !selected;
      });
      if (moveFocus) selectedTab.focus();
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectTab(tab));
      tab.addEventListener("keydown", (event) => {
        const keyTargets = {
          ArrowRight: tabs[(index + 1) % tabs.length],
          ArrowLeft: tabs[(index - 1 + tabs.length) % tabs.length],
          Home: tabs[0],
          End: tabs[tabs.length - 1],
        };
        const target = keyTargets[event.key];
        if (!target) return;
        event.preventDefault();
        selectTab(target, true);
      });
    });
    selectTab(tabs[0]);
  });
  const form = document.querySelector("[data-drop-upload]");
  if (!form) return;
  const input = form.querySelector("input[type=file]");
  const status = form.querySelector(".selected-file");
  const preview = form.querySelector("[data-upload-preview]");
  let previewUrl = null;
  const showSelection = () => {
    status.textContent = input.files.length ? `已选择：${input.files[0].name}` : "尚未选择图片";
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (input.files.length) {
      previewUrl = URL.createObjectURL(input.files[0]);
      preview.src = previewUrl;
      preview.hidden = false;
    } else {
      preview.removeAttribute("src");
      preview.hidden = true;
    }
  };
  input.addEventListener("change", showSelection);
  ["dragenter", "dragover"].forEach((eventName) => {
    form.addEventListener(eventName, (event) => {
      event.preventDefault();
      form.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    form.addEventListener(eventName, (event) => {
      event.preventDefault();
      form.classList.remove("dragging");
    });
  });
  form.addEventListener("drop", (event) => {
    if (!event.dataTransfer.files.length) return;
    input.files = event.dataTransfer.files;
    showSelection();
  });
});
