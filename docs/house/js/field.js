/**
 * Runs a hero's moving background: everything about it but the drawing.
 *
 * A site draws its own field on the `.hs-field` canvas, with WebGL or a 2D
 * context, and hands its drawing to `runField`, which follows GUIDELINES.md's
 * motion rules: still for reduced motion, paused off screen or in a hidden
 * tab, and stoppable with its pause button (css/site.css, `.hs-motion`). Start
 * it with `afterLoad`, so the first screen paints as text:
 *
 *   afterLoad(() => {
 *     const gl = canvas.getContext('webgl2');
 *     if (gl) runField(canvas, button, myScene(gl));
 *   });
 *
 * The canvas's CSS sets the drawing's style: `--hs-field-color` (default the
 * accent), `--hs-field-strength` (0.36), and `--hs-field-blend` (`add` on dark
 * pages, `normal` on light ones). Call `refresh()` after changing them.
 *
 * A WebGL canvas can lose its context when the GPU resets or a phone reclaims
 * memory. `runField` asks the browser to restore it, draws nothing while it's
 * gone, and calls the scene's `restore()` to rebuild its shaders and buffers
 * before drawing again.
 */

// The button's visible text is its whole accessible name (WCAG 2.5.3), and it
// says what a press does; `data-hs-paused` picks the icon.
const LABELS = { pause: 'Pause motion', play: 'Play motion' };

// The longest step a frame takes, so a stalled tab doesn't jump on return.
const MAX_DELTA = 0.08;

// The longest `afterLoad` waits for an idle moment. Chromium can leave an idle
// callback unrun on a page that draws no new frames, so the field never started.
const IDLE_TIMEOUT = 1000;

/**
 * Calls `start` once the page has loaded and the browser is idle, or a second
 * after load at the latest.
 *
 * @param {() => void} start
 */
export function afterLoad(start) {
  const idle = () =>
    window.requestIdleCallback
      ? window.requestIdleCallback(start, { timeout: IDLE_TIMEOUT })
      : window.setTimeout(start, 200);
  if (document.readyState === 'complete') idle();
  else window.addEventListener('load', idle, { once: true });
}

/**
 * Runs `scene` on `canvas`, with `button` as its pause control.
 *
 * The scene draws; `runField` decides when. `draw(time, delta)` gets the
 * seconds the field has moved and those since the last frame, which is 0 when
 * it only redraws a still frame (paused, resized, or restyled). `restore()`
 * runs when a lost WebGL context comes back, before the next frame.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {HTMLButtonElement} button
 * @param {{
 *   style?(style: { color: [number, number, number], strength: number, blend: 'add' | 'normal' }): void,
 *   resize?(width: number, height: number): void,
 *   draw(time: number, delta: number): void,
 *   restore?(): void,
 *   dispose?(): void,
 * }} scene
 * @returns {{ refresh(): void, dispose(): void } | undefined} Controls, or
 *   nothing when the canvas has left the page.
 */
export function runField(canvas, button, scene) {
  if (!canvas.isConnected) return undefined;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reducedMotion.matches;
  let visible = true;
  let frame = 0;
  let last = 0;
  let time = 0;
  // The WebGL context is gone: nothing draws until the browser restores it.
  let lost = false;

  function applyStyle() {
    const style = getComputedStyle(canvas);
    scene.style?.({
      color: resolveColor(style.getPropertyValue('--hs-field-color').trim() || style.color),
      strength: Number.parseFloat(style.getPropertyValue('--hs-field-strength')) || 0.36,
      blend: style.getPropertyValue('--hs-field-blend').trim() === 'normal' ? 'normal' : 'add',
    });
  }

  function resize() {
    scene.resize?.(canvas.clientWidth || 1, canvas.clientHeight || 1);
  }

  function stop() {
    cancelAnimationFrame(frame);
    frame = 0;
  }

  function dispose() {
    stop();
    observer.disconnect();
    sizes.disconnect();
    document.removeEventListener('visibilitychange', sync);
    reducedMotion.removeEventListener('change', onMotionChange);
    button.removeEventListener('click', toggle);
    canvas.removeEventListener('webglcontextlost', onContextLost);
    canvas.removeEventListener('webglcontextrestored', onContextRestored);
    scene.dispose?.();
  }

  function tick(now) {
    frame = 0;
    // Client-side navigation removed the page: free the drawing and stop.
    if (!canvas.isConnected) return dispose();
    if (paused || !visible || document.hidden || lost) return;
    const delta = last ? Math.min((now - last) / 1000, MAX_DELTA) : 0;
    last = now;
    time += delta;
    scene.draw(time, delta);
    frame = requestAnimationFrame(tick);
  }

  function sync() {
    stop();
    button.hidden = false;
    button.dataset.hsPaused = String(paused);
    const text = button.querySelector('[data-hs-motion-label]');
    if (text) text.textContent = paused ? LABELS.play : LABELS.pause;
    if (lost) return;
    scene.draw(time, 0);
    if (!paused && visible && !document.hidden) {
      last = 0;
      frame = requestAnimationFrame(tick);
    }
  }

  function toggle() {
    paused = !paused;
    sync();
  }

  function onMotionChange() {
    paused = reducedMotion.matches;
    sync();
  }

  function onContextLost(event) {
    // Without this, the browser never restores the context.
    event.preventDefault();
    lost = true;
    stop();
  }

  function onContextRestored() {
    lost = false;
    scene.restore?.();
    applyStyle();
    resize();
    sync();
  }

  applyStyle();
  resize();
  const sizes = new ResizeObserver(() => {
    resize();
    if (!lost) scene.draw(time, 0);
  });
  sizes.observe(canvas);
  const observer = new IntersectionObserver(([entry]) => {
    visible = entry?.isIntersecting ?? true;
    sync();
  });
  observer.observe(canvas);
  button.addEventListener('click', toggle);
  reducedMotion.addEventListener('change', onMotionChange);
  document.addEventListener('visibilitychange', sync);
  canvas.addEventListener('webglcontextlost', onContextLost);
  canvas.addEventListener('webglcontextrestored', onContextRestored);
  sync();

  return {
    refresh() {
      applyStyle();
      if (!lost) scene.draw(time, 0);
    },
    dispose,
  };
}

/**
 * Resolves any CSS colour (relative colours, `color-mix()`) to its RGB
 * channels, 0 to 255, through a probe element's computed colour.
 *
 * @param {string} value
 * @returns {[number, number, number]}
 */
export function resolveColor(value) {
  const probe = document.createElement('span');
  probe.style.color = value;
  probe.style.display = 'none';
  document.body.append(probe);
  const resolved = getComputedStyle(probe).color;
  probe.remove();
  // Relative colours compute to `color(srgb r g b)`, with channels from 0 to 1.
  const scale = resolved.startsWith('color(') ? 255 : 1;
  const [r = 255, g = 255, b = 255] =
    resolved
      .match(/[\d.]+/g)
      ?.slice(0, 3)
      .map((channel) => Math.round(Number(channel) * scale)) ?? [];
  return [r, g, b];
}
