/**
 * A hero's moving background: the Dadras attractor, drawn as a faint texture,
 * with slow orbital shots and close passes through its curled surfaces.
 *
 * It follows GUIDELINES.md's motion rules: subdued shades of the accent, well
 * below the text in contrast, still for reduced motion, paused off screen or
 * in a hidden tab, and stoppable with its pause button (css/site.css,
 * `.hs-motion`). Start it after the page has loaded, so the first screen
 * paints as text, and pass in three.js:
 *
 *   const THREE = await import('three');
 *   startField(THREE, canvas, button);
 *
 * The canvas's CSS sets the drawing: `--hs-field-color` (default the accent),
 * `--hs-field-strength` (0.36), and `--hs-field-blend` (`add` on dark pages,
 * `normal` on light ones). Call `refresh()` after changing them.
 */

const POINTS = 24000;
const STRANDS = 4;
const VERTICES = POINTS * STRANDS;
const STEPS_PER_FRAME = 2;
const DT = 0.004;

// Dadras parameters: a = 3, b = 2.7, c = 1.7, d = 2, h = 9.
const A = 3,
  B = 2.7,
  C = 1.7,
  D = 2,
  H = 9;
const SCALE = 0.13;

function derivative(x, y, z, out) {
  out[0] = y - A * x + B * y * z;
  out[1] = C * y - x * z + z;
  out[2] = D * x * y - H * z;
}

// Open above the three curls, then alternate intimate passes and wider
// reveals. Each move eases in and out, then cuts directly to the next shot.
const SHOTS = [
  {
    duration: 19,
    yaw: [0.85, 1.3],
    pitch: [0.86, 0.62],
    distance: [4.55, 3.85],
    focus: [
      [0, 0, 0],
      [0.12, 0.15, -0.08],
    ],
    roll: [-0.03, 0.04],
  },
  {
    duration: 17,
    yaw: [2.25, 2.7],
    pitch: [-0.35, -0.55],
    distance: [3.1, 2.3],
    focus: [
      [0.55, 0.1, 0.1],
      [0.7, 0.2, 0.15],
    ],
    roll: [0.05, -0.06],
  },
  {
    duration: 18,
    yaw: [4.55, 5.05],
    pitch: [0.22, 0.5],
    distance: [4.4, 3.6],
    focus: [
      [0, 0.1, 0],
      [-0.2, 0.2, 0],
    ],
    roll: [-0.04, 0.04],
  },
  {
    duration: 17,
    yaw: [5.55, 5.95],
    pitch: [0.7, 0.4],
    distance: [2.85, 2.4],
    focus: [
      [0.55, 0.4, 0.2],
      [0.85, 0.6, 0.15],
    ],
    roll: [0.06, -0.03],
  },
  {
    duration: 18,
    yaw: [0.2, 0.66],
    pitch: [-0.45, -0.1],
    distance: [4.5, 4.8],
    focus: [
      [0.15, 0, 0.15],
      [0, 0, 0],
    ],
    roll: [-0.04, 0.02],
  },
];

function interpolate(from, to, progress) {
  return from + (to - from) * progress;
}

const k1 = [0, 0, 0],
  k2 = [0, 0, 0],
  k3 = [0, 0, 0],
  k4 = [0, 0, 0];

function step(s) {
  derivative(s[0], s[1], s[2], k1);
  derivative(s[0] + 0.5 * DT * k1[0], s[1] + 0.5 * DT * k1[1], s[2] + 0.5 * DT * k1[2], k2);
  derivative(s[0] + 0.5 * DT * k2[0], s[1] + 0.5 * DT * k2[1], s[2] + 0.5 * DT * k2[2], k3);
  derivative(s[0] + DT * k3[0], s[1] + DT * k3[1], s[2] + DT * k3[2], k4);
  for (let i = 0; i < 3; i++) s[i] += (DT / 6) * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
}

const VERTEX = `
  attribute float aIndex;
  attribute float aStrand;
  uniform float uTime;
  varying float vGlow;

  void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    float age = aIndex / ${POINTS.toFixed(1)};
    float tail = exp(-age * 1.2);
    // A slow pulse travels down each strand.
    float phase = age * 6.0 - uTime * 0.18 + aStrand * 0.33;
    float pulse = pow(0.5 + 0.5 * sin(6.2831853 * phase), 6.0);
    vGlow = (0.55 + 0.45 * tail) * (0.75 + 0.25 * pulse);
  }
`;

const FRAGMENT = `
  uniform vec3 uColor;
  uniform float uStrength;
  uniform vec2 uViewport;
  uniform float uTextGuard;
  varying float vGlow;

  void main() {
    // Keep the hero's copy quiet while the geometry opens out on the right.
    float space = 0.4 + 0.6 * smoothstep(0.35, 0.72, gl_FragCoord.x / uViewport.x);
    gl_FragColor = vec4(uColor, vGlow * uStrength * mix(1.0, space, uTextGuard));
  }
`;

// The button's visible text is its whole accessible name (WCAG 2.5.3), and it
// says what a press does; `data-hs-paused` picks the icon.
const LABELS = { pause: 'Pause motion', play: 'Play motion' };

/**
 * Starts the field on `canvas`, with `button` as its pause control.
 *
 * @param {object} THREE The three.js module.
 * @param {HTMLCanvasElement} canvas
 * @param {HTMLButtonElement} button
 * @returns {{ refresh(): void, dispose(): void } | undefined} Controls, or
 *   nothing when the browser has no WebGL (the hero keeps its plain background).
 */
export function startField(THREE, canvas, button) {
  if (!canvas.isConnected) return undefined;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  } catch {
    return undefined;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

  const states = [
    [1.0, 1.0, 1.0],
    [1.01, 1.0, 1.0],
    [1.0, 1.01, 1.0],
    [1.0, 1.0, 1.01],
  ];
  for (let i = 0; i < 3000; i++) states.forEach(step);

  const positions = new Float32Array(VERTICES * 3);
  const indices = new Float32Array(VERTICES);
  const strands = new Float32Array(VERTICES);
  for (let s = 0; s < STRANDS; s++) {
    for (let i = 0; i < POINTS; i++) {
      step(states[s]);
      const v = s * POINTS + (POINTS - 1 - i);
      positions.set(states[s], v * 3);
      indices[v] = POINTS - 1 - i;
      strands[v] = s;
    }
  }

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 50);
  const position = new THREE.BufferAttribute(positions, 3);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Color() },
      uStrength: { value: 0 },
      uViewport: { value: new THREE.Vector2() },
      uTextGuard: { value: 0 },
    },
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    transparent: true,
    depthWrite: false,
  });
  const group = new THREE.Group();
  for (let s = 0; s < STRANDS; s++) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', position);
    geometry.setAttribute('aIndex', new THREE.BufferAttribute(indices, 1));
    geometry.setAttribute('aStrand', new THREE.BufferAttribute(strands, 1));
    geometry.setDrawRange(s * POINTS, POINTS);
    group.add(new THREE.Line(geometry, material));
  }
  // Centre the attractor's range in the camera's view.
  group.position.set(2, 2, -1.5);
  const stage = new THREE.Group();
  stage.add(group);
  stage.scale.setScalar(SCALE);
  stage.rotation.x = -Math.PI / 2;
  scene.add(stage);

  // The colour, strength, and blending come from the canvas's CSS.
  let strength = 0;
  function applyStyle() {
    const style = getComputedStyle(canvas);
    const color = style.getPropertyValue('--hs-field-color').trim() || style.color;
    material.uniforms.uColor.value.set(resolveColor(color));
    strength = Number.parseFloat(style.getPropertyValue('--hs-field-strength')) || 0.36;
    const normal = style.getPropertyValue('--hs-field-blend').trim() === 'normal';
    material.blending = normal ? THREE.NormalBlending : THREE.AdditiveBlending;
    material.needsUpdate = true;
  }

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reducedMotion.matches;
  let visible = true;
  let frame = 0;
  let last = 0;
  let time = 0;
  let shot = 0;
  let shotTime = 0;
  const focus = new THREE.Vector3();

  function resize() {
    const width = canvas.clientWidth || 1;
    const height = canvas.clientHeight || 1;
    camera.aspect = width / height;
    // Sit the attractor right of centre on wide screens, where the text isn't.
    camera.setViewOffset(width, height, width > 900 ? -width * 0.2 : 0, 0, width, height);
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    renderer.getDrawingBufferSize(material.uniforms.uViewport.value);
    material.uniforms.uTextGuard.value = width > 900 ? 1 : 0;
  }

  function advance(delta) {
    shotTime += delta;
    while (shotTime >= SHOTS[shot].duration) {
      shotTime -= SHOTS[shot].duration;
      shot = (shot + 1) % SHOTS.length;
    }
  }

  function draw() {
    const view = SHOTS[shot];
    const progress = shotTime / view.duration;
    const eased = progress * progress * (3 - 2 * progress);
    const yaw = interpolate(...view.yaw, eased);
    const tilt = interpolate(...view.pitch, eased);
    // Leave more breathing room for the text on portrait screens.
    const portrait = canvas.clientWidth < 700;
    const distance = interpolate(...view.distance, eased) * (portrait ? 1.25 : 1);
    focus.set(
      ...view.focus[0].map((value, axis) => interpolate(value, view.focus[1][axis], eased)),
    );
    camera.position
      .set(
        distance * Math.cos(tilt) * Math.sin(yaw),
        distance * Math.sin(tilt),
        distance * Math.cos(tilt) * Math.cos(yaw),
      )
      .add(focus);
    camera.lookAt(focus);
    camera.rotateZ(interpolate(...view.roll, eased));
    material.uniforms.uStrength.value = strength * (portrait ? 0.75 : 1);
    material.uniforms.uTime.value = time;
    renderer.render(scene, camera);
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
    renderer.dispose();
  }

  function tick(now) {
    frame = 0;
    // Client-side navigation removed the page: free the GPU and stop.
    if (!canvas.isConnected) return dispose();
    if (paused || !visible || document.hidden) return;
    const delta = last ? Math.min((now - last) / 1000, 0.08) : 0;
    last = now;
    time += delta;
    advance(delta);
    for (let n = 0; n < STEPS_PER_FRAME; n++) {
      for (let s = 0; s < STRANDS; s++) {
        step(states[s]);
        const start = s * POINTS * 3;
        positions.copyWithin(start + 3, start, start + (POINTS - 1) * 3);
        positions.set(states[s], start);
      }
    }
    position.needsUpdate = true;
    draw();
    frame = requestAnimationFrame(tick);
  }

  function sync() {
    stop();
    button.hidden = false;
    button.dataset.hsPaused = String(paused);
    const text = button.querySelector('[data-hs-motion-label]');
    if (text) text.textContent = paused ? LABELS.play : LABELS.pause;
    draw();
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

  applyStyle();
  resize();
  const sizes = new ResizeObserver(() => {
    resize();
    draw();
  });
  sizes.observe(canvas);
  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    sync();
  });
  observer.observe(canvas);
  button.addEventListener('click', toggle);
  reducedMotion.addEventListener('change', onMotionChange);
  document.addEventListener('visibilitychange', sync);
  canvas.classList.add('hs-field--ready');
  sync();

  return {
    refresh() {
      applyStyle();
      draw();
    },
    dispose,
  };
}

// CSS colours can be any syntax (relative colours, color-mix); the browser
// resolves them to rgb() through a probe element's computed colour.
function resolveColor(value) {
  const probe = document.createElement('span');
  probe.style.color = value;
  probe.style.display = 'none';
  document.body.append(probe);
  const resolved = getComputedStyle(probe).color;
  probe.remove();
  const channels = resolved
    .match(/[\d.]+/g)
    ?.slice(0, 3)
    .map(Number) ?? [255, 255, 255];
  return `rgb(${channels.map(Math.round).join(', ')})`;
}
