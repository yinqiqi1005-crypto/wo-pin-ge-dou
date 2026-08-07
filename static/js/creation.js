document.addEventListener("DOMContentLoaded", () => {
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
