/**
 * The landing page's moving background: a protostar's accretion disk.
 *
 * A young star still gathering its mass from a tilted disk of gas and dust.
 * The disk turns faster near the star than at its edge, so its turbulence
 * shears into streaks, two spiral arms turn through it, and dark rings mark
 * where forming planets have cleared their orbits. The near side of
 * the disk hides part of the star, and jets leave both poles, with knots
 * travelling outward between faint hourglass-shaped outflow lobes.
 *
 * It's one fragment shader in raw WebGL2, drawn at reduced resolution since
 * it's a soft glow. house-style's `runField` decides when it draws, under the
 * motion rules, and hands it the canvas's `--hs-field-*` style.
 */

import { runField } from "../house/js/field.js";

// The disk's tilt from face-on, as the cosine that squashes its far axis.
const TILT = 0.34;
// The tilt of its axis on screen, in radians.
const POSITION_ANGLE = -0.32;
// A soft glow needs fewer pixels than the screen has.
const RESOLUTION = 0.75;

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
uniform float uTime;
uniform vec3 uColor;
uniform float uStrength;
uniform float uWide;
uniform float uLight;
out vec4 outColor;

const float TAU = 6.28318530718;

vec2 hash(vec2 p) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return fract(sin(p) * 43758.5453) * 2.0 - 1.0;
}

// Gradient noise, from -1 to 1.
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = dot(hash(i), f);
  float b = dot(hash(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0));
  float c = dot(hash(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0));
  float d = dot(hash(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float sum = 0.0;
  float amplitude = 0.5;
  for (int i = 0; i < 4; i++) {
    sum += amplitude * noise(p);
    p = mat2(1.6, 1.2, -1.2, 1.6) * p;
    amplitude *= 0.5;
  }
  return sum;
}

// The disk's turbulence, carried round at each radius's orbital speed.
// Sheared noise winds ever tighter, so two layers restart in turn and
// crossfade, renormalised so the texture never dims between them.
float turbulence(float r, float theta) {
  float omega = 0.07 * pow(max(r, 0.2), -1.5);
  const float CYCLE = 12.0;
  float sum = 0.0;
  float weights = 0.0;
  for (int layer = 0; layer < 2; layer++) {
    float phase = fract(uTime / CYCLE + 0.5 * float(layer));
    float weight = 1.0 - abs(2.0 * phase - 1.0);
    float angle = theta - omega * phase * CYCLE;
    vec2 at = vec2(cos(angle), sin(angle)) * r * 7.0 + float(layer) * 17.0;
    sum += weight * fbm(at);
    weights += weight * weight;
  }
  return sum / sqrt(max(weights, 1e-3));
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

  // Brightest just outside the inner cavity, fading to the edge. The far
  // side shows its lit, flared surface, so it reads a little brighter.
  float profile = smoothstep(0.05, 0.16, r) * (1.0 - smoothstep(0.45, 1.0, r)) / (0.35 + r);
  float far = 0.75 + 0.25 * smoothstep(-0.4, 0.4, d.y / max(r, 1e-3));
  float spiral = pow(0.5 + 0.5 * cos(2.0 * (theta - 0.05 * uTime) - 5.5 * log(max(r, 0.05))), 2.0);
  float gas = clamp(0.5 + 0.8 * turbulence(r, theta), 0.0, 1.0);
  // Dark rings where forming planets have cleared their orbits.
  float gaps = 1.0 - 0.55 * exp(-pow((r - 0.34) / 0.025, 2.0)) - 0.45 * exp(-pow((r - 0.58) / 0.03, 2.0))
    - 0.35 * exp(-pow((r - 0.79) / 0.035, 2.0));
  // Gas coming towards us on one side is a touch brighter.
  float approach = 1.0 + 0.12 * clamp(d.x, -1.0, 1.0);
  float disk = profile * far * approach * gaps * (0.3 + 0.7 * gas) * (0.6 + 0.4 * spiral) * 0.95;

  // The star, partly behind the near side of the disk.
  float core = exp(-dot(q, q) / 0.0008) * mix(1.0, 0.45, uLight);
  float halo = exp(-length(q) / 0.11) * 0.45;
  float nearSide = smoothstep(0.004, -0.03, q.y) * (1.0 - smoothstep(0.2, 0.45, r));
  float star = (core + halo) * mix(1.0, 0.3, nearSide);

  // Jets leave both poles along the axis, wobbling as the axis precesses,
  // with knots travelling outward. The far jet is partly hidden by dust.
  float along = abs(q.y);
  float across = q.x - 0.025 * sin(along * 7.0 - uTime * 0.35) * along;
  float width = 0.008 + 0.03 * along;
  float knots = 0.45 + 0.55 * pow(0.5 + 0.5 * sin(along * 16.0 - uTime * 0.9), 3.0);
  float jet = exp(-pow(across / width, 2.0)) * smoothstep(0.04, 0.16, along)
    * (1.0 - smoothstep(0.55, 1.35, along)) * knots * (q.y > 0.0 ? 0.42 : 0.26);

  // Outflow lobes: the faint walls of an hourglass carved by the jets.
  float wall = abs(abs(q.x) - 0.3 * pow(along, 0.7));
  float lobes = exp(-pow(wall / (0.015 + 0.04 * along), 2.0)) * smoothstep(0.05, 0.3, along)
    * (1.0 - smoothstep(0.35, 1.0, along)) * (0.5 + 0.5 * fbm(p * 4.0 + uTime * 0.01)) * 0.07;

  float light = disk + star + jet + lobes;

  // Keep the hero's copy quiet: on wide screens the field rises to the right
  // of it, as house-style's attractor did.
  float space = 0.4 + 0.6 * smoothstep(0.35, 0.72, gl_FragCoord.x / uViewport.x);
  float alpha = (1.0 - exp(-1.6 * light)) * uStrength * mix(1.0, space, uWide);
  // A whisper of noise keeps faint gradients from banding.
  alpha += (fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) - 0.5) / 255.0;
  alpha = clamp(alpha, 0.0, 1.0);
  outColor = vec4(uColor * alpha, alpha);
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

  const program = link(gl);
  if (!program) return undefined;
  const at = (name) => gl.getUniformLocation(program, name);
  const u = {
    viewport: at("uViewport"),
    center: at("uCenter"),
    scale: at("uScale"),
    time: at("uTime"),
    color: at("uColor"),
    strength: at("uStrength"),
    wide: at("uWide"),
    light: at("uLight"),
  };
  gl.useProgram(program);

  let strength = 0.36;
  let portrait = false;

  return runField(canvas, button, {
    style({ color, strength: value, blend }) {
      gl.uniform3f(u.color, color[0] / 255, color[1] / 255, color[2] / 255);
      gl.uniform1f(u.light, blend === "normal" ? 1 : 0);
      strength = value;
    },
    resize(width, height) {
      const scale = Math.min(window.devicePixelRatio || 1, 1.5) * RESOLUTION;
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      const wide = width > 900;
      portrait = width < 700;
      // Right of the copy on wide screens; on narrow ones, where the copy
      // fills the width, faintly behind the heading.
      const center = wide ? [width * 0.73, height * 0.5] : [width * 0.62, height * 0.3];
      const radius = wide ? Math.min(width * 0.23, height * 0.66) : width * 0.62;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(u.viewport, canvas.width, canvas.height);
      // gl_FragCoord counts up from the bottom.
      gl.uniform2f(u.center, center[0] * scale, (height - center[1]) * scale);
      gl.uniform1f(u.scale, radius * scale);
      gl.uniform1f(u.wide, wide ? 1 : 0);
    },
    draw(time) {
      gl.uniform1f(u.time, time);
      gl.uniform1f(u.strength, strength * (portrait ? 0.75 : 1));
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
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
