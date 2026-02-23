(function () {
  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function setDisabled(btn, preview) {
    btn.classList.add("btn--disabled");
    btn.setAttribute("aria-disabled", "true");
    btn.setAttribute("href", "#");
    preview.textContent = "—";
  }

  function initAdminPick() {
    const btn = document.getElementById("registerBtn");
    const preview = document.getElementById("selectedPreview");
    if (!btn || !preview) return; // solo corre en Admin->Boletos

    setDisabled(btn, preview);

    // tickets.js llama esta función si existe (y NO es inline, así que CSP no lo bloquea)
    window.__onTicketSelectionChange = function (selected) {
      if (!selected || selected.length === 0) {
        setDisabled(btn, preview);
        return;
      }

      preview.textContent = selected.map(pad2).join(", ");

      const qs = encodeURIComponent(selected.join(","));
      btn.setAttribute("href", `/admin/manual-purchase?prefill=${qs}`);
      btn.classList.remove("btn--disabled");
      btn.removeAttribute("aria-disabled");
    };
  }

  document.addEventListener("DOMContentLoaded", initAdminPick);
})();