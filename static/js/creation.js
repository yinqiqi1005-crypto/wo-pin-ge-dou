document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-drop-upload]");
  if (!form) return;
  const input = form.querySelector("input[type=file]");
  const status = form.querySelector(".selected-file");
  const showSelection = () => {
    status.textContent = input.files.length ? `已选择：${input.files[0].name}` : "尚未选择图片";
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
