/**
 * The landing page's background: the Lorenz attractor, drawn as a faint
 * texture behind the hero and filmed in hard-cut camera shots the way
 * jacksonferguson.me films its own attractor.
 *
 * docs/index.md imports this only after the page has loaded, so the first
 * screen paints as text. It follows house-style's motion rules: dark cyan,
 * well below the text in contrast, still for reduced motion, paused off
 * screen or in a hidden tab, and stoppable with the page's motion button.
 */

// The version jacksonferguson.me bundles.
const THREE_URL = "https://cdn.jsdelivr.net/npm/three@0.186.0/+esm";

const POINTS = 9000;
const STRANDS = 3;
const VERTICES = POINTS * STRANDS;
const STEPS_PER_FRAME = 2;
const DT = 0.004;

// Lorenz's classic parameters, which give the two butterfly wings.
const SIGMA = 10, RHO = 28, BETA = 8 / 3;
// The wings sit around this height; the scene centres on it.
const CENTRE_Z = 23.5;
const SCALE = 0.1;

function derivative(x, y, z, out) {
  out[0] = SIGMA * (y - x);
  out[1] = x * (RHO - z) - y;
  out[2] = x * y - BETA * z;
}

// Camera shots, cut between like jacksonferguson.me's: each holds about ten
// seconds with a slow drift, then the view jumps to the next.
const SHOTS = [
  { duration: 10, yaw: 0.6, yawSpeed: 0.05, pitch: 0.22, nutation: 0.03, distance: 6.4 },
  { duration: 9.5, yaw: 2.5, yawSpeed: -0.04, pitch: 0.04, nutation: 0.02, distance: 5.2 },
  { duration: 10.5, yaw: -0.6, yawSpeed: 0.06, pitch: 0.55, nutation: 0.03, distance: 6.8 },
  { duration: 9.5, yaw: 3.7, yawSpeed: 0.045, pitch: -0.25, nutation: 0.03, distance: 7.4 },
];

const k1 = [0, 0, 0], k2 = [0, 0, 0], k3 = [0, 0, 0], k4 = [0, 0, 0];

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
    float tail = exp(-age * 2.4);
    // A slow pulse travels down each strand.
    float phase = age * 6.0 - uTime * 0.18 + aStrand * 0.33;
    float pulse = pow(0.5 + 0.5 * sin(6.2831853 * phase), 6.0);
    vGlow = (0.35 + 0.65 * tail) * (0.55 + 0.45 * pulse);
  }
`;

const FRAGMENT = `
  uniform vec3 uColor;
  uniform float uStrength;
  varying float vGlow;

  void main() {
    gl_FragColor = vec4(uColor, vGlow * uStrength);
  }
`;

/**
 * Starts the field on `canvas`, with `button` as its pause control.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {HTMLButtonElement} button
 */
export async function startField(canvas, button) {
  const THREE = await import(THREE_URL);
  if (!canvas.isConnected) return;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  } catch {
    return; // No WebGL: the hero keeps its plain background.
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

  const states = [
    [1.0, 1.0, 1.0],
    [-1.0, 0.5, 20.0],
    [0.5, -1.5, 30.0],
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
    },
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    transparent: true,
    depthWrite: false,
  });
  const group = new THREE.Group();
  for (let s = 0; s < STRANDS; s++) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", position);
    geometry.setAttribute("aIndex", new THREE.BufferAttribute(indices, 1));
    geometry.setAttribute("aStrand", new THREE.BufferAttribute(strands, 1));
    geometry.setDrawRange(s * POINTS, POINTS);
    group.add(new THREE.Line(geometry, material));
  }
  // Lorenz's z is up: stand the wings upright and centre them.
  group.position.set(0, 0, -CENTRE_Z);
  const stage = new THREE.Group();
  stage.add(group);
  stage.scale.setScalar(SCALE);
  stage.rotation.x = -Math.PI / 2;
  scene.add(stage);

  // Dark: cyan added onto the page. Light: a faint teal ink on white.
  const applyScheme = () => {
    const light = document.body.dataset.mdColorScheme === "default";
    material.uniforms.uColor.value.set(light ? "#0e7490" : "#22d3ee");
    material.uniforms.uStrength.value = light ? 0.16 : 0.22;
    material.blending = light ? THREE.NormalBlending : THREE.AdditiveBlending;
    material.needsUpdate = true;
  };
  applyScheme();
  const schemeWatch = new MutationObserver(() => {
    applyScheme();
    draw();
  });
  schemeWatch.observe(document.body, { attributeFilter: ["data-md-color-scheme"] });

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let paused = reducedMotion.matches;
  let visible = true;
  let frame = 0;
  let last = 0;
  let time = 0;
  let shot = 0;
  let shotTime = 0;
  let shotYaw = SHOTS[0].yaw;

  function resize() {
    const width = canvas.clientWidth || 1;
    const height = canvas.clientHeight || 1;
    camera.aspect = width / height;
    // Sit the attractor right of centre on wide screens, where the text isn't.
    camera.setViewOffset(width, height, width > 900 ? -width * 0.2 : 0, 0, width, height);
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
  }

  function advance(delta) {
    shotTime += delta;
    if (shotTime >= SHOTS[shot].duration) {
      shotTime = 0;
      shot = (shot + 1) % SHOTS.length;
      shotYaw = SHOTS[shot].yaw;
    } else {
      shotYaw += SHOTS[shot].yawSpeed * delta;
    }
  }

  function draw() {
    const { pitch, nutation, distance } = SHOTS[shot];
    const tilt = pitch + Math.sin(time * 0.15) * nutation;
    camera.position.set(
      distance * Math.cos(tilt) * Math.sin(shotYaw),
      distance * Math.sin(tilt),
      distance * Math.cos(tilt) * Math.cos(shotYaw),
    );
    camera.lookAt(0, 0, 0);
    material.uniforms.uTime.value = time;
    renderer.render(scene, camera);
  }

  function stop() {
    cancelAnimationFrame(frame);
    frame = 0;
  }

  function dispose() {
    stop();
    schemeWatch.disconnect();
    observer.disconnect();
    sizes.disconnect();
    document.removeEventListener("visibilitychange", sync);
    reducedMotion.removeEventListener("change", onMotionChange);
    renderer.dispose();
  }

  function tick(now) {
    frame = 0;
    // Instant navigation removed the page: free the GPU and stop.
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
    button.setAttribute("aria-pressed", String(paused));
    button.setAttribute("aria-label", paused ? "Play background animation" : "Pause background animation");
    button.querySelector("[data-ps-motion-label]").textContent = paused ? "Play motion" : "Pause motion";
    const icon = button.querySelector(".hs-icon");
    icon.classList.toggle("hs-icon-pause", !paused);
    icon.classList.toggle("hs-icon-play", paused);
    draw();
    if (!paused && visible && !document.hidden) {
      last = 0;
      frame = requestAnimationFrame(tick);
    }
  }

  function onMotionChange() {
    paused = reducedMotion.matches;
    sync();
  }

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
  button.addEventListener("click", () => {
    paused = !paused;
    sync();
  });
  reducedMotion.addEventListener("change", onMotionChange);
  document.addEventListener("visibilitychange", sync);
  canvas.classList.add("is-ready");
  sync();
}
