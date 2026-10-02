import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';
import { escapeHtml, metricHistory, precedingAverage } from '../benchmarks/metrics.mjs';

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
  const source = await readFile(new URL('../benchmarks/dashboard.js', import.meta.url), 'utf8');
  const complete = runInNewContext(source.replace(/^import[^\n]*\n/, ''), {
    metricHistory, precedingAverage, escapeHtml,
    window: { BENCHMARK_DATA: { entries: { 'Protostar Initialization Latency': [
      run(1, wizard, 1500), run(2, editor, 800), run(3, editor, 1000),
    ] } }, addEventListener() {} },
    document: {
      getElementById: element,
      querySelectorAll() { return []; },
      createElement() { return {}; },
      body: { appendChild(script) { script.onload(); } },
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
});
