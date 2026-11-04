import { isRecord } from './metrics.mjs';

/**
 * @typedef {'wall' | 'cpu' | 'commands'} Measure
 * @typedef {'steady' | 'faster' | 'suspect' | 'regression'} Verdict
 * @typedef {{ratio: number, low: number, high: number}} Change
 * @typedef {{wall: number, protostar: number, cpu: number, commands: number,
 *   change: Change, status: Verdict}} Scenario
 * @typedef {{commit: string, baseline: string, date: string, os: string,
 *   scenarios: Record<string, Scenario>}} BenchmarkRun
 * @typedef {BenchmarkRun & {flagged: string[], shortSha: string, baselineSha: string,
 *   url: string, compareUrl: string}} BenchmarkPoint
 */

// One entry per night and operating system: the commit, the baseline it was
// compared with on the same runner, and each scenario's median timings (ms)
// with its change in Protostar's own CPU time and what that change means.
const SHA = /^[a-f0-9]{40}$/i;
const STATUSES = new Set(['steady', 'faster', 'suspect', 'regression']);
const TIMINGS = /** @type {const} */ (['wall', 'protostar', 'cpu', 'commands']);
const REPOSITORY = 'https://github.com/JacksonFergusonDev/protostar';

/** @type {Record<Measure, string>} */
export const MEASURES = {
  wall: 'Wall time',
  cpu: 'Protostar CPU time',
  commands: 'Time in commands',
};

/** @type {Record<Verdict, string>} */
export const VERDICTS = {
  steady: 'No change',
  faster: 'Faster',
  suspect: 'Slower once; measured again next run',
  regression: 'Slower twice; issue opened',
};

/** @param {string} os */
export function osName(os) {
  /** @type {Record<string, string>} */
  const names = { 'ubuntu-latest': 'Linux', 'macos-latest': 'macOS', 'windows-latest': 'Windows' };
  return names[os] ?? os;
}

/** @param {unknown} change @returns {change is Change} */
function validChange(change) {
  return isRecord(change) &&
    ['ratio', 'low', 'high'].every(name => typeof change[name] === 'number' && Number.isFinite(change[name]) && change[name] > 0);
}

/** @param {unknown} result @returns {result is Scenario} */
function validScenario(result) {
  if (!isRecord(result) || !validChange(result.change)) return false;
  const change = result.change;
  return TIMINGS.every(name => typeof result[name] === 'number' && Number.isFinite(result[name]) && result[name] >= 0) &&
    change.low <= change.ratio && change.ratio <= change.high && typeof result.status === 'string' && STATUSES.has(result.status);
}

/** @param {unknown} value @returns {value is Record<string, Scenario>} */
function validScenarios(value) {
  return isRecord(value) && Object.keys(value).length > 0 && Object.values(value).every(validScenario);
}

/** @param {unknown} entries @returns {BenchmarkPoint[]} */
export function benchmarkHistory(entries) {
  if (!Array.isArray(entries)) throw new Error('Benchmark history must be an array');
  return entries.map(entry => {
    const scenarios = isRecord(entry) ? entry.scenarios : undefined;
    if (!isRecord(entry) || typeof entry.commit !== 'string' || !SHA.test(entry.commit) ||
        typeof entry.baseline !== 'string' || !SHA.test(entry.baseline) ||
        typeof entry.date !== 'string' || !Number.isFinite(Date.parse(entry.date)) ||
        typeof entry.os !== 'string' || !entry.os.trim() ||
        !validScenarios(scenarios)) {
      throw new Error('Invalid benchmark history entry');
    }
    const flagged = Object.keys(scenarios).sort()
      .filter(name => scenarios[name].status === 'suspect' || scenarios[name].status === 'regression');
    return { ...entry, commit: entry.commit, baseline: entry.baseline, date: entry.date, os: entry.os,
      scenarios, flagged, shortSha: entry.commit.slice(0, 7), baselineSha: entry.baseline.slice(0, 7),
      url: `${REPOSITORY}/commit/${entry.commit}`,
      compareUrl: `${REPOSITORY}/compare/${entry.baseline}...${entry.commit}` };
  }).sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
}

/** @param {BenchmarkPoint[]} history */
export function systems(history) {
  return [...new Set(history.map(entry => entry.os))].sort();
}

// One line per scenario across one operating system's runs, gaps left empty.
/**
 * @param {BenchmarkPoint[]} history
 * @param {string} os
 * @param {Measure} measure
 * @returns {{runs: BenchmarkPoint[], series: import('./metrics.mjs').MetricSeries[]}}
 */
export function benchmarkSeries(history, os, measure) {
  const runs = history.filter(entry => entry.os === os);
  const names = [...new Set(runs.flatMap(run => Object.keys(run.scenarios)))].sort();
  return {
    runs,
    series: names.map(name => ({
      name, type: 'line', connectNulls: false, smooth: false, symbolSize: 6,
      data: runs.map(run => run.scenarios[name]?.[measure] ?? null),
    })),
  };
}

/** @param {Change} change */
export function changeText(change) {
  /** @param {number} value */
  const percent = value => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
  return `${percent(change.ratio - 1)} (${percent(change.low - 1)} to ${percent(change.high - 1)})`;
}
