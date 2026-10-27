/**
 * The landing page's moving background: a protostar's accretion disk.
 *
 * A young star still gathering its mass from a tilted disk of gas and dust.
 * The disk is drawn as thousands of fine, wavy filaments following their
 * orbits, each radius turning at its own orbital speed, so the inner disk
 * whirls while the edge drifts. It's brightest just outside the cavity around
 * the star, where the brightest strands catch the light. The star shows at
 * the centre, partly hidden by the disk's near side, and thin jets leave both
 * poles with knots travelling outward.
 *
 * It's one fragment shader in raw WebGL2, drawn at the screen's resolution so
 * the filaments stay sharp; each layer of detail fades out where it would be
 * finer than a pixel, so nothing shimmers. house-style's `runField` decides
 * when it draws, under the motion rules, and hands it the canvas's
 * `--hs-field-*` style.
 */

import { runField } from "../house/js/field.js";

// The disk's tilt from face-on, as the cosine that squashes its far axis.
const TILT = 0.4;
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

// Value noise from 0 to 1 that repeats every \`period\` cells along x, so it
// wraps seamlessly around the disk.
float noise(vec2 p, float period) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float x0 = mod(i.x, period);
  float x1 = mod(i.x + 1.0, period);
  return mix(
    mix(hash(vec2(x0, i.y)), hash(vec2(x1, i.y)), u.x),
    mix(hash(vec2(x0, i.y + 1.0)), hash(vec2(x1, i.y + 1.0)), u.x),
    u.y
  );
}

// Filaments: noise stretched along the orbits, long around the disk and thin
// across it. \`turn\` is the position around the disk (0 to 1) and \`r\` the
// radius; \`blur\` is how much of each a pixel covers, so detail finer than a
// pixel fades to its average instead of shimmering.
float filaments(float turn, float r, vec2 blur) {
  float around = 12.0;
  float across = 80.0;
  float amplitude = 0.5;
  float sum = 0.0;
  float total = 0.0;
  for (int octave = 0; octave < 7; octave++) {
    float fine = max(around * blur.x, across * blur.y);
    float keep = 1.0 - smoothstep(0.35, 0.8, fine);
    float n = noise(vec2(turn * around, r * across), around);
    sum += amplitude * mix(0.5, n, keep);
    total += amplitude;
    around *= 2.0;
    across *= 2.1;
    amplitude *= 0.75;
  }
  return sum / total;
}

// Fibres: thin ridges where the noise crosses its middle, so they read as
// single bright hairs rather than bands.
float fibres(float turn, float r, vec2 blur) {
  float sum = 0.0;
  float around = 40.0;
  float across = 210.0;
  for (int octave = 0; octave < 2; octave++) {
    float keep = 1.0 - smoothstep(0.3, 0.6, max(around * blur.x, across * blur.y));
    float n = noise(vec2(turn * around, r * across), around);
    sum += keep * pow(1.0 - abs(2.0 * n - 1.0), 8.0) * (octave == 0 ? 0.65 : 0.45);
    around *= 2.0;
    across *= 1.7;
  }
  return sum;
}

// Specks: sparse points of light caught on the strands, each a cell of a
// grid stretched along the orbits that happens to hold one.
float specks(float turn, float r, vec2 blur) {
  vec2 grid = vec2(turn * 420.0, r * 140.0);
  float keep = 1.0 - smoothstep(0.4, 0.9, max(420.0 * blur.x, 140.0 * blur.y));
  vec2 cell = floor(grid);
  float lit = step(0.93, hash(vec2(mod(cell.x, 420.0), cell.y) + 7.3));
  vec2 at = fract(grid) - 0.5;
  return keep * lit * smoothstep(0.5, 0.0, length(at));
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

  // Each radius turns at its own orbital speed, faster near the star.
  float omega = 0.035 * pow(max(r, 0.12), -1.5);
  float turn = fract((theta - omega * uTime) / TAU);
  // How much of the disk one pixel spans, around and across. The turn jumps
  // from 1 to 0 at one angle, so its change is measured away from the jump too.
  float dTurn = min(fwidth(turn), fwidth(fract(turn + 0.5)));
  vec2 blur = vec2(dTurn, fwidth(r));

  // The filaments ripple: their radius wanders slowly around the disk.
  float wander = (noise(vec2(turn * 14.0, r * 7.0), 14.0) - 0.5) * 0.05
    + (noise(vec2(turn * 40.0, r * 19.0 + 3.0), 40.0) - 0.5) * 0.015;
  float f = filaments(turn, r + wander, blur);
  // Contrast: bright strands over dark lanes.
  float strands = pow(smoothstep(0.3, 0.78, f), 1.8);
  float hair = fibres(turn, r + wander, blur);
  float glint = specks(turn, r + wander, blur);

  // Brightest just outside the cavity, dimming outward to a ragged edge.
  float edge = 0.92 + 0.12 * (noise(vec2(turn * 9.0, 0.5), 9.0) - 0.5);
  float body = smoothstep(0.1, 0.2, r)
    * mix(1.8, 0.34, smoothstep(0.18, 0.8, r))
    * (1.0 - smoothstep(edge - 0.2, edge, r));
  // The far side shows its lit, flared surface, so it reads a little brighter.
  float far = 0.82 + 0.18 * smoothstep(-0.5, 0.5, d.y / max(r, 1e-3));
  float disk = body * far * (0.06 + 1.3 * strands + hair * (0.25 + 1.1 * strands) + glint * (0.4 + 1.6 * strands));

  // The star, partly behind the near side of the disk.
  float core = exp(-dot(q, q) / 0.00018) * mix(1.0, 0.4, uLight);
  float halo = exp(-length(q) / 0.045) * 0.3;
  float nearSide = smoothstep(0.004, -0.03, q.y) * (1.0 - smoothstep(0.15, 0.3, r));
  float star = (core + halo) * mix(1.0, 0.25, nearSide);

  // Jets leave both poles along the axis, wobbling as the axis precesses,
  // with knots travelling outward. The far jet is partly hidden by dust.
  float along = abs(q.y);
  float across = q.x - 0.02 * sin(along * 7.0 - uTime * 0.35) * along;
  float width = 0.004 + 0.018 * along;
  float knots = 0.4 + 0.6 * pow(0.5 + 0.5 * sin(along * 18.0 - uTime * 0.9), 3.0);
  float jet = exp(-pow(across / width, 2.0)) * smoothstep(0.05, 0.16, along)
    * (1.0 - smoothstep(0.5, 1.2, along)) * knots * (q.y > 0.0 ? 0.5 : 0.3);

  float light = disk + star + jet;

  // Keep the hero's copy readable: on wide screens the field rises to the
  // right of it, as house-style's attractor did; on narrow ones, below it.
  float right = 0.3 + 0.7 * smoothstep(0.3, 0.68, gl_FragCoord.x / uViewport.x);
  float below = 0.25 + 0.75 * smoothstep(0.5, 0.78, 1.0 - gl_FragCoord.y / uViewport.y);
  float alpha = (1.0 - exp(-1.5 * light)) * uStrength * mix(below, right, uWide);
  alpha = clamp(alpha, 0.0, 1.0);
  // On dark pages the brightest strands run hot, towards white; on light
  // pages the disk is ink, so it stays in the accent.
  float hot = smoothstep(0.4, 1.3, light) * (1.0 - uLight) * 0.8;
  outColor = vec4(mix(uColor, vec3(1.0), hot) * alpha, alpha);
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
      // Full resolution keeps the filaments sharp; past 1.5 device pixels per
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
      gl.uniform1f(u.wide, wide ? 1 : 0);
    },
    draw(time) {
      gl.uniform1f(u.time, time);
      gl.uniform1f(u.strength, strength * (portrait ? 0.8 : 1));
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
