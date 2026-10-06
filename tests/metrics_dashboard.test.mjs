import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';
import { escapeHtml, metricHistory, precedingAverage } from '../metrics/metrics.mjs';

const editor = 'Protostar Recipe Editor First Frame Latency';
const wizard = 'Protostar TUI Wizard Latency';
const headless = 'Protostar Headless Latency';
function run(date, name, value, id = 'a'.repeat(40)) {
  return { date, commit: { id, message: 'Commit', author: { name: 'Author' } },
    benches: [{ name, value, unit: 'ms' }] };
}

test('current editor measurements exclude historical wizard and headless results', () => {
  const runs = [run(1, wizard, 1500), run(2, headless, 200), run(3, editor, 900)];
  const history = metricHistory(runs, editor);
  assert.equal(history.length, 1);
  assert.equal(history[0].value, 900);
  assert.equal(history[0].date, 3);
  assert.equal(runs.length, 3); // The full export still contains every measurement.
});

test('measurement dates determine latest values, independently of storage order', () => {
  const history = metricHistory([run(3, editor, 300), run(1, editor, 100), run(2, editor, 200)], editor);
  assert.deepEqual(history.map(item => item.value), [100, 200, 300]);
  assert.equal(history.at(-1).date, 3);
});

test('a short history uses its actual preceding count and excludes the current point', () => {
  assert.deepEqual(precedingAverage([{ value: 10 }, { value: 20 }, { value: 90 }], 100),
    { value: 15, count: 2 });
  assert.equal(precedingAverage([], 100), null);
  assert.equal(precedingAverage([{ value: 90 }], 100), null);
});

test('the rolling baseline includes only the requested number of preceding runs', () => {
  const history = Array.from({ length: 102 }, (_, value) => ({ value }));
  assert.deepEqual(precedingAverage(history, 100), { value: 50.5, count: 100 });
});

test('invalid measurements cannot contaminate comparisons or commit links', () => {
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

test('dashboard wiring displays the current editor result, preceding count, and current chart', async () => {
  const elements = new Map();
  const charts = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: '', hidden: false,
      addEventListener() {},
      insertRow() { return { insertCell() { return { appendChild() {} }; } }; },
    });
    return elements.get(id);
  };
  const source = await readFile(new URL('../metrics/dashboard.js', import.meta.url), 'utf8');
  const complete = runInNewContext(source.replace(/^import[^\n]*\n/gm, ''), {
    metricHistory, precedingAverage, escapeHtml, loadCharts: async () => {},
    window: { BENCHMARK_DATA: { entries: { 'Protostar Initialization Latency': [
      run(1, wizard, 1500), run(2, editor, 800), run(3, editor, 1000),
    ] } }, addEventListener() {} },
    document: {
      documentElement: {},
      fonts: { ready: Promise.resolve() },
      getElementById: element,
      querySelectorAll() { return []; },
      createElement() { return { setAttribute() {}, appendChild() {}, prepend() {} }; },
      body: { appendChild(script) { script.onload(); } },
    },
    getComputedStyle() {
      const tokens = { '--panel': '#0e1114', '--text': '#e8edef', '--muted': '#939da6',
        '--accent': '#22d3ee', '--line': '#252c31', '--mono': 'JetBrains Mono',
        '--fs-ui': '14px', '--fs-label': '11px' };
      return { getPropertyValue(name) { return tokens[name]; } };
    },
    echarts: {
      init() {
        return { setOption(options) { charts.push(options); }, on() {} };
      },
      graphic: { LinearGradient: function() {} },
    },
  });
  await complete;
  assert.equal(element('benchmark-status').textContent, '');
  assert.equal(element('kpi-editor-val').textContent, '1000.0');
  assert.equal(element('kpi-editor-avg').textContent, '800.0');
  assert.equal(element('kpi-editor-count').textContent, 1);
  assert.equal(element('kpi-editor-delta').textContent, '+25.0%');
  assert.equal(element('kpi-headless-val').textContent, 'N/A');
  assert.deepEqual(Array.from(charts[1].series[0].data), [800, 1000]);
  assert.equal(charts[1].series[0].lineStyle.color, '#22d3ee');
  assert.equal(charts[1].xAxis.axisLabel.fontFamily, 'JetBrains Mono');
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
