(() => {
  const list = document.getElementById("trustedOrderList");
  const input = document.getElementById("trustedOrderInput");
  if (!list || !input) {
    return;
  }

  let dragged = null;

  const updateHidden = () => {
    const names = Array.from(list.querySelectorAll(".trusted-manager-item"))
      .map((item) => item.dataset.name || "")
      .filter(Boolean);
    input.value = names.join(", ");
  };

  list.querySelectorAll(".trusted-manager-item").forEach((item) => {
    item.addEventListener("dragstart", () => {
      dragged = item;
      item.style.opacity = "0.55";
    });

    item.addEventListener("dragend", () => {
      item.style.opacity = "1";
      dragged = null;
      updateHidden();
    });

    item.addEventListener("dragover", (event) => {
      event.preventDefault();
    });

    item.addEventListener("drop", (event) => {
      event.preventDefault();
      if (!dragged || dragged === item) {
        return;
      }
      const rect = item.getBoundingClientRect();
      const after = event.clientY - rect.top > rect.height / 2;
      if (after) {
        item.after(dragged);
      } else {
        item.before(dragged);
      }
      updateHidden();
    });
  });

  updateHidden();
})();
