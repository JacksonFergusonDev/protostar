import { metricHistory, precedingAverage, escapeHtml } from './metrics.mjs';
(async function() {
  const data = window.BENCHMARK_DATA;
  if (!data || !data.entries) {
    document.getElementById('benchmark-status').textContent = 'Benchmark data could not load. Please try again later.';
    document.getElementById('btn-export-json').disabled = true;
    return;
  }

  // Wire export JSON button
  const exportBtn = document.getElementById('btn-export-json');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'protostar_benchmarks.json';
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  // Extract suite runs
  const suiteName = "Protostar Initialization Latency";
  const runs = data.entries[suiteName] || [];
  if (!runs.length) {
    document.getElementById('benchmark-status').textContent = 'No benchmark runs recorded yet.';
    return;
  }

  // Different benchmark names represent different measurements.
  const headlessData = metricHistory(runs, 'Protostar Headless Latency');
  const editorData = metricHistory(runs, 'Protostar Recipe Editor First Frame Latency');

  function updateKPI(cardPrefix, dataset) {
    const valElem = document.getElementById(`kpi-${cardPrefix}-val`);
    const comparison = document.getElementById(`kpi-${cardPrefix}-comparison`);
    const deltaElem = document.getElementById(`kpi-${cardPrefix}-delta`);
    const latest = dataset.at(-1);
    if (!latest) {
      valElem.textContent = 'N/A';
      comparison.textContent = 'No measurements recorded';
      deltaElem.hidden = true;
      return;
    }
    valElem.textContent = latest.value.toFixed(1);
    document.getElementById(`kpi-${cardPrefix}-measurement`).textContent =
      `Measured at ${latest.shortSha}, ${new Date(latest.date).toLocaleString()}`;
    const baseline = precedingAverage(dataset, 100);
    if (!baseline || baseline.value === 0) {
      comparison.textContent = 'No preceding baseline';
      deltaElem.hidden = true;
      return;
    }
    document.getElementById(`kpi-${cardPrefix}-avg`).textContent = baseline.value.toFixed(1);
    document.getElementById(`kpi-${cardPrefix}-count`).textContent = baseline.count;
    const delta = ((latest.value - baseline.value) / baseline.value) * 100;
    deltaElem.textContent = `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`;
  }

  updateKPI('headless', headlessData);
  updateKPI('editor', editorData);

  // Total runs & Latest SHA
  document.getElementById('kpi-total-runs').textContent = runs.length.toLocaleString();
  if (runs.length > 0) {
    const lastRun = [...runs].sort((a, b) => a.date - b.date).at(-1);
    const sha = lastRun.commit ? lastRun.commit.id.slice(0, 7) : 'latest';
    document.getElementById('kpi-latest-sha').textContent = sha;
    const runDate = new Date(lastRun.date || lastRun.commit.timestamp);
    document.getElementById('kpi-latest-date').textContent = runDate.toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }

  const table = document.getElementById('recent-measurements');
  for (const [label, dataset] of [['Help-command startup', headlessData], ['Recipe editor first frame', editorData]]) {
    for (const item of dataset.slice(-30).reverse()) {
      const row = table.insertRow();
      row.insertCell().textContent = label;
      row.insertCell().textContent = new Date(item.date).toLocaleString();
      row.insertCell().textContent = `${item.value.toFixed(2)} ms`;
      const link = document.createElement('a');
      link.href = item.url;
      link.textContent = item.shortSha;
      row.insertCell().appendChild(link);
    }
  }

  // ECharts Custom Theme Factory
  function createChartOptions(dataset, metricColor, softGradientColor) {
    const xCategories = dataset.map(d => d.shortSha);
    const yValues = dataset.map(d => d.value);

    return {
      backgroundColor: 'transparent',
      animationDuration: 600,
      grid: {
        top: 25,
        right: 25,
        bottom: 60,
        left: 55,
        containLabel: false
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(11, 15, 23, 0.95)',
        borderColor: metricColor,
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: '#f8fafc',
          fontSize: 12
        },
        extraCssText: 'box-shadow: 0 10px 25px rgba(0,0,0,0.6); border-radius: 8px; backdrop-filter: blur(8px);',
        formatter: function(params) {
          if (!params || !params.length) return '';
          const idx = params[0].dataIndex;
          const d = dataset[idx];
          if (!d) return '';

          const dateStr = new Date(d.date).toLocaleString(undefined, {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
          });

          let diffHtml = '';
          if (idx > 0 && dataset[idx - 1].value > 0) {
            const prev = dataset[idx - 1].value;
            const pct = ((d.value - prev) / prev) * 100;

            const sign = pct > 0 ? '+' : '';
            diffHtml = `<span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted); opacity:0.85;">(${sign}${pct.toFixed(1)}%)</span>`;
          }

          const msgEscaped = escapeHtml(d.message.split('\n')[0] || '');

          return `
            <div class="echarts-tooltip-custom">
              <div class="tooltip-header">
                <span class="tooltip-sha">${escapeHtml(d.shortSha)}</span>
                <span class="tooltip-date">${dateStr}</span>
              </div>
              <div class="tooltip-value-row">
                <span class="tooltip-val">${d.value.toFixed(2)} ${escapeHtml(d.unit)}</span>
                ${diffHtml}
              </div>
              <div class="tooltip-msg">${msgEscaped}</div>
              <div class="tooltip-author">
                <span>by ${escapeHtml(d.author)}</span>
                <span class="tooltip-action">&rarr; Click to open commit</span>
              </div>
            </div>
          `;
        }
      },
      xAxis: {
        type: 'category',
        data: xCategories,
        axisLine: {
          lineStyle: { color: 'rgba(255, 255, 255, 0.1)' }
        },
        axisTick: { show: false },
        axisLabel: {
          color: '#64748b',
          fontFamily: 'JetBrains Mono',
          fontSize: 11,
          interval: 'auto'
        }
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: {
          lineStyle: {
            color: 'rgba(255, 255, 255, 0.05)',
            type: 'dashed'
          }
        },
        axisLabel: {
          color: '#94a3b8',
          fontFamily: 'JetBrains Mono',
          fontSize: 11,
          formatter: '{value} ms'
        }
      },
      dataZoom: [
        {
          type: 'slider',
          show: true,
          height: 24,
          bottom: 8,
          borderColor: 'transparent',
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
          fillerColor: softGradientColor,
          handleStyle: {
            color: metricColor,
            borderColor: '#ffffff',
            borderWidth: 1,
            shadowBlur: 4,
            shadowColor: 'rgba(0,0,0,0.5)'
          },
          textStyle: {
            color: '#64748b',
            fontFamily: 'JetBrains Mono',
            fontSize: 10
          },
          startValue: Math.max(0, dataset.length - 100),
          endValue: dataset.length - 1
        },
        {
          type: 'inside',
          startValue: Math.max(0, dataset.length - 100),
          endValue: dataset.length - 1
        }
      ],
      series: [
        {
          name: 'Latency',
          type: 'line',
          data: yValues,
          smooth: false,
          showSymbol: dataset.length < 50,
          symbol: 'circle',
          symbolSize: 6,
          itemStyle: {
            color: metricColor
          },
          lineStyle: {
            width: 2.5,
            color: metricColor,
            shadowColor: metricColor,
            shadowBlur: 6
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: softGradientColor },
              { offset: 1, color: 'transparent' }
            ])
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: {
              color: 'rgba(255, 255, 255, 0.2)',
              type: 'dotted'
            },
            data: [
              {
                type: 'average',
                name: 'Avg',
                label: {
                  formatter: 'Avg: {c} ms',
                  fontFamily: 'JetBrains Mono',
                  fontSize: 10,
                  color: '#94a3b8'
                }
              }
            ]
          }
        }
      ]
    };
  }

  // Load the chart library after the page and summary can render.
  await new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/echarts@6.1.0/dist/echarts.min.js';
    script.integrity = 'sha384-C2iskrW/uPW46KzOjrvJIQo4YkV8lkD+QS0CrDN18IIPIpT/g2USu8bTP3nvmIAD';
    script.crossOrigin = 'anonymous';
    script.onload = resolve;
    script.onerror = reject;
    document.body.appendChild(script);
  });

  // Initialize ECharts instances
  const headlessDom = document.getElementById('chart-headless');
  const editorDom = document.getElementById('chart-editor');

  const chartHeadless = echarts.init(headlessDom, null, { renderer: 'canvas' });
  const chartEditor = echarts.init(editorDom, null, { renderer: 'canvas' });

  chartHeadless.setOption(createChartOptions(headlessData, '#22d3ee', 'rgba(34, 211, 238, 0.2)'));
  chartEditor.setOption(createChartOptions(editorData, '#a78bfa', 'rgba(167, 139, 250, 0.2)'));

  // Each metric has a different history length, so ranges stay independent.

  // Click to open commit on GitHub
  function bindChartClick(chart, dataset) {
    chart.on('click', function(params) {
      const item = dataset[params.dataIndex];
      if (item && item.url) {
        window.open(item.url, '_blank', 'noopener,noreferrer');
      }
    });
  }
  bindChartClick(chartHeadless, headlessData);
  bindChartClick(chartEditor, editorData);

  // Handle Range Toolbar buttons
  function setupRangeButtons(chartName, chartInstance, dataset) {
    const buttons = document.querySelectorAll(`.zoom-btn[data-chart="${chartName}"]`);
    buttons.forEach(btn => {
      btn.setAttribute('aria-pressed', String(btn.classList.contains('active')));
      btn.disabled = dataset.length === 0;
      btn.addEventListener('click', () => {
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        buttons.forEach(b => b.setAttribute('aria-pressed', String(b === btn)));

        const range = btn.getAttribute('data-range');
        let startVal = 0;
        const endVal = dataset.length - 1;

        if (range === '30') {
          startVal = Math.max(0, dataset.length - 30);
        } else if (range === '100') {
          startVal = Math.max(0, dataset.length - 100);
        } else {
          startVal = 0;
        }

        chartInstance.dispatchAction({
          type: 'dataZoom',
          startValue: startVal,
          endValue: endVal
        });
      });
    });
  }
  setupRangeButtons('headless', chartHeadless, headlessData);
  setupRangeButtons('editor', chartEditor, editorData);

  // Responsive Resize
  window.addEventListener('resize', () => {
    chartHeadless.resize();
    chartEditor.resize();
  });

})().catch(() => {
  document.getElementById('benchmark-status').textContent =
    'Charts could not load. Recent measurements and the JSON export remain available.';
});
