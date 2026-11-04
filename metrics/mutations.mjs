import { isRecord } from './metrics.mjs';

/**
 * @typedef {{module: string, killed: number, timeout: number, survived: number,
 *   suspicious: number, no_tests: number}} ModuleResult
 * @typedef {{commit: string, date: string, modules: ModuleResult[]}} MutationRun
 * @typedef {MutationRun & {value: number | null, shortSha: string, url: string,
 *   scopeChanged: boolean, added: string[], removed: string[]}} MutationPoint
 */

// Percentages use the same decided-mutant denominator as mutation_report.py.
/** @param {ModuleResult[]} modules */
export function mutationScore(modules) {
  const caught = modules.reduce((sum, row) => sum + row.killed + row.timeout, 0);
  const decided = modules.reduce((sum, row) => sum + row.killed + row.timeout + row.survived + row.suspicious, 0);
  return decided ? 100 * caught / decided : null;
}

/** @param {unknown} row @returns {row is ModuleResult} */
function validModule(row) {
  const counts = ['killed', 'timeout', 'survived', 'suspicious', 'no_tests'];
  return isRecord(row) && typeof row.module === 'string' && !!row.module.trim() &&
    counts.every(key => typeof row[key] === 'number' && Number.isSafeInteger(row[key]) && row[key] >= 0);
}

/** @param {unknown} entries @returns {MutationPoint[]} */
export function mutationHistory(entries) {
  if (!Array.isArray(entries)) throw new Error('Mutation history must be an array');
  const history = entries.map(entry => {
    if (!isRecord(entry) || typeof entry.commit !== 'string' || !/^[a-f0-9]{40}$/i.test(entry.commit) ||
        typeof entry.date !== 'string' || !Number.isFinite(Date.parse(entry.date)) ||
        !Array.isArray(entry.modules) || !entry.modules.length ||
        !entry.modules.every(validModule) ||
        new Set(entry.modules.map(row => row.module)).size !== entry.modules.length) {
      throw new Error('Invalid mutation history entry');
    }
    const modules = [...entry.modules].sort((a, b) => a.module.localeCompare(b.module));
    return { ...entry, commit: entry.commit, date: entry.date, modules,
      value: mutationScore(modules), shortSha: entry.commit.slice(0, 7),
      url: `https://github.com/JacksonFergusonDev/protostar/commit/${entry.commit}` };
  }).sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  return history.map((entry, index) => {
    const previous = history[index - 1]?.modules.map(row => row.module) || [];
    const current = entry.modules.map(row => row.module);
    return { ...entry, scopeChanged: index > 0 && JSON.stringify(previous) !== JSON.stringify(current),
      added: current.filter(name => !previous.includes(name)),
      removed: previous.filter(name => !current.includes(name)) };
  });
}

/** @param {MutationPoint[]} history @returns {import('./metrics.mjs').MetricSeries[]} */
export function mutationSeries(history) {
  const names = [...new Set(history.flatMap(entry => entry.modules.map(row => row.module)))].sort();
  /** @type {import('./metrics.mjs').MetricSeries[]} */
  const series = [
    { name: 'Overall', type: 'line', data: history.map(entry => entry.value), lineStyle: { width: 3 } },
    ...names.map(/** @returns {import('./metrics.mjs').MetricSeries} */ name => ({
      name, type: 'line', lineStyle: { width: 1, type: 'dashed' },
      data: history.map(entry => {
        const row = entry.modules.find(row => row.module === name);
        return row ? mutationScore([row]) : null;
      }) })),
  ];
  return series.map(series => ({ ...series, connectNulls: false, smooth: false, symbolSize: 6 }));
}
