/**
 * The landing page's moving background: a protostar's accretion disk.
 *
 * A young star still gathering its mass from a tilted disk of gas and dust,
 * drawn as light rather than shapes, so it reads like a telescope image:
 *
 * - The gas is turbulent: its density is log-normal, so most of it is dim and
 *   a few clumps are very bright, curled by a slow warp and stretched along
 *   orbits that turn faster near the star.
 * - It glows by the star's light, falling off with distance, and the inner
 *   rim, puffed up where the star first heats it, is brightest where we see
 *   it face-on, on the far side.
 * - Dust in the near side's midplane absorbs the light behind it, dimming the
 *   star and the far rim, and a soft bloom surrounds the bright inner disk.
 * - Faint knotty jets leave both poles, a dim envelope surrounds the disk,
 *   and a starfield sits behind it all.
 *
 * Colour comes from light: each channel saturates on its own, so dim gas
 * stays a deep shade of the accent and the brightest gas burns towards white,
 * as an exposure does. It's one fragment shader in raw WebGL2, at the
 * screen's resolution, with every layer of detail fading out where it would
 * be finer than a pixel. house-style's `runField` decides when it draws,
 * under the motion rules, and hands it the canvas's `--hs-field-*` style.
 */

import { runField } from "../house/js/field.js";

// The disk's tilt from face-on, as the cosine that squashes its far axis.
const TILT = 0.38;
// The tilt of its axis on screen, in radians.
const POSITION_ANGLE = -0.36;

const VERTEX = `#version 300 es
void main() {
  vec2 corner = vec2(gl_VertexID == 1 ? 3.0 : -1.0, gl_VertexID == 2 ? 3.0 : -1.0);
  gl_Position = vec4(corner, 0.0, 1.0);
}`;

const FRAGMENT = `#version 300 es
precision highp float;

uniform vec2 uViewport;
uniform vec2 uCenter;
uniform float uScale;
uniform float uPixel;
uniform float uTime;
uniform vec3 uColor;
uniform float uStrength;
uniform float uWide;
uniform float uLight;
out vec4 outColor;

const float TAU = 6.28318530718;

float hash(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

vec2 gradient(vec2 cell) {
  float a = hash(cell) * TAU;
  return vec2(cos(a), sin(a));
}

// Gradient noise from -0.5 to 0.5 that repeats every \`period\` cells along x,
// so it wraps seamlessly around the disk.
float noise(vec2 p, float period) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float x0 = mod(i.x, period);
  float x1 = mod(i.x + 1.0, period);
  float a = dot(gradient(vec2(x0, i.y)), f);
  float b = dot(gradient(vec2(x1, i.y)), f - vec2(1.0, 0.0));
  float c = dot(gradient(vec2(x0, i.y + 1.0)), f - vec2(0.0, 1.0));
  float d = dot(gradient(vec2(x1, i.y + 1.0)), f - vec2(1.0, 1.0));
  return 0.7 * mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Turbulence on the disk: octaves of noise stretched along the orbits.
// \`blur\` is how much of the disk one pixel covers around and across, and
// each octave fades out where it would be finer than a pixel.
float turbulence(vec2 at, float around, float across, vec2 blur, int octaves) {
  float sum = 0.0;
  float amplitude = 1.0;
  for (int octave = 0; octave < 8; octave++) {
    if (octave >= octaves) break;
    float keep = 1.0 - smoothstep(0.3, 0.7, max(around * blur.x, across * blur.y));
    sum += amplitude * keep * noise(vec2(at.x * around, at.y * across), around);
    around *= 2.0;
    across *= 2.0;
    amplitude *= 0.7;
  }
  return sum;
}

// Where a point of the disk was \`age\` seconds ago, as a turn (0 to 1) around
// it: each radius turns at its own orbital speed, faster near the star.
float turnAt(float theta, float r, float age) {
  return fract((theta - 0.008 * pow(max(r, 0.12), -1.5) * age) / TAU);
}

// How much of the disk one pixel covers around and across. The turn jumps
// from 1 to 0 at one angle, so its change is also measured away from the jump.
vec2 pixelSpan(float turn, float r) {
  return vec2(min(fwidth(turn), fwidth(fract(turn + 0.5))), fwidth(r));
}

// The gas carried round by the orbits for \`age\` seconds. A slow warp curls
// the flow, then turbulence stretches along the orbits.
float gasAt(float theta, float r, float age, float seed) {
  float turn = turnAt(theta, r, age);
  vec2 blur = pixelSpan(turn, r);
  vec2 warp = vec2(
    turbulence(vec2(turn, r + seed), 5.0, 6.0, blur, 3),
    turbulence(vec2(turn + 0.37, r + seed + 2.1), 5.0, 6.0, blur, 3)
  );
  vec2 flow = vec2(turn + 0.035 * warp.x, r + seed + 0.025 * warp.y);
  return turbulence(flow, 14.0, 64.0, blur, 7);
}

// One layer of stars: a candidate in each \`size\`-pixel cell, at a random spot,
// with a brightness skewed by \`rarity\` so few are bright, drawn as a point
// \`radius\` pixels wide.
float starLayer(vec2 pixel, float size, float rarity, float radius, float seed) {
  vec2 cell = floor(pixel / size);
  vec2 offset = pixel - (cell + vec2(hash(cell + seed), hash(cell + seed + 9.2))) * size;
  float bright = pow(hash(cell + seed + 4.4), rarity);
  return bright * exp(-dot(offset, offset) / (radius * radius));
}

// Exposure: each channel saturates on its own, so bright light whitens.
vec3 expose(vec3 light) {
  return 1.0 - exp(-light);
}

void main() {
  // Screen space around the star, with the disk's axis turned upright.
  vec2 p = (gl_FragCoord.xy - uCenter) / uScale;
  float s = sin(${POSITION_ANGLE.toFixed(3)});
  float c = cos(${POSITION_ANGLE.toFixed(3)});
  vec2 q = mat2(c, s, -s, c) * p;

  // The disk's own plane: its far axis is foreshortened by the tilt.
  vec2 d = vec2(q.x, q.y / ${TILT.toFixed(3)});
  float r = length(d);
  float theta = atan(d.y, d.x);
  // Facing: 1 on the far side, whose lit upper surface we see; -1 near.
  float facing = d.y / max(r, 1e-4);

  // The orbits shear the gas ever tighter, until its detail is finer than a
  // pixel and fades to a blur. So two copies of the gas each shear for one
  // cycle and start again unwound, half a cycle apart, crossfading so neither
  // restart shows; the mix is rescaled so the texture never dims between them.
  const float CYCLE = 50.0;
  float phase = fract(uTime / CYCLE);
  float wA = 1.0 - abs(2.0 * phase - 1.0);
  float wB = 1.0 - wA;
  float gasA = gasAt(theta, r, phase * CYCLE, floor(uTime / CYCLE) * 3.1);
  float gasB = gasAt(theta, r, fract(phase + 0.5) * CYCLE, floor(uTime / CYCLE + 0.5) * 3.1 + 1.7);
  float gas = (wA * gasA + wB * gasB) / sqrt(wA * wA + wB * wB);
  // Exponentiating it gives the long bright tail of real gas.
  float density = exp(3.4 * gas - 0.5);

  // Features that turn with the disk as a whole, slowly enough not to shear.
  float turn = fract((theta - 0.008 * uTime) / TAU);
  vec2 blur = pixelSpan(turn, r);

  // Starlight on the disk: falling off outward from the inner edge, with a
  // ragged outer edge where the gas thins into the envelope.
  float edge = 0.95 + 0.25 * turbulence(vec2(turn, 0.3), 6.0, 1.0, blur, 3);
  float lit = smoothstep(0.08, 0.19, r) * pow(max(r, 0.15) / 0.2, -2.3)
    * (1.0 - smoothstep(edge - 0.35, edge, r));
  // The far side shows its lit, flared upper surface; the near side its
  // shadowed underside.
  lit *= 0.55 + 0.45 * smoothstep(-0.8, 0.8, facing);
  float disk = lit * density;

  // The inner rim, puffed up where the star first heats the gas: lit gas, so
  // it follows the gas's own clumps, seen most face-on on the far side and
  // fading smoothly towards the near side, where it's seen edge-on.
  float rim = exp(-pow((r - 0.16) / 0.03, 2.0)) * mix(0.35, 1.0, smoothstep(-0.7, 0.9, facing))
    * density;

  // The star and its glow.
  float rq = length(q);
  float star = exp(-rq * rq / 0.00008) * 14.0 + exp(-rq / 0.025) * 1.2;
  // Dust in the near side's midplane absorbs what lies behind it.
  float lane = exp(-pow((q.y + 0.004) / (0.02 + 0.03 * clamp(r, 0.0, 1.0)), 2.0))
    * smoothstep(0.05, -0.01, q.y) * (1.0 - smoothstep(0.25, 0.55, r));
  float behind = exp(-2.2 * lane);
  star *= behind;
  // Only light from behind the near side passes through its dust.
  rim *= mix(1.0, behind, smoothstep(0.5, -0.3, facing));

  // Bloom: the bright inner disk's light spills softly around it.
  float bloom = 0.3 * exp(-r / 0.09) + 0.02 * exp(-length(p) / 0.35);

  // Jets: faint and irregular, knots of shocked gas strung along each pole,
  // broadening as they go. The far jet is dimmer behind the dust.
  float along = abs(q.y);
  float across = q.x - 0.015 * sin(along * 6.0 - uTime * 0.08) * along;
  float width = 0.004 + 0.022 * along;
  float knots = exp(3.0 * noise(vec2(along * 9.0 - uTime * 0.1, q.y > 0.0 ? 3.0 : 7.0), 1000.0));
  float jet = exp(-pow(across / width, 2.0)) * smoothstep(0.06, 0.2, along)
    * (1.0 - smoothstep(0.4, 1.1, along)) * knots * (q.y > 0.0 ? 0.07 : 0.04);

  // The envelope: dim, dusty nebulosity the disk is still drawing from.
  float envelope = 0.025 * exp(-length(p) / 0.6)
    * exp(2.0 * turbulence(vec2(fract(atan(p.y, p.x) / TAU), length(p)), 6.0, 3.0, vec2(0.0), 4));

  // A starfield, still behind it all: a dense layer of faint stars and a
  // sparser one of brighter stars with a little more glow.
  vec2 pixel = gl_FragCoord.xy / uPixel;
  float stars = starLayer(pixel, 16.0, 7.0, 0.7, 1.7) * 0.8
    + starLayer(pixel, 55.0, 2.5, 1.0, 23.1) * 1.6;

  float light = (disk * 1.0 + rim * 1.2 + star + bloom + jet + envelope) * uStrength;

  // Keep the hero's copy readable: on wide screens the field rises to the
  // right of it; on narrow ones, below it.
  float right = 0.25 + 0.75 * smoothstep(0.3, 0.68, gl_FragCoord.x / uViewport.x);
  float below = 0.2 + 0.8 * smoothstep(0.5, 0.78, 1.0 - gl_FragCoord.y / uViewport.y);
  float guard = mix(below, right, uWide);
  light *= guard;
  float starlight = stars * uStrength * sqrt(guard);

  // A whisper of noise keeps the faint gradients from banding.
  float dither = (hash(gl_FragCoord.xy + fract(uTime) * 61.0) - 0.5) / 255.0;

  if (uLight > 0.5) {
    // On a light page the disk is ink: absorbed light in the accent.
    float ink = clamp(1.0 - exp(-0.9 * light), 0.0, 1.0) + dither;
    outColor = vec4(uColor * ink, ink);
  } else {
    // On a dark page, light in the accent's hue, exposed channel by channel.
    // Cooler outer gas sits a little deeper towards blue, which reads as depth.
    vec3 hue = uColor / max(max(uColor.r, uColor.g), uColor.b);
    hue = mix(hue, hue * vec3(0.55, 0.8, 1.0), 0.6 * smoothstep(0.25, 0.9, r));
    vec3 col = expose(light * 1.6 * hue) + starlight * vec3(0.85, 0.95, 1.0) + dither;
    col = clamp(col, 0.0, 1.0);
    outColor = vec4(col, max(max(col.r, col.g), col.b));
  }
}`;

/**
 * Starts the disk on `canvas`, with `button` as its pause control.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {HTMLButtonElement} button
 * @returns {{ refresh(): void, dispose(): void } | undefined} Controls, or
 *   nothing when the browser has no WebGL2 (the hero keeps its plain background).
 */
export function startDisk(canvas, button) {
  const gl = canvas.getContext("webgl2", { alpha: true, premultipliedAlpha: true, antialias: false });
  if (!gl) return undefined;

  // Links the program and finds its uniforms: at startup, and again when a
  // lost context comes back, since the new context has none of the old ones.
  function build() {
    const program = link(gl);
    if (!program) return null;
    const at = (name) => gl.getUniformLocation(program, name);
    gl.useProgram(program);
    return {
      program,
      u: {
        viewport: at("uViewport"),
        center: at("uCenter"),
        scale: at("uScale"),
        pixel: at("uPixel"),
        time: at("uTime"),
        color: at("uColor"),
        strength: at("uStrength"),
        wide: at("uWide"),
        light: at("uLight"),
      },
    };
  }
  let built = build();
  if (!built) return undefined;
  let { program, u } = built;

  let strength = 0.36;
  let portrait = false;

  return runField(canvas, button, {
    style({ color, strength: value, blend }) {
      gl.uniform3f(u.color, color[0] / 255, color[1] / 255, color[2] / 255);
      gl.uniform1f(u.light, blend === "normal" ? 1 : 0);
      strength = value;
    },
    resize(width, height) {
      // Full resolution keeps the detail sharp; past 1.5 device pixels per
      // CSS pixel the extra detail isn't worth the GPU.
      const scale = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      const wide = width > 900;
      portrait = width < 700;
      // Large and right of the copy on wide screens; on narrow ones, where the
      // copy fills the width, low behind the buttons and jump links.
      const center = wide ? [width * 0.69, height * 0.5] : [width * 0.62, height * 0.8];
      const radius = wide ? Math.min(width * 0.36, height * 1.0) : width * 0.8;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(u.viewport, canvas.width, canvas.height);
      // gl_FragCoord counts up from the bottom.
      gl.uniform2f(u.center, center[0] * scale, (height - center[1]) * scale);
      gl.uniform1f(u.scale, radius * scale);
      gl.uniform1f(u.pixel, scale);
      gl.uniform1f(u.wide, wide ? 1 : 0);
    },
    draw(time) {
      gl.uniform1f(u.time, time);
      gl.uniform1f(u.strength, strength * (portrait ? 0.8 : 1));
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
    // runField restyles and resizes after this, which sets the uniforms again.
    restore() {
      built = build();
      if (built) ({ program, u } = built);
    },
    dispose() {
      gl.deleteProgram(program);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    },
  });
}

// Compiles and links the disk's shaders, or returns null when the GPU refuses.
function link(gl) {
  const program = gl.createProgram();
  for (const [type, source] of [
    [gl.VERTEX_SHADER, VERTEX],
    [gl.FRAGMENT_SHADER, FRAGMENT],
  ]) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return null;
    gl.attachShader(program, shader);
  }
  gl.linkProgram(program);
  return gl.getProgramParameter(program, gl.LINK_STATUS) ? program : null;
}
