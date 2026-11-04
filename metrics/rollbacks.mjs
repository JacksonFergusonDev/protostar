import { isRecord } from './metrics.mjs';

/**
 * @typedef {{os: string, template: string, passed: number}} RollbackCell
 * @typedef {{commit: string, date: string, cells: RollbackCell[]}} RollbackRun
 * @typedef {RollbackRun & {value: number, shortSha: string, url: string,
 *   scopeChanged: boolean, added: string[], removed: string[]}} RollbackPoint
 */

// A fault is one injected failure the project was restored from. Counts are
// kept per operating system and template, so the total stays correct when
// either set grows.
/** @param {RollbackCell} cell */
const cellKey = cell => `${cell.os}/${cell.template}`;

/** @param {RollbackCell[]} cells */
export function rollbackTotal(cells) {
  return cells.reduce((sum, cell) => sum + cell.passed, 0);
}

/** @param {unknown} cell @returns {cell is RollbackCell} */
function validCell(cell) {
  return isRecord(cell) && typeof cell.os === 'string' && !!cell.os.trim() &&
    typeof cell.template === 'string' && !!cell.template.trim() &&
    typeof cell.passed === 'number' && Number.isSafeInteger(cell.passed) && cell.passed >= 0;
}

/** @param {unknown} entries @returns {RollbackPoint[]} */
export function rollbackHistory(entries) {
  if (!Array.isArray(entries)) throw new Error('Rollback history must be an array');
  const history = entries.map(entry => {
    if (!isRecord(entry) || typeof entry.commit !== 'string' || !/^[a-f0-9]{40}$/i.test(entry.commit) ||
        typeof entry.date !== 'string' || !Number.isFinite(Date.parse(entry.date)) ||
        !Array.isArray(entry.cells) || !entry.cells.length ||
        !entry.cells.every(validCell) ||
        new Set(entry.cells.map(cellKey)).size !== entry.cells.length) {
      throw new Error('Invalid rollback history entry');
    }
    const cells = [...entry.cells].sort((a, b) => cellKey(a).localeCompare(cellKey(b)));
    return { ...entry, commit: entry.commit, date: entry.date, cells,
      value: rollbackTotal(cells), shortSha: entry.commit.slice(0, 7),
      url: `https://github.com/JacksonFergusonDev/protostar/commit/${entry.commit}` };
  }).sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  return history.map((entry, index) => {
    const previous = history[index - 1]?.cells.map(cellKey) || [];
    const current = entry.cells.map(cellKey);
    return { ...entry, scopeChanged: index > 0 && JSON.stringify(previous) !== JSON.stringify(current),
      added: current.filter(name => !previous.includes(name)),
      removed: previous.filter(name => !current.includes(name)) };
  });
}

// The overall total, then each operating system and each template summed over the rest.
/** @param {RollbackPoint[]} history @returns {import('./metrics.mjs').MetricSeries[]} */
export function rollbackSeries(history) {
  /** @param {RollbackPoint} entry @param {'os' | 'template'} field @param {string} name */
  const total = (entry, field, name) => {
    const rows = entry.cells.filter(cell => cell[field] === name);
    return rows.length ? rollbackTotal(rows) : null;
  };
  /** @param {'os' | 'template'} field */
  const names = field => [...new Set(history.flatMap(entry => entry.cells.map(cell => cell[field])))].sort();
  const fields = /** @type {const} */ (['os', 'template']);
  /** @type {import('./metrics.mjs').MetricSeries[]} */
  const series = [
    { name: 'Overall', type: 'line', data: history.map(entry => entry.value), lineStyle: { width: 3 } },
    ...fields.flatMap(field => names(field).map(
      /** @returns {import('./metrics.mjs').MetricSeries} */ name => ({
        name, type: 'line', lineStyle: { width: 1, type: 'dashed' },
        data: history.map(entry => total(entry, field, name)) }))),
  ];
  return series.map(series => ({ ...series, connectNulls: false, smooth: false, symbolSize: 6 }));
}
