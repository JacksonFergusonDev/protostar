/**
 * Asciinema Web Player initialization for Protostar documentation.
 * Supports instant navigation in MkDocs Material / Zensical.
 */
function initAsciinemaPlayers() {
  if (typeof AsciinemaPlayer === "undefined" || !AsciinemaPlayer.create) {
    return;
  }

  document.querySelectorAll("[data-asciinema]").forEach(function (el) {
    if (el.dataset.initialized) {
      return;
    }
    el.dataset.initialized = "true";

    var src = el.getAttribute("data-asciinema");
    AsciinemaPlayer.create(src, el, {
      autoPlay: true,
      loop: true,
      speed: 1,
      terminalFontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      terminalFontSize: "14px",
      fit: "width",
    });
  });
}

// Support both instant navigation in MkDocs/Zensical and standard DOM loading
if (typeof document$ !== "undefined") {
  document$.subscribe(function () {
    initAsciinemaPlayers();
  });
} else {
  document.addEventListener("DOMContentLoaded", initAsciinemaPlayers);
}
