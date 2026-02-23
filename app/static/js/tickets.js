(function () {
  async function fetchTickets(apiUrl) {
    const res = await fetch(apiUrl, { credentials: "same-origin" });
    if (!res.ok) throw new Error("No se pudo cargar el tablero");
    return await res.json();
  }

  function statusToClass(status) {
    if (status === "FREE") return "ticket--free";
    if (status === "RESERVED") return "ticket--res";
    return "ticket--paid";
  }

  function renderGrid(container, data, opts) {
    container.innerHTML = "";

    const selectable = opts.selectable;
    const max = opts.max;
    const selected = new Set();

    data.tickets.forEach(t => {
      const div = document.createElement("div");
      div.className = `ticket ${statusToClass(t.s)}`;
      div.textContent = String(t.n).padStart(2, "0");

      if (selectable) {
        if (t.s !== "FREE") {
          div.style.cursor = "not-allowed";
        } else {
          div.addEventListener("click", () => {
            const key = t.n;

            if (selected.has(key)) {
              selected.delete(key);
              div.classList.remove("ticket--selected");
            } else {
              if (selected.size >= max) return;
              selected.add(key);
              div.classList.add("ticket--selected");
            }

            if (typeof window.__onTicketSelectionChange === "function") {
              window.__onTicketSelectionChange(Array.from(selected).sort((a, b) => a - b));
            }
          });
        }
      } else {
        div.style.cursor = "default";
      }

      container.appendChild(div);
    });
  }

  async function init() {
    const grids = [
      document.getElementById("ticketsGrid"),
      document.getElementById("ticketsGridSelect"),
      document.getElementById("ticketsGridHome"),
      document.getElementById("ticketsGridAdminPick"),
    ].filter(Boolean);

    for (const grid of grids) {
      const api = grid.getAttribute("data-api");
      const selectable = grid.getAttribute("data-select") === "1";
      const max = parseInt(grid.getAttribute("data-max") || "3", 10);

      try {
        const data = await fetchTickets(api);
        renderGrid(grid, data, { selectable, max });

        // refrescar solo grids NO seleccionables (para no borrar selección admin)
        if (!selectable) {
          setInterval(async () => {
            try {
              const fresh = await fetchTickets(api);
              renderGrid(grid, fresh, { selectable, max });
            } catch (_) {}
          }, 10000);
        }
      } catch (e) {
        grid.innerHTML = `<div class="muted">No se pudo cargar el tablero.</div>`;
      }
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();