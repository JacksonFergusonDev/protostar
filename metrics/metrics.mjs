/**
 * @typedef {import('echarts').LineSeriesOption & {name: string}} MetricSeries
 * @typedef {object} MetricPoint
 * @property {number} date
 * @property {number} value
 * @property {'ms'} unit
 * @property {string} shortSha
 * @property {string} message
 * @property {string} author
 * @property {string} url
 */

/** @param {unknown} value @returns {value is Record<string, unknown>} */
export function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

// The stored names identify measurements, not presentation labels.
/** @param {unknown[]} runs @param {string} name @returns {MetricPoint[]} */
export function metricHistory(runs, name) {
  /** @type {MetricPoint[]} */
  const history = [];
  for (const entry of runs) {
    if (!isRecord(entry)) continue;
    const commit = entry.commit;
    if (!isRecord(commit) || typeof commit.id !== 'string' || !/^[a-f0-9]{40}$/i.test(commit.id)) continue;
    const date = entry.date ?? (typeof commit.timestamp === 'string' ? Date.parse(commit.timestamp) : NaN);
    if (typeof date !== 'number' || !Number.isFinite(date)) continue;
    for (const bench of Array.isArray(entry.benches) ? entry.benches : []) {
      if (!isRecord(bench) || bench.name !== name || bench.unit !== 'ms' ||
          typeof bench.value !== 'number' || !Number.isFinite(bench.value) || bench.value < 0) continue;
      history.push({
        date,
        value: bench.value,
        unit: bench.unit,
        shortSha: commit.id.slice(0, 7),
        message: typeof commit.message === 'string' ? commit.message : '',
        author: authorName(commit.author) ?? authorName(commit.committer) ?? 'Unknown',
        url: `https://github.com/JacksonFergusonDev/protostar/commit/${commit.id}`,
      });
    }
  }
  return history.sort((a, b) => a.date - b.date);
}

/** @param {unknown} author */
function authorName(author) {
  return isRecord(author) && typeof author.name === 'string' ? author.name : undefined;
}

/** @param {unknown} value */
export function escapeHtml(value) {
  /** @type {Record<string, string>} */
  const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(value).replace(/[&<>"']/g, character => entities[character]);
}
