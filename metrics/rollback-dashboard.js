import { rollbackHistory, rollbackSeries } from './rollbacks.mjs';
import { escapeHtml } from './metrics.mjs';
import { loadCharts } from './charts.mjs';

const status = document.getElementById('rollback-status');
const count = value => typeof value !== 'number' ? 'N/A' : value.toLocaleString('en-US');
const scope = entry => entry.scopeChanged
  ? `Scope changed: ${[...entry.added.map(name => `added ${name}`), ...entry.removed.map(name => `removed ${name}`)].join('; ')}`
  : `${entry.cells.length} jobs`;

(async function() {
  const response = await fetch('rollback-history.json');
  if (response.status === 404) {
    status.textContent = 'No complete rollback runs published yet.';
    return;
  }
  if (!response.ok) throw new Error('History could not load');
  const history = rollbackHistory(await response.json());
  if (!history.length) {
    status.textContent = 'No complete rollback runs published yet.';
    return;
  }
  const latest = history.at(-1);
  document.getElementById('rollback-latest').textContent =
    `${count(latest.value)} faults restored · ${latest.shortSha} · ${new Date(latest.date).toLocaleString()}`;

  // The history keeps only green runs; the badge file says when the latest one failed.
  try {
    const badge = await fetch('rollback-latest.json');
    const message = badge.ok ? (await badge.json()).message : '';
    if (typeof message === 'string' && message.endsWith(' failing')) {
      document.getElementById('rollback-failing').textContent =
        `The most recent run had ${message}. The history below holds only runs in which every fault was restored.`;
    }
  } catch { /* The history alone is still true. */ }

  const systems = [...new Set(latest.cells.map(cell => cell.os))].sort();
  const templates = [...new Set(latest.cells.map(cell => cell.template))].sort();
  const header = document.getElementById('rollback-os');
  for (const system of systems) {
    const cell = document.createElement('th');
    cell.scope = 'col';
    cell.textContent = system;
    header.appendChild(cell);
  }
  const breakdown = document.getElementById('rollback-cells');
  for (const template of templates) {
    const row = breakdown.insertRow();
    row.insertCell().textContent = template;
    for (const system of systems) {
      const cell = latest.cells.find(item => item.os === system && item.template === template);
      row.insertCell().textContent = count(cell?.passed);
    }
  }
  const runs = document.getElementById('rollback-runs');
  for (const entry of history.slice(-30).reverse()) {
    const row = runs.insertRow();
    row.insertCell().textContent = new Date(entry.date).toLocaleString();
    row.insertCell().textContent = count(entry.value);
    const link = document.createElement('a');
    link.href = entry.url;
    link.textContent = entry.shortSha;
    const icon = document.createElement('span');
    icon.className = 'hs-icon hs-icon-brand-github';
    icon.setAttribute('aria-hidden', 'true');
    link.prepend(icon);
    row.insertCell().appendChild(link);
    row.insertCell().textContent = scope(entry);
  }
  document.getElementById('rollback-results').hidden = false;
  status.textContent = '';

  try {
    await loadCharts();
    await document.fonts.ready;
    const tokens = getComputedStyle(document.documentElement);
    const token = name => tokens.getPropertyValue(name).trim();
    const text = token('--text'), muted = token('--muted'), line = token('--line');
    const accent = token('--accent'), mono = token('--mono');
    const series = rollbackSeries(history);
    series[0].itemStyle = { color: accent };
    series[0].markLine = {
      symbol: 'none', silent: true,
      lineStyle: { color: muted, type: 'dashed' },
      label: { formatter: 'Scope changed', color: muted, fontFamily: mono },
      data: history.flatMap((entry, index) => entry.scopeChanged ? [{ xAxis: index }] : []),
    };
    const chart = echarts.init(document.getElementById('chart-rollback'), null, { renderer: 'canvas' });
    // Blend the house palette's hex tokens into canvas-compatible RGB colors.
    const colors = series.slice(1).map((_, index) => {
      const weight = (35 + (index % 5) * 13) / 100;
      const channels = [1, 3, 5].map(offset => Math.round(
        parseInt(accent.slice(offset, offset + 2), 16) * weight +
        parseInt(text.slice(offset, offset + 2), 16) * (1 - weight)));
      return `rgb(${channels.join(', ')})`;
    });
    chart.setOption({
      animation: false, backgroundColor: 'transparent',
      color: [accent, ...colors],
      textStyle: { color: text, fontFamily: mono },
      legend: { type: 'scroll', top: 0, textStyle: { color: muted, fontSize: parseFloat(token('--fs-label')) },
        selected: Object.fromEntries(series.map(item => [item.name, item.name === 'Overall'])) },
      grid: { top: 55, right: 25, bottom: 65, left: 75 },
      tooltip: {
        trigger: 'axis', confine: true, backgroundColor: token('--panel'), borderColor: line,
        textStyle: { color: text, fontSize: parseFloat(token('--fs-ui')) },
        formatter(params) {
          const entry = history[params[0]?.dataIndex];
          if (!entry) return '';
          return `<div class="echarts-tooltip-custom">${escapeHtml(entry.shortSha)} · ${escapeHtml(new Date(entry.date).toLocaleString())}<br>` +
            params.map(item => `${escapeHtml(item.seriesName)}: ${count(item.value)}`).join('<br>') +
            `<br>${escapeHtml(scope(entry))}</div>`;
        },
      },
      xAxis: { type: 'category', data: history.map(entry => entry.shortSha),
        axisLine: { lineStyle: { color: line } }, axisTick: { show: false },
        axisLabel: { color: muted, fontFamily: mono } },
      yAxis: { type: 'value', min: 0,
        axisLabel: { color: muted, fontFamily: mono },
        splitLine: { lineStyle: { color: line, type: 'dashed' } } },
      dataZoom: [
        { type: 'slider', bottom: 8, height: 24, startValue: Math.max(0, history.length - 100),
          endValue: history.length - 1, borderColor: 'transparent', backgroundColor: token('--panel'),
          fillerColor: line, handleStyle: { color: accent }, textStyle: { color: muted } },
        { type: 'inside', startValue: Math.max(0, history.length - 100), endValue: history.length - 1 },
      ],
      series,
    });
    chart.on('click', params => {
      const entry = history[params.dataIndex];
      if (entry) window.open(entry.url, '_blank', 'noopener,noreferrer');
    });
    window.addEventListener('resize', () => chart.resize());
  } catch {
    status.textContent = 'The rollback chart could not load. Counts and commit links remain available below.';
  }
})().catch(() => {
  status.textContent = 'Rollback history could not load. Please try again later.';
});
