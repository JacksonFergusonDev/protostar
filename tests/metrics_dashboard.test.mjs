import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';
import { escapeHtml, metricHistory } from '../metrics/metrics.mjs';
import { MEASURES, VERDICTS, benchmarkHistory, benchmarkSeries, changeText, osName, systems }
  from '../metrics/benchmarks.mjs';

// The archived Hyperfine history, measured on a different runner each push.
const editor = 'Protostar Recipe Editor First Frame Latency';
const wizard = 'Protostar TUI Wizard Latency';
const headless = 'Protostar Headless Latency';
function run(date, name, value, id = 'a'.repeat(40)) {
  return { date, commit: { id, message: 'Commit', author: { name: 'Author' } },
    benches: [{ name, value, unit: 'ms' }] };
}

test('archived editor measurements exclude historical wizard and headless results', () => {
  const runs = [run(1, wizard, 1500), run(2, headless, 200), run(3, editor, 900)];
  const history = metricHistory(runs, editor);
  assert.equal(history.length, 1);
  assert.equal(history[0].value, 900);
  assert.equal(history[0].date, 3);
});

test('measurement dates determine order, independently of storage order', () => {
  const history = metricHistory([run(3, editor, 300), run(1, editor, 100), run(2, editor, 200)], editor);
  assert.deepEqual(history.map(item => item.value), [100, 200, 300]);
});

test('invalid measurements cannot contaminate the archive or its commit links', () => {
  const invalidUnit = run(1, editor, 20);
  invalidUnit.benches[0].unit = 'seconds';
  assert.deepEqual(metricHistory([
    run(1, editor, NaN), run(1, editor, Infinity), run(1, editor, -1),
    run(NaN, editor, 20), run(1, editor, 20, 'javascript:alert(1)'), invalidUnit,
  ], editor), []);
  const valid = run(1, editor, 0);
  valid.commit.url = 'javascript:alert(1)';
  assert.equal(metricHistory([valid], editor)[0].url,
    `https://github.com/JacksonFergusonDev/protostar/commit/${'a'.repeat(40)}`);
});

test('tooltip data escapes ampersands, quotes, and HTML rather than rendering markup', () => {
  assert.equal(escapeHtml('<img onerror="bad"> & \'author\''),
    '&lt;img onerror=&quot;bad&quot;&gt; &amp; &#39;author&#39;');
});

// The nightly comparisons: one entry per night and operating system.
const timing = (wall, status = 'steady', change = { ratio: 1, low: 0.98, high: 1.02 }) =>
  ({ wall, protostar: wall * 0.6, cpu: wall * 0.5, commands: wall * 0.4, change, status });
const night = (date, os, scenarios, commit = 'd'.repeat(40), baseline = 'e'.repeat(40)) =>
  ({ commit, baseline, date, os, run_id: '1', python: '3.14.0', runs: 10, scenarios });

test('benchmark history sorts by date, keeps safe links, and lists slower scenarios', () => {
  const history = benchmarkHistory([
    night('2026-10-02T00:00:00Z', 'ubuntu-latest', { sync: timing(600, 'suspect'), version: timing(200) }),
    night('2026-10-01T00:00:00Z', 'macos-latest', { sync: timing(500, 'regression') }),
  ]);
  assert.deepEqual(history.map(entry => entry.os), ['macos-latest', 'ubuntu-latest']);
  assert.deepEqual(history[1].flagged, ['sync']);
  assert.equal(history[1].url, `https://github.com/JacksonFergusonDev/protostar/commit/${'d'.repeat(40)}`);
  assert.equal(history[1].compareUrl,
    `https://github.com/JacksonFergusonDev/protostar/compare/${'e'.repeat(40)}...${'d'.repeat(40)}`);
  assert.deepEqual(systems(history), ['macos-latest', 'ubuntu-latest']);
  assert.deepEqual(benchmarkHistory([]), []);
});

test('benchmark data rejects unsafe commits, bad dates, and malformed timings or changes', () => {
  const valid = night('2026-10-01T00:00:00Z', 'ubuntu-latest', { sync: timing(500) });
  for (const entry of [
    { ...valid, commit: 'javascript:alert(1)' }, { ...valid, baseline: 'main' },
    { ...valid, date: 'invalid' }, { ...valid, os: ' ' }, { ...valid, scenarios: {} },
    { ...valid, scenarios: [timing(500)] }, { ...valid, scenarios: { sync: timing(-1) } },
    { ...valid, scenarios: { sync: timing(NaN) } },
    { ...valid, scenarios: { sync: timing(500, 'steady', { ratio: 1, low: 1.1, high: 1.2 }) } },
    { ...valid, scenarios: { sync: timing(500, 'steady', { ratio: 0, low: 0, high: 0 }) } },
    { ...valid, scenarios: { sync: timing(500, 'unknown') } },
  ]) assert.throws(() => benchmarkHistory([entry]), /Invalid/);
  assert.throws(() => benchmarkHistory({}), /array/);
});

test('each scenario is one line across one operating system, with gaps left empty', () => {
  const history = benchmarkHistory([
    night('2026-10-01T00:00:00Z', 'ubuntu-latest', { sync: timing(500) }),
    night('2026-10-01T00:00:00Z', 'macos-latest', { sync: timing(300) }),
    night('2026-10-02T00:00:00Z', 'ubuntu-latest', { sync: timing(550), version: timing(200) }),
  ]);
  const { runs, series } = benchmarkSeries(history, 'ubuntu-latest', 'cpu');
  assert.equal(runs.length, 2);
  assert.deepEqual(series.map(line => line.name), ['sync', 'version']);
  assert.deepEqual(series[0].data, [250, 275]);
  assert.deepEqual(series[1].data, [null, 100]);
  assert.equal(series[0].connectNulls, false);
});

test('a change reads as its percentage and interval, and systems by their names', () => {
  assert.equal(changeText({ ratio: 1.123, low: 1.1, high: 1.15 }), '+12.3% (+10.0% to +15.0%)');
  assert.equal(changeText({ ratio: 0.9, low: 0.85, high: 1 }), '-10.0% (-15.0% to +0.0%)');
  assert.equal(osName('ubuntu-latest'), 'Linux');
  assert.equal(osName('macos-latest'), 'macOS');
  assert.equal(osName('freebsd'), 'freebsd');
});

function fakeElement() {
  return {
    textContent: '', hidden: true, value: '', rows: [], children: [], handlers: {},
    appendChild(child) { this.children.push(child); },
    addEventListener(type, handler) { this.handlers[type] = handler; },
    replaceChildren() { this.rows = []; },
    insertRow() {
      const cells = [];
      this.rows.push(cells);
      return { insertCell() {
        const cell = { textContent: '', appendChild(child) { this.child = child; } };
        cells.push(cell);
        return cell;
      } };
    },
  };
}

const themeTokens = { '--text': '#e8edef', '--muted': '#939da6', '--line': '#252c31',
  '--accent': '#22d3ee', '--mono': 'JetBrains Mono', '--panel': '#0e1114',
  '--fs-ui': '14px', '--fs-label': '11px' };

async function renderBenchmarks(response, chartFailure = false) {
  const elements = new Map();
  const charts = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, fakeElement());
    return elements.get(id);
  };
  const source = await readFile(new URL('../metrics/benchmark-dashboard.js', import.meta.url), 'utf8');
  await runInNewContext(source.replace(/^import[\s\S]*?from[^\n]*\n/gm, ''), {
    MEASURES, VERDICTS, benchmarkHistory, benchmarkSeries, changeText, osName, systems, escapeHtml,
    fetch: async () => response,
    loadCharts: async () => { if (chartFailure) throw new Error('CDN unavailable'); },
    window: { addEventListener() {}, open() {} },
    document: {
      documentElement: {}, fonts: { ready: Promise.resolve() }, getElementById: element,
      createElement() { return { style: {}, setAttribute() {}, prepend() {} }; },
    },
    getComputedStyle() { return { getPropertyValue(name) { return themeTokens[name]; } }; },
    echarts: { init() { return { setOption(options) { charts.push(options); }, on() {}, off() {}, resize() {} }; } },
  });
  return { element, charts };
}

const benchmarkEntries = [
  night('2026-10-01T00:00:00Z', 'ubuntu-latest', { sync: timing(600), version: timing(200) }),
  night('2026-10-01T00:00:00Z', 'macos-latest', { sync: timing(400, 'suspect',
    { ratio: 1.2, low: 1.12, high: 1.25 }), 'init-api': timing(1500) }),
];

test('benchmark panel renders the latest run, recent runs, and featured chart lines', async () => {
  const { element, charts } = await renderBenchmarks({ ok: true, json: async () => benchmarkEntries });
  assert.equal(element('benchmark-status').textContent, '');
  assert.equal(element('benchmark-results').hidden, false);
  assert.equal(element('benchmark-latest').textContent,
    `macOS: ${'d'.repeat(7)}, 1 slower · Linux: ${'d'.repeat(7)}, nothing slower`);
  assert.deepEqual(element('benchmark-os').children.map(option => option.textContent), ['macOS', 'Linux']);
  assert.deepEqual(element('benchmark-measure').children.map(option => option.value), Object.keys(MEASURES));
  const scenarios = element('benchmark-scenarios').rows;
  assert.deepEqual(scenarios.map(row => row[0].textContent), ['init-api', 'sync']);
  assert.deepEqual(scenarios[1].map(cell => cell.textContent),
    ['sync', '400 ms', '200 ms', '160 ms', '+20.0% (+12.0% to +25.0%)', VERDICTS.suspect]);
  const runs = element('benchmark-runs').rows;
  assert.equal(runs[0][2].child.href, `https://github.com/JacksonFergusonDev/protostar/commit/${'d'.repeat(40)}`);
  assert.equal(runs[0][3].child.href,
    `https://github.com/JacksonFergusonDev/protostar/compare/${'e'.repeat(40)}...${'d'.repeat(40)}`);
  assert.deepEqual(charts[0].series.map(line => line.name), ['init-api', 'sync']);
  assert.equal(charts[0].legend.selected['init-api'], false);
  assert.equal(charts[0].legend.selected.sync, true);
});

test('Linux-only benchmark history renders without a macOS series or selector option', async () => {
  const history = benchmarkEntries.filter(entry => entry.os === 'ubuntu-latest');
  const { element, charts } = await renderBenchmarks({ ok: true, json: async () => history });
  assert.equal(element('benchmark-results').hidden, false);
  assert.equal(element('benchmark-latest').textContent, `Linux: ${'d'.repeat(7)}, nothing slower`);
  assert.deepEqual(element('benchmark-os').children.map(option => option.textContent), ['Linux']);
  assert.deepEqual(charts[0].series.map(line => line.name), ['sync', 'version']);
});

test('choosing another system or measure redraws the chart and the latest run', async () => {
  const { element, charts } = await renderBenchmarks({ ok: true, json: async () => benchmarkEntries });
  element('benchmark-os').value = 'ubuntu-latest';
  element('benchmark-os').handlers.change();
  assert.deepEqual(element('benchmark-scenarios').rows.map(row => row[0].textContent), ['sync', 'version']);
  assert.deepEqual(charts.at(-1).series.map(line => line.name), ['sync', 'version']);
  element('benchmark-measure').value = 'cpu';
  element('benchmark-measure').handlers.change();
  assert.equal(element('benchmark-caption').textContent, 'Protostar CPU time / ms');
  assert.deepEqual(charts.at(-1).series[0].data, [300]);
});

test('benchmark panel handles unpublished, empty, malformed, and unavailable history', async () => {
  for (const response of [{ status: 404 }, { ok: true, json: async () => [] }]) {
    const { element, charts } = await renderBenchmarks(response);
    assert.equal(element('benchmark-status').textContent, 'No benchmark runs published yet.');
    assert.equal(element('benchmark-results').hidden, true);
    assert.equal(charts.length, 0);
  }
  for (const response of [{ status: 500, ok: false }, { ok: true, json: async () => ({}) }]) {
    const { element } = await renderBenchmarks(response);
    assert.match(element('benchmark-status').textContent, /could not load/);
  }
});

test('a chart-library failure keeps the timings, and choosing a system still updates them', async () => {
  const { element } = await renderBenchmarks({ ok: true, json: async () => benchmarkEntries }, true);
  assert.equal(element('benchmark-results').hidden, false);
  assert.match(element('benchmark-status').textContent, /Timings and commit links remain available/);
  element('benchmark-os').value = 'ubuntu-latest';
  element('benchmark-os').handlers.change();
  assert.deepEqual(element('benchmark-scenarios').rows.map(row => row[0].textContent), ['sync', 'version']);
});

async function renderArchive(data, { chartFailure = false } = {}) {
  const elements = new Map();
  const charts = [];
  const scripts = [];
  const window = { addEventListener() {} };
  const element = id => {
    if (!elements.has(id)) elements.set(id, fakeElement());
    return elements.get(id);
  };
  const source = await readFile(new URL('../metrics/archive-dashboard.js', import.meta.url), 'utf8');
  runInNewContext(source.replace(/^import[^\n]*\n/gm, ''), {
    escapeHtml, metricHistory, window,
    loadCharts: async () => { if (chartFailure) throw new Error('CDN unavailable'); },
    document: {
      documentElement: {}, fonts: { ready: Promise.resolve() }, getElementById: element,
      createElement() { return {}; },
      body: { appendChild(script) {
        scripts.push(script.src);
        if (data === undefined) return script.onerror();
        window.BENCHMARK_DATA = data;
        script.onload();
      } },
    },
    getComputedStyle() { return { getPropertyValue(name) { return themeTokens[name]; } }; },
    echarts: { init() { return { setOption(options) { charts.push(options); }, resize() {} }; } },
  });
  const archive = element('benchmark-archive');
  return { element, charts, scripts, archive,
    async open() { archive.open = true; await archive.handlers.toggle(); } };
}

const archived = { entries: { 'Protostar Initialization Latency': [
  run(Date.parse('2026-03-07T00:00:00Z'), headless, 150), run(Date.parse('2026-03-08T00:00:00Z'), wizard, 1500),
  run(Date.parse('2026-10-06T00:00:00Z'), editor, 1200), run(Date.parse('2026-10-06T00:00:00Z'), headless, 140),
] } };

test('the archive loads its data only when opened, and charts both startup series', async () => {
  const archive = await renderArchive(archived);
  assert.deepEqual(archive.scripts, []);
  await archive.open();
  await archive.open();
  assert.deepEqual(archive.scripts, ['data.js']);
  assert.equal(archive.element('archive-status').textContent, '3 points, March 2026 to October 2026.');
  // Built inside the panel's own realm, so compared as plain arrays.
  assert.deepEqual(Array.from(archive.charts[0].series, line => line.name),
    ['Help-command startup', 'Recipe editor first frame']);
  assert.deepEqual(Array.from(archive.charts[0].series[0].data, point => point[1]), [150, 140]);
  assert.equal(archive.charts[0].xAxis.type, 'time');
});

test('an archive that cannot load or has no points says so', async () => {
  const missing = await renderArchive(undefined);
  await missing.open();
  assert.match(missing.element('archive-status').textContent, /could not load/);
  const empty = await renderArchive({ entries: {} });
  await empty.open();
  assert.match(empty.element('archive-status').textContent, /could not be read/);
  assert.equal(empty.charts.length, 0);
});

// Mutation history is a separate raw-count dataset, independent of latency runs.
const { mutationScore, mutationHistory, mutationSeries } = await import('../metrics/mutations.mjs');
const moduleResult = (module, killed, survived = 0, extra = {}) =>
  ({ module, killed, timeout: 0, survived, suspicious: 0, no_tests: 0, ...extra });
const mutationRun = (date, modules) => ({ commit: 'b'.repeat(40), date, modules });

test('mutation scores weight raw counts and include timeouts and suspicious mutants', () => {
  const modules = [moduleResult('small', 1, 0, { no_tests: 100 }),
    moduleResult('large', 1, 5, { timeout: 1, suspicious: 2 })];
  assert.equal(mutationScore(modules), 30);
  assert.equal(mutationScore([moduleResult('unreached', 0, 0, { no_tests: 8 })]), null);
});

test('mutation scope changes use sorted names, including additions and removals', () => {
  const entries = [mutationRun('2026-10-03T00:00:00Z', [moduleResult('b', 1)]),
    mutationRun('2026-10-01T00:00:00Z', [moduleResult('b', 1), moduleResult('a', 1)]),
    mutationRun('2026-10-02T00:00:00Z', [moduleResult('a', 1), moduleResult('b', 1)]),
    mutationRun('2026-10-04T00:00:00Z', [moduleResult('b', 1), moduleResult('c', 1)])];
  const history = mutationHistory(entries);
  assert.deepEqual(history.map(entry => entry.scopeChanged), [false, false, true, true]);
  assert.deepEqual(history[2].removed, ['a']);
  assert.deepEqual(history[3].added, ['c']);
  assert.equal(entries[0].date, '2026-10-03T00:00:00Z');
  const series = mutationSeries(history);
  assert.deepEqual(series.map(line => line.name), ['Overall', 'a', 'b', 'c']);
  assert.deepEqual(series[1].data, [100, 100, null, null]);
  assert.deepEqual(series[3].data, [null, null, null, 100]);
  assert.equal(series[1].connectNulls, false);
});

test('empty mutation histories and zero denominators cannot invent a score', () => {
  assert.deepEqual(mutationHistory([]), []);
  const history = mutationHistory([mutationRun('2026-10-01T00:00:00Z', [moduleResult('a', 0)])]);
  assert.equal(history[0].value, null);
  assert.deepEqual(mutationSeries(history)[1].data, [null]);
});

test('mutation data rejects malformed dates, unsafe commits, duplicate modules, and invalid counts', () => {
  const valid = mutationRun('2026-10-01T00:00:00Z', [moduleResult('a', 1)]);
  for (const entry of [
    { ...valid, commit: 'javascript:alert(1)' }, { ...valid, date: 'invalid' },
    { ...valid, modules: [] }, { ...valid, modules: [moduleResult('a', -1)] },
    { ...valid, modules: [moduleResult('a', 1.2)] },
    { ...valid, modules: [moduleResult('a', 1, 0, { suspicious: NaN })] },
    { ...valid, modules: [moduleResult('a', 1), moduleResult('a', 2)] },
  ]) assert.throws(() => mutationHistory([entry]), /Invalid/);
  assert.throws(() => mutationHistory({}), /array/);
  assert.equal(mutationHistory([valid])[0].url,
    `https://github.com/JacksonFergusonDev/protostar/commit/${valid.commit}`);
});

async function renderMutations(response, chartFailure = false) {
  const elements = new Map();
  const charts = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: '', hidden: true, rows: [],
      insertRow() {
        const cells = [];
        this.rows.push(cells);
        return { insertCell() {
          const cell = { textContent: '', appendChild(child) { this.child = child; } };
          cells.push(cell);
          return cell;
        } };
      },
    });
    return elements.get(id);
  };
  const source = await readFile(new URL('../metrics/mutation-dashboard.js', import.meta.url), 'utf8');
  await runInNewContext(source.replace(/^import[^\n]*\n/gm, ''), {
    mutationHistory, mutationScore, mutationSeries, escapeHtml,
    fetch: async () => response,
    loadCharts: async () => { if (chartFailure) throw new Error('CDN unavailable'); },
    window: { addEventListener() {} },
    document: {
      documentElement: {}, fonts: { ready: Promise.resolve() }, getElementById: element,
      createElement() { return { style: {}, setAttribute() {}, prepend() {}, remove() {} }; },
      body: { appendChild() {} },
    },
    getComputedStyle() {
      return { color: '#22d3ee', getPropertyValue(name) {
        return ({ '--text': '#e8edef', '--muted': '#939da6', '--line': '#252c31',
          '--accent': '#22d3ee', '--mono': 'JetBrains Mono', '--panel': '#0e1114',
          '--fs-ui': '14px', '--fs-label': '11px' })[name];
      } };
    },
    echarts: { init() { return { setOption(options) { charts.push(options); }, on() {} }; } },
  });
  return { element, charts };
}

test('mutation panel renders independently, with module lines, scope markers, and safe commit links', async () => {
  const entries = [mutationRun('2026-10-01T00:00:00Z', [moduleResult('a', 1)]),
    mutationRun('2026-10-02T00:00:00Z', [moduleResult('b', 1, 1)])];
  const { element, charts } = await renderMutations({ ok: true, json: async () => entries });
  assert.equal(element('mutation-status').textContent, '');
  assert.equal(element('mutation-results').hidden, false);
  assert.match(element('mutation-latest').textContent, /^50.0% overall/);
  assert.equal(element('mutation-modules').rows[0][0].textContent, 'b');
  assert.equal(element('mutation-modules').rows[0][2].textContent, '1 / 2');
  assert.equal(element('mutation-runs').rows[0][2].child.href,
    `https://github.com/JacksonFergusonDev/protostar/commit/${'b'.repeat(40)}`);
  assert.match(element('mutation-runs').rows[0][3].textContent, /added b; removed a/);
  assert.equal(charts[0].series.length, 3);
  assert.equal(charts[0].series[0].markLine.data[0].xAxis, 1);
  assert.equal(charts[0].yAxis.max, 100);
  assert.equal(charts[0].legend.selected.Overall, true);
  assert.equal(charts[0].legend.selected.b, false);
});

test('mutation panel handles unpublished, empty, malformed, and unavailable history', async () => {
  for (const response of [{ status: 404 }, { ok: true, json: async () => [] }]) {
    const { element, charts } = await renderMutations(response);
    assert.equal(element('mutation-status').textContent, 'No complete mutation runs published yet.');
    assert.equal(element('mutation-results').hidden, true);
    assert.equal(charts.length, 0);
  }
  for (const response of [{ status: 500, ok: false }, { ok: true, json: async () => ({}) }]) {
    const { element } = await renderMutations(response);
    assert.match(element('mutation-status').textContent, /could not load/);
  }
});

test('a chart-library failure preserves mutation scores and the accessible tables', async () => {
  const { element } = await renderMutations({ ok: true,
    json: async () => [mutationRun('2026-10-01T00:00:00Z', [moduleResult('a', 1)])] }, true);
  assert.equal(element('mutation-results').hidden, false);
  assert.equal(element('mutation-modules').rows[0][1].textContent, '100.0%');
  assert.match(element('mutation-status').textContent, /Scores and commit links remain available/);
});

// Rollback history is another raw-count dataset, kept per operating system and template.
const { rollbackTotal, rollbackHistory, rollbackSeries } = await import('../metrics/rollbacks.mjs');
const rollbackCell = (os, template, passed) => ({ os, template, passed });
const rollbackRun = (date, cells) => ({ commit: 'c'.repeat(40), date, cells });

test('rollback totals add every job and the series split them by system and template', () => {
  const history = rollbackHistory([rollbackRun('2026-10-01T00:00:00Z', [
    rollbackCell('ubuntu', 'cli', 10), rollbackCell('ubuntu', 'lib', 5),
    rollbackCell('windows', 'cli', 10)])]);
  assert.equal(history[0].value, 25);
  assert.equal(rollbackTotal([]), 0);
  const series = rollbackSeries(history);
  assert.deepEqual(series.map(line => line.name), ['Overall', 'ubuntu', 'windows', 'cli', 'lib']);
  assert.deepEqual(series.map(line => line.data[0]), [25, 15, 10, 20, 5]);
});

test('rollback scope changes follow the set of jobs, not the counts', () => {
  const history = rollbackHistory([
    rollbackRun('2026-10-03T00:00:00Z', [rollbackCell('ubuntu', 'cli', 12), rollbackCell('ubuntu', 'lib', 1)]),
    rollbackRun('2026-10-01T00:00:00Z', [rollbackCell('ubuntu', 'cli', 10)]),
    rollbackRun('2026-10-02T00:00:00Z', [rollbackCell('ubuntu', 'cli', 11)])]);
  assert.deepEqual(history.map(entry => entry.scopeChanged), [false, false, true]);
  assert.deepEqual(history[2].added, ['ubuntu/lib']);
  assert.deepEqual(history[2].removed, []);
  const series = rollbackSeries(history);
  assert.deepEqual(series.find(line => line.name === 'lib').data, [null, null, 1]);
  assert.equal(series[0].connectNulls, false);
  assert.deepEqual(rollbackHistory([]), []);
});

test('rollback data rejects malformed dates, unsafe commits, duplicate jobs, and invalid counts', () => {
  const valid = rollbackRun('2026-10-01T00:00:00Z', [rollbackCell('ubuntu', 'cli', 1)]);
  for (const entry of [
    { ...valid, commit: 'javascript:alert(1)' }, { ...valid, date: 'invalid' },
    { ...valid, cells: [] }, { ...valid, cells: [rollbackCell('ubuntu', 'cli', -1)] },
    { ...valid, cells: [rollbackCell('ubuntu', 'cli', 1.5)] },
    { ...valid, cells: [rollbackCell('', 'cli', 1)] },
    { ...valid, cells: [rollbackCell('ubuntu', 'cli', 1), rollbackCell('ubuntu', 'cli', 2)] },
  ]) assert.throws(() => rollbackHistory([entry]), /Invalid/);
  assert.throws(() => rollbackHistory({}), /array/);
  assert.equal(rollbackHistory([valid])[0].url,
    `https://github.com/JacksonFergusonDev/protostar/commit/${valid.commit}`);
});

async function renderRollbacks(responses, chartFailure = false) {
  const elements = new Map();
  const charts = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: '', hidden: true, rows: [], children: [],
      appendChild(child) { this.children.push(child); },
      insertRow() {
        const cells = [];
        this.rows.push(cells);
        return { insertCell() {
          const cell = { textContent: '', appendChild(child) { this.child = child; } };
          cells.push(cell);
          return cell;
        } };
      },
    });
    return elements.get(id);
  };
  const source = await readFile(new URL('../metrics/rollback-dashboard.js', import.meta.url), 'utf8');
  await runInNewContext(source.replace(/^import[^\n]*\n/gm, ''), {
    rollbackHistory, rollbackSeries, escapeHtml,
    fetch: async url => responses[url],
    loadCharts: async () => { if (chartFailure) throw new Error('CDN unavailable'); },
    window: { addEventListener() {} },
    document: {
      documentElement: {}, fonts: { ready: Promise.resolve() }, getElementById: element,
      createElement() { return { style: {}, setAttribute() {}, prepend() {}, remove() {} }; },
      body: { appendChild() {} },
    },
    getComputedStyle() {
      return { color: '#22d3ee', getPropertyValue(name) {
        return ({ '--text': '#e8edef', '--muted': '#939da6', '--line': '#252c31',
          '--accent': '#22d3ee', '--mono': 'JetBrains Mono', '--panel': '#0e1114',
          '--fs-ui': '14px', '--fs-label': '11px' })[name];
      } };
    },
    echarts: { init() { return { setOption(options) { charts.push(options); }, on() {} }; } },
  });
  return { element, charts };
}

const rollbackEntries = [
  rollbackRun('2026-10-01T00:00:00Z', [rollbackCell('ubuntu', 'cli', 1200), rollbackCell('windows', 'cli', 1200)]),
  rollbackRun('2026-10-02T00:00:00Z', [rollbackCell('ubuntu', 'cli', 1300), rollbackCell('windows', 'cli', 1300),
    rollbackCell('windows', 'lib', 800)])];

test('rollback panel renders counts, a per-template table, scope markers, and safe commit links', async () => {
  const { element, charts } = await renderRollbacks({
    'rollback-history.json': { ok: true, json: async () => rollbackEntries },
    'rollback-latest.json': { ok: true, json: async () => ({ message: '3,400' }) } });
  assert.equal(element('rollback-status').textContent, '');
  assert.equal(element('rollback-failing').textContent, '');
  assert.equal(element('rollback-results').hidden, false);
  assert.match(element('rollback-latest').textContent, /^3,400 faults restored/);
  assert.deepEqual(element('rollback-os').children.map(cell => cell.textContent), ['ubuntu', 'windows']);
  assert.deepEqual(element('rollback-cells').rows[0].map(cell => cell.textContent), ['cli', '1,300', '1,300']);
  assert.deepEqual(element('rollback-cells').rows[1].map(cell => cell.textContent), ['lib', 'N/A', '800']);
  assert.equal(element('rollback-runs').rows[0][2].child.href,
    `https://github.com/JacksonFergusonDev/protostar/commit/${'c'.repeat(40)}`);
  assert.match(element('rollback-runs').rows[0][3].textContent, /added windows\/lib/);
  assert.equal(charts[0].series[0].markLine.data[0].xAxis, 1);
  assert.equal(charts[0].legend.selected.Overall, true);
  assert.equal(charts[0].legend.selected.cli, false);
});

test('rollback panel says when the latest run failed, without putting it in the history', async () => {
  const { element } = await renderRollbacks({
    'rollback-history.json': { ok: true, json: async () => rollbackEntries },
    'rollback-latest.json': { ok: true, json: async () => ({ message: '2 failing' }) } });
  assert.match(element('rollback-failing').textContent, /most recent run had 2 failing/);
  assert.equal(element('rollback-results').hidden, false);
});

test('rollback panel handles unpublished, empty, malformed, and unavailable history', async () => {
  for (const response of [{ status: 404 }, { ok: true, json: async () => [] }]) {
    const { element, charts } = await renderRollbacks({ 'rollback-history.json': response });
    assert.equal(element('rollback-status').textContent, 'No complete rollback runs published yet.');
    assert.equal(element('rollback-results').hidden, true);
    assert.equal(charts.length, 0);
  }
  for (const response of [{ status: 500, ok: false }, { ok: true, json: async () => ({}) }]) {
    const { element } = await renderRollbacks({ 'rollback-history.json': response });
    assert.match(element('rollback-status').textContent, /could not load/);
  }
});

test('a missing badge file or a chart-library failure keeps the rollback counts', async () => {
  const { element } = await renderRollbacks({
    'rollback-history.json': { ok: true, json: async () => rollbackEntries },
    'rollback-latest.json': { status: 404, ok: false } }, true);
  assert.equal(element('rollback-failing').textContent, '');
  assert.equal(element('rollback-results').hidden, false);
  assert.match(element('rollback-status').textContent, /Counts and commit links remain available/);
});
