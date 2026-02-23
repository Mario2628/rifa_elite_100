(function () {
  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function initLandingBg() {
    const landing = document.querySelector("[data-landing-bg]");
    if (!landing) return;

    const bg = landing.getAttribute("data-landing-bg");
    if (!bg) return;

    landing.style.backgroundImage = `url("${bg}")`;

    // ✅ Banner completo y GRANDE (sin recorte)
    // Altura: 78vh (o 720px máx) para que se vea "como flyer"
    landing.style.backgroundRepeat = "no-repeat";
    landing.style.backgroundPosition = "center";
    landing.style.backgroundSize = "auto min(78vh, 720px)";
  }

  function initProgressBars() {
    const bars = document.querySelectorAll("[data-progress]");
    bars.forEach((bar) => {
      const pctStr = bar.getAttribute("data-progress") || "0";
      const pct = clamp(parseFloat(pctStr), 0, 100);
      bar.style.width = pct + "%";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initLandingBg();
    initProgressBars();
  });
})();