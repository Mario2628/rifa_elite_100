(function () {
  function closeNav(btn, nav) {
    btn.setAttribute("aria-expanded", "false");
    nav.classList.remove("nav--open");
  }

  function openNav(btn, nav) {
    btn.setAttribute("aria-expanded", "true");
    nav.classList.add("nav--open");
  }

  function toggleNav(btn, nav) {
    const expanded = btn.getAttribute("aria-expanded") === "true";
    if (expanded) closeNav(btn, nav);
    else openNav(btn, nav);
  }

  function initOne(toggleSelector, navId) {
    const btn = document.querySelector(toggleSelector);
    const nav = document.getElementById(navId);
    if (!btn || !nav) return;

    btn.addEventListener("click", function (e) {
      e.preventDefault();
      toggleNav(btn, nav);
    });

    // Cierra al click en cualquier link del menú (móvil)
    nav.addEventListener("click", function (e) {
      const target = e.target;
      if (target && target.tagName === "A") {
        closeNav(btn, nav);
      }
    });

    // Cierra con ESC
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeNav(btn, nav);
    });

    // Cierra al click afuera
    document.addEventListener("click", function (e) {
      const isBtn = btn.contains(e.target);
      const isNav = nav.contains(e.target);
      if (!isBtn && !isNav) closeNav(btn, nav);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initOne("#siteNavToggle", "siteNav");
    initOne("#adminNavToggle", "adminNav");
  });
})();