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

    // Wrap in terminal shell frame if not already wrapped
    if (!el.closest(".protostar-demo-shell")) {
      var shell = document.createElement("div");
      shell.className = "protostar-demo-shell";

      var panelTop = document.createElement("div");
      panelTop.className = "panel-top";

      var dots = document.createElement("span");
      dots.className = "terminal-dots";
      dots.setAttribute("aria-hidden", "true");
      dots.innerHTML = '<span class="dot dot-close"></span><span class="dot dot-minimize"></span><span class="dot dot-maximize"></span>';

      var title = document.createElement("span");
      title.className = "terminal-title";
      var customTitle = el.getAttribute("data-title");
      if (customTitle) {
        title.textContent = customTitle;
      } else if (src.indexOf("wizard") !== -1) {
        title.textContent = "PROTOSTAR / INTERACTIVE WIZARD";
      } else if (src.indexOf("headless") !== -1) {
        title.textContent = "PROTOSTAR / HEADLESS DEMO";
      } else {
        title.textContent = "PROTOSTAR / TERMINAL";
      }

      panelTop.appendChild(dots);
      panelTop.appendChild(title);

      el.parentNode.insertBefore(shell, el);
      shell.appendChild(panelTop);
      shell.appendChild(el);
    }

    // Warm the HTTP cache so playback starts without delay once scrolled into view
    fetch(src).catch(function () {});

    // Pre-warm the symbols font in the background so glyphs render without pop-in
    if (document.fonts) {
      document.fonts.load("14px 'Symbols Nerd Font'").catch(function () {});
    }

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
