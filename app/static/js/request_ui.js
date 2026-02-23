(function () {
  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function qs(id) {
    return document.getElementById(id);
  }

  function setSubmitState(btn, enabled) {
    if (!btn) return;
    btn.disabled = !enabled;
    if (enabled) {
      btn.classList.remove("btn--disabled");
    } else {
      btn.classList.add("btn--disabled");
    }
  }

  function initRequestUI() {
    const hidden = qs("ticket_numbers");
    const preview = qs("selectedPreview");
    const count = qs("selectedCount");
    const submitBtn = qs("submitRequestBtn");

    if (!hidden || !preview || !submitBtn) return;

    // Estado inicial
    hidden.value = "";
    preview.textContent = "—";
    if (count) count.textContent = "0";
    setSubmitState(submitBtn, false);

    // tickets.js invoca esto cuando seleccionas boletos (solo si existe)
    window.__onTicketSelectionChange = function (selected) {
      if (!selected || selected.length === 0) {
        hidden.value = "";
        preview.textContent = "—";
        if (count) count.textContent = "0";
        setSubmitState(submitBtn, false);
        return;
      }

      hidden.value = selected.join(",");
      preview.textContent = selected.map(pad2).join(", ");
      if (count) count.textContent = String(selected.length);
      setSubmitState(submitBtn, true);
    };

    // Si alguien intenta enviar sin selección (por ejemplo, JS no cargó)
    const form = submitBtn.closest("form");
    if (form) {
      form.addEventListener("submit", function (e) {
        if (!hidden.value) {
          e.preventDefault();
          preview.textContent = "Selecciona al menos 1 boleto.";
          preview.style.color = "rgba(239,68,68,.95)";
          setTimeout(() => {
            preview.style.color = "";
            preview.textContent = "—";
          }, 2500);
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", initRequestUI);
})();