/**
 * Plays the terminal recordings in the docs: each `.hs-terminal-screen` with
 * a `data-asciinema` recording (see docs/house/css/terminal.css).
 *
 * Every page loads this module, so it fetches nothing until a recording comes
 * near the viewport. Only then does it load asciinema-player and the
 * recording, and it plays once most of the recording is on screen.
 */
import {
  loadSymbolsFont,
  mountCast,
  prefersReducedMotion,
  whenVisible,
} from "../house/js/cast.js";

// The version jacksonferguson.me bundles, so the house player skin fits it.
const PLAYER = "https://cdn.jsdelivr.net/npm/asciinema-player@3.17.0/dist/bundle/";
let player;

// The player's files go in <body>: instant navigation drops any <head>
// element the next page doesn't declare, and the player needs its stylesheet
// on every page it plays on.
function loadPlayer() {
  player ??= new Promise((resolve, reject) => {
    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = `${PLAYER}asciinema-player.css`;
    document.body.append(style);

    const script = document.createElement("script");
    script.src = `${PLAYER}asciinema-player.min.js`;
    script.onload = () => resolve(window.AsciinemaPlayer);
    script.onerror = () => {
      player = undefined;
      reject(new Error("The terminal player failed to load"));
    };
    document.body.append(script);
  });
  return player;
}

function mount(screen) {
  loadPlayer()
    .then((AsciinemaPlayer) => {
      if (!screen.isConnected) return;
      const recording = mountCast(AsciinemaPlayer.create, screen);
      if (!recording) return;
      screen.classList.add("is-loaded");
      if (prefersReducedMotion()) return;
      whenVisible(screen, () => loadSymbolsFont().then(() => recording.play()), {
        threshold: 0.5,
      });
    })
    .catch(() => {
      delete screen.dataset.castWaiting;
    });
}

function init() {
  const screens = document.querySelectorAll(
    ".hs-terminal-screen[data-asciinema]:not([data-cast-waiting])",
  );
  for (const screen of screens) {
    screen.dataset.castWaiting = "true";
    whenVisible(screen, () => mount(screen), { rootMargin: "0px 0px 25% 0px" });
  }
}

// Instant navigation swaps the page without loading this module again.
if (typeof document$ !== "undefined") {
  document$.subscribe(init);
} else {
  init();
}
