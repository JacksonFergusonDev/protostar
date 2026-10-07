import { MEASURES, VERDICTS, benchmarkHistory, benchmarkSeries, changeText, osName, systems }
  from './benchmarks.mjs';
import { escapeHtml } from './metrics.mjs';
import { loadCharts } from './charts.mjs';

const status = document.getElementById('benchmark-status');
const milliseconds = value => typeof value !== 'number' ? 'N/A' : `${value.toFixed(0)} ms`;
// The lines shown first; the legend turns on the rest.
const FEATURED = ['version', 'sync', 'init-lib', 'editor'];

function commitLink(href, text) {
  const link = document.createElement('a');
  link.href = href;
  link.textContent = text;
  const icon = document.createElement('span');
  icon.className = 'hs-icon hs-icon-brand-github';
  icon.setAttribute('aria-hidden', 'true');
  link.prepend(icon);
  return link;
}

function option(select, value, label) {
  const item = document.createElement('option');
  item.value = value;
  item.textContent = label;
  select.appendChild(item);
}

(async function() {
  const response = await fetch('benchmark-history.json');
  if (response.status === 404) {
    status.textContent = 'No benchmark runs published yet.';
    return;
  }
  if (!response.ok) throw new Error('History could not load');
  const history = benchmarkHistory(await response.json());
  if (!history.length) {
    status.textContent = 'No benchmark runs published yet.';
    return;
  }

  const oses = systems(history);
  document.getElementById('benchmark-latest').textContent = oses.map(os => {
    const latest = history.filter(entry => entry.os === os).at(-1);
    const flagged = latest.flagged.length ? `${latest.flagged.length} slower` : 'nothing slower';
    return `${osName(os)}: ${latest.shortSha}, ${flagged}`;
  }).join(' · ');

  const runs = document.getElementById('benchmark-runs');
  for (const entry of history.slice(-30).reverse()) {
    const row = runs.insertRow();
    row.insertCell().textContent = new Date(entry.date).toLocaleString();
    row.insertCell().textContent = osName(entry.os);
    row.insertCell().appendChild(commitLink(entry.url, entry.shortSha));
    row.insertCell().appendChild(commitLink(entry.compareUrl, entry.baselineSha));
    row.insertCell().textContent = entry.flagged.length ? entry.flagged.join(', ') : 'None';
  }

  const osSelect = document.getElementById('benchmark-os');
  const measureSelect = document.getElementById('benchmark-measure');
  for (const os of oses) option(osSelect, os, osName(os));
  for (const [measure, label] of Object.entries(MEASURES)) option(measureSelect, measure, label);
  osSelect.value = oses[0];
  measureSelect.value = 'wall';

  const table = document.getElementById('benchmark-scenarios');
  function showLatest() {
    const latest = history.filter(entry => entry.os === osSelect.value).at(-1);
    document.getElementById('benchmark-latest-range').textContent =
      `${osName(latest.os)} · ${latest.shortSha} against ${latest.baselineSha}`;
    table.replaceChildren();
    for (const [name, result] of Object.entries(latest.scenarios).sort(([a], [b]) => a.localeCompare(b))) {
      const row = table.insertRow();
      row.insertCell().textContent = name;
      row.insertCell().textContent = milliseconds(result.wall);
      row.insertCell().textContent = milliseconds(result.cpu);
      row.insertCell().textContent = milliseconds(result.commands);
      row.insertCell().textContent = changeText(result.change);
      row.insertCell().textContent = VERDICTS[result.status];
    }
  }
  showLatest();
  document.getElementById('benchmark-results').hidden = false;
  status.textContent = '';

  try {
    await loadCharts();
    await document.fonts.ready;
    const tokens = getComputedStyle(document.documentElement);
    const token = name => tokens.getPropertyValue(name).trim();
    const text = token('--text'), muted = token('--muted'), line = token('--line');
    const accent = token('--accent'), mono = token('--mono');
    const chart = echarts.init(document.getElementById('chart-benchmarks'), null, { renderer: 'canvas' });
    function draw() {
      const { runs: shown, series } = benchmarkSeries(history, osSelect.value, measureSelect.value);
      document.getElementById('benchmark-caption').textContent = `${MEASURES[measureSelect.value]} / ms`;
      // Blend the house palette's hex tokens into canvas-compatible RGB colors.
      const colors = series.map((_, index) => {
        const weight = (35 + (index % 5) * 13) / 100;
        const channels = [1, 3, 5].map(offset => Math.round(
          parseInt(accent.slice(offset, offset + 2), 16) * weight +
          parseInt(text.slice(offset, offset + 2), 16) * (1 - weight)));
        return `rgb(${channels.join(', ')})`;
      });
      const featured = series.some(item => FEATURED.includes(item.name));
      chart.setOption({
        animation: false, backgroundColor: 'transparent', color: [accent, ...colors],
        textStyle: { color: text, fontFamily: mono },
        legend: { type: 'scroll', top: 0, textStyle: { color: muted, fontSize: parseFloat(token('--fs-label')) },
          selected: Object.fromEntries(series.map(item =>
            [item.name, !featured || FEATURED.includes(item.name)])) },
        grid: { top: 55, right: 25, bottom: 65, left: 75 },
        tooltip: {
          trigger: 'axis', confine: true, backgroundColor: token('--panel'), borderColor: line,
          textStyle: { color: text, fontSize: parseFloat(token('--fs-ui')) },
          formatter(params) {
            const entry = shown[params[0]?.dataIndex];
            if (!entry) return '';
            return `<div class="echarts-tooltip-custom">${escapeHtml(entry.shortSha)} against ` +
              `${escapeHtml(entry.baselineSha)} · ${escapeHtml(new Date(entry.date).toLocaleString())}<br>` +
              params.map(item => `${escapeHtml(item.seriesName)}: ${escapeHtml(milliseconds(item.value))}`)
                .join('<br>') + '</div>';
          },
        },
        xAxis: { type: 'category', data: shown.map(entry => entry.shortSha),
          axisLine: { lineStyle: { color: line } }, axisTick: { show: false },
          axisLabel: { color: muted, fontFamily: mono } },
        yAxis: { type: 'value', min: 0, axisLabel: { color: muted, fontFamily: mono },
          splitLine: { lineStyle: { color: line, type: 'dashed' } } },
        dataZoom: [
          { type: 'slider', bottom: 8, height: 24, startValue: Math.max(0, shown.length - 100),
            endValue: shown.length - 1, borderColor: 'transparent', backgroundColor: token('--panel'),
            fillerColor: line, handleStyle: { color: accent }, textStyle: { color: muted } },
          { type: 'inside', startValue: Math.max(0, shown.length - 100), endValue: shown.length - 1 },
        ],
        series,
      }, true);
      chart.off('click');
      chart.on('click', params => {
        const entry = shown[params.dataIndex];
        if (entry) window.open(entry.compareUrl, '_blank', 'noopener,noreferrer');
      });
    }
    draw();
    osSelect.addEventListener('change', () => { showLatest(); draw(); });
    measureSelect.addEventListener('change', draw);
    window.addEventListener('resize', () => chart.resize());
  } catch {
    osSelect.addEventListener('change', showLatest);
    status.textContent = 'The benchmark chart could not load. Timings and commit links remain available below.';
  }
})().catch(() => {
  status.textContent = 'Benchmark history could not load. Please try again later.';
});
