document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-theme-picker]").forEach((picker) => {
    const toggle = picker.querySelector(".theme-toggle");
    const menu = picker.querySelector(".theme-menu");
    const setOpen = (open) => {
      toggle.setAttribute("aria-expanded", String(open));
      menu.hidden = !open;
    };
    toggle.addEventListener("click", () => setOpen(menu.hidden));
    picker.querySelectorAll("[data-theme-choice]").forEach((choice) => {
      choice.addEventListener("click", () => {
        const theme = choice.dataset.themeChoice;
        document.documentElement.dataset.theme = theme;
        try { localStorage.setItem("wpgd-theme", theme); } catch (error) { /* Keep the theme for this page. */ }
        setOpen(false);
      });
    });
    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) setOpen(false);
    });
    picker.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        setOpen(false);
        toggle.focus();
      }
    });
  });
  document.querySelectorAll("[data-account-menu]").forEach((menuWrap) => {
    const trigger = menuWrap.querySelector(".account-trigger");
    const menu = menuWrap.querySelector(".account-menu");
    const setOpen = (open) => {
      trigger.setAttribute("aria-expanded", String(open));
      menu.hidden = !open;
    };
    trigger.addEventListener("click", () => setOpen(menu.hidden));
    document.addEventListener("click", (event) => {
      if (!menuWrap.contains(event.target)) setOpen(false);
    });
    menuWrap.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.focus();
      }
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
  document.querySelectorAll("[data-ironing-card]").forEach((card) => {
    const input = card.querySelector("input[type=radio]");
    if (!input) return;
    const syncSelection = () => {
      document.querySelectorAll("[data-ironing-card]").forEach((candidate) => {
        candidate.classList.toggle("is-selected", candidate.querySelector("input")?.checked);
      });
    };
    input.addEventListener("change", syncSelection);
    syncSelection();
  });
  document.querySelectorAll("[data-inline-rename]").forEach((form) => {
    const card = form.closest("[data-pattern-card]");
    const open = card.querySelector("[data-open-rename]");
    const cancel = form.querySelector("[data-cancel-rename]");
    const title = card.querySelector("[data-pattern-title]");
    const setEditing = (editing) => {
      form.hidden = !editing;
      open.hidden = editing;
      if (editing) form.querySelector("input[name=title]").focus();
    };
    open.addEventListener("click", () => setEditing(true));
    cancel.addEventListener("click", () => setEditing(false));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const response = await fetch(form.action, { method: "POST", body: new FormData(form), headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!response.ok) return;
      const payload = await response.json();
      title.textContent = payload.title;
      form.querySelector("input[name=title]").value = payload.title;
      setEditing(false);
    });
  });
  document.querySelectorAll("[data-pattern-delete], [data-pattern-restore]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      const deleting = form.matches("[data-pattern-delete]");
      if (deleting && !window.confirm("移入回收站？你可以随时恢复这张图纸。")) return;
      event.preventDefault();
      const response = await fetch(form.action, { method: "POST", body: new FormData(form), headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!response.ok) return;
      const card = form.closest("[data-pattern-card]");
      if (deleting) card.remove();
      else window.location.assign("/patterns/");
    });
  });
  document.querySelectorAll("[data-model-rotate]").forEach((button) => {
    const model = button.closest(".report-model-chip").querySelector("[data-bead-model]");
    let angle = 0;
    button.addEventListener("click", () => {
      angle += 90;
      model.style.setProperty("--model-rotation", `${angle}deg`);
    });
  });
  const modal = document.querySelector("[data-save-pattern-modal]");
  const openModal = document.querySelector("[data-open-save-modal]");
  if (modal && openModal) {
    const form = modal.querySelector("[data-ajax-save]");
    const errorMessage = form.querySelector("[data-save-errors]");
    const feedback = document.querySelector("[data-save-feedback]");
    const focusableSelector = "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary";
    const closeModal = () => { modal.hidden = true; openModal.focus(); };
    openModal.addEventListener("click", () => {
      modal.hidden = false;
      modal.querySelector("[name=title]").focus();
    });
    modal.querySelector("[data-close-save-modal]").addEventListener("click", closeModal);
    modal.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeModal();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(modal.querySelectorAll(focusableSelector));
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      errorMessage.textContent = "";
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        const payload = await response.json();
        if (!response.ok || !payload.saved) {
          const errors = Object.values(payload.errors || {}).flat();
          errorMessage.textContent = errors[0]?.message || "保存失败，请检查名称和分类后重试。";
          return;
        }
        closeModal();
        openModal.textContent = "已保存";
        openModal.disabled = true;
        feedback.hidden = false;
        feedback.innerHTML = `图纸已保存。<a href="${payload.detail_url}">查看我的图纸</a>`;
      } catch (error) {
        errorMessage.textContent = "网络暂时不可用，请重试。";
      }
    });
  }
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
