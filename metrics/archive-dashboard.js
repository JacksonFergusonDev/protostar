import { escapeHtml, metricHistory } from './metrics.mjs';
import { loadCharts } from './charts.mjs';

// Startup timings Hyperfine recorded on every push to main until October 2026.
// Each was measured on whichever runner the push got, so they stay apart from
// the nightly comparisons. They load only when the archive is opened.
const SERIES = [
  ['Help-command startup', 'Protostar Headless Latency'],
  ['Recipe editor first frame', 'Protostar Recipe Editor First Frame Latency'],
];
const archive = document.getElementById('benchmark-archive');
const status = document.getElementById('archive-status');
const month = date => new Date(date).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

function loadData() {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'data.js';
    script.onload = resolve;
    script.onerror = reject;
    document.body.appendChild(script);
  });
}

let opened = false;
archive.addEventListener('toggle', async () => {
  if (!archive.open || opened) return;
  opened = true;
  status.textContent = 'Loading the archived timings…';
  try {
    await loadData();
    const runs = Object.values(window.BENCHMARK_DATA?.entries ?? {}).flat();
    const histories = SERIES.map(([label, name]) => [label, metricHistory(runs, name)]);
    const dates = histories.flatMap(([, history]) => history.map(point => point.date));
    if (!dates.length) {
      status.textContent = 'The archived timings could not be read. Download them below.';
      return;
    }
    status.textContent = `${dates.length.toLocaleString('en-US')} points, ` +
      `${month(Math.min(...dates))} to ${month(Math.max(...dates))}.`;
    await loadCharts();
    await document.fonts.ready;
    const tokens = getComputedStyle(document.documentElement);
    const token = name => tokens.getPropertyValue(name).trim();
    const text = token('--text'), muted = token('--muted'), line = token('--line');
    const accent = token('--accent'), mono = token('--mono');
    const chart = echarts.init(document.getElementById('chart-archive'), null, { renderer: 'canvas' });
    chart.setOption({
      animation: false, backgroundColor: 'transparent', color: [accent, muted],
      textStyle: { color: text, fontFamily: mono },
      legend: { top: 0, textStyle: { color: muted, fontSize: parseFloat(token('--fs-label')) } },
      grid: { top: 45, right: 25, bottom: 40, left: 75 },
      tooltip: {
        trigger: 'item', confine: true, backgroundColor: token('--panel'), borderColor: line,
        textStyle: { color: text, fontSize: parseFloat(token('--fs-ui')) },
        formatter(params) {
          const point = histories[params.seriesIndex]?.[1][params.dataIndex];
          if (!point) return '';
          return `<div class="echarts-tooltip-custom">${escapeHtml(params.seriesName)}: ` +
            `${point.value.toFixed(0)} ms<br>${escapeHtml(point.shortSha)} · ` +
            `${escapeHtml(new Date(point.date).toLocaleString())}</div>`;
        },
      },
      xAxis: { type: 'time', axisLine: { lineStyle: { color: line } },
        axisLabel: { color: muted, fontFamily: mono } },
      yAxis: { type: 'value', min: 0, axisLabel: { color: muted, fontFamily: mono },
        splitLine: { lineStyle: { color: line, type: 'dashed' } } },
      series: histories.map(([label, history]) => ({
        name: label, type: 'line', showSymbol: false, smooth: false,
        data: history.map(point => [point.date, point.value]),
      })),
    });
    window.addEventListener('resize', () => chart.resize());
  } catch {
    status.textContent = 'The archived timings could not load. Download them below.';
  }
});
