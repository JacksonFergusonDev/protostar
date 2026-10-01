/**
 * Helpers for terminal recordings in an `.hs-terminal-screen` (see
 * css/terminal.css). They take asciinema-player's `create` function rather
 * than importing it, so a site can bundle the player or load it on demand.
 */

/** @returns {boolean} Whether the reader asked for reduced motion. */
export function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * The player options every house recording uses. A recording loops unless
 * the reader asked for reduced motion, and never starts on its own: the page
 * decides when to call `play()`.
 *
 * @param {{ reduceMotion?: boolean }} [settings]
 */
export function castOptions({ reduceMotion = prefersReducedMotion() } = {}) {
  return {
    autoPlay: false,
    preload: true,
    poster: 'npt:0:00.1',
    loop: !reduceMotion,
    speed: 1,
    terminalFontFamily: "'JetBrains Mono', 'Symbols Nerd Font', 'Fira Code', monospace",
    terminalFontSize: '14px',
    fit: 'width',
    controls: 'auto',
  };
}

let symbols;

/**
 * Loads the Nerd Font symbols the recordings draw with, once per page.
 * Play a recording after this settles so its icons don't pop in.
 *
 * @returns {Promise<FontFace[]>}
 */
export function loadSymbolsFont() {
  symbols ??= document.fonts.load("14px 'Symbols Nerd Font'").catch(() => []);
  return symbols;
}

/**
 * Creates the player for an element's `data-asciinema` recording, once.
 *
 * @param {Function} create asciinema-player's `create`.
 * @param {HTMLElement} element The screen holding `data-asciinema`.
 * @param {object} [options] Player options that override `castOptions()`.
 * @returns The player, or undefined if the element has none to mount.
 */
export function mountCast(create, element, options = {}) {
  const src = element.dataset.asciinema;
  if (!src || element.dataset.castMounted) return undefined;
  element.dataset.castMounted = 'true';
  return create(src, element, { ...castOptions(), ...options });
}

/**
 * Calls `callback` once, the first time `element` intersects the viewport
 * grown by `rootMargin`. Without IntersectionObserver it calls it at once.
 *
 * @param {Element} element
 * @param {() => void} callback
 * @param {IntersectionObserverInit} [options]
 * @returns {() => void} Stops waiting.
 */
export function whenVisible(element, callback, options = {}) {
  if (!('IntersectionObserver' in window)) {
    callback();
    return () => {};
  }
  const observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      observer.disconnect();
      callback();
    }
  }, options);
  observer.observe(element);
  return () => observer.disconnect();
}
