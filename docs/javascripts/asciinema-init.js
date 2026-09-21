/**
 * Asciinema Web Player initialization for Protostar documentation.
 * Supports instant navigation in MkDocs Material / Zensical with scroll-triggered autoplay.
 */
function initAsciinemaPlayers() {
  if (typeof AsciinemaPlayer === "undefined" || !AsciinemaPlayer.create) {
    return;
  }

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll("[data-asciinema]").forEach(function (el) {
    if (el.dataset.initialized) {
      return;
    }
    el.dataset.initialized = "true";

    var src = el.getAttribute("data-asciinema");
    if (!src) return;

    // Warm the HTTP cache so playback starts without delay once scrolled into view
    fetch(src).catch(function () {});

    var player = AsciinemaPlayer.create(src, el, {
      autoPlay: false,
      preload: true,
      poster: "npt:0:00.1",
      loop: !reduceMotion,
      speed: 1,
      terminalFontFamily: "'JetBrains Mono', 'Symbols Nerd Font', 'Fira Code', monospace",
      terminalFontSize: "14px",
      fit: "width",
      controls: "auto",
    });

    if (!reduceMotion) {
      if ("IntersectionObserver" in window) {
        var observer = new IntersectionObserver(
          function (entries, obs) {
            entries.forEach(function (entry) {
              if (entry.isIntersecting) {
                obs.unobserve(entry.target);
                player.play();
              }
            });
          },
          {
            threshold: 0.2,
            rootMargin: "0px 0px -10% 0px",
          }
        );
        observer.observe(el);
      } else {
        player.play();
      }
    }
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
