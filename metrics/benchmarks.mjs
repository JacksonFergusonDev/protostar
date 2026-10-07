// One entry per night and operating system: the commit, the baseline it was
// compared with on the same runner, and each scenario's median timings (ms)
// with its change in Protostar's own CPU time and what that change means.
const SHA = /^[a-f0-9]{40}$/i;
const STATUSES = new Set(['steady', 'faster', 'suspect', 'regression']);
const TIMINGS = ['wall', 'protostar', 'cpu', 'commands'];
const REPOSITORY = 'https://github.com/JacksonFergusonDev/protostar';

export const MEASURES = {
  wall: 'Wall time',
  cpu: 'Protostar CPU time',
  commands: 'Time in commands',
};

export const VERDICTS = {
  steady: 'No change',
  faster: 'Faster',
  suspect: 'Slower once; measured again next run',
  regression: 'Slower twice; issue opened',
};

export function osName(os) {
  return { 'ubuntu-latest': 'Linux', 'macos-latest': 'macOS', 'windows-latest': 'Windows' }[os] ?? os;
}

function validScenario(result) {
  const change = result?.change;
  return result && TIMINGS.every(name => Number.isFinite(result[name]) && result[name] >= 0) &&
    change && ['ratio', 'low', 'high'].every(name => Number.isFinite(change[name]) && change[name] > 0) &&
    change.low <= change.ratio && change.ratio <= change.high && STATUSES.has(result.status);
}

export function benchmarkHistory(entries) {
  if (!Array.isArray(entries)) throw new Error('Benchmark history must be an array');
  return entries.map(entry => {
    const scenarios = entry?.scenarios;
    if (!entry || !SHA.test(entry.commit) || !SHA.test(entry.baseline) ||
        typeof entry.date !== 'string' || !Number.isFinite(Date.parse(entry.date)) ||
        typeof entry.os !== 'string' || !entry.os.trim() ||
        !scenarios || typeof scenarios !== 'object' || Array.isArray(scenarios) ||
        !Object.keys(scenarios).length || !Object.values(scenarios).every(validScenario)) {
      throw new Error('Invalid benchmark history entry');
    }
    const flagged = Object.keys(scenarios).sort()
      .filter(name => scenarios[name].status === 'suspect' || scenarios[name].status === 'regression');
    return { ...entry, flagged, shortSha: entry.commit.slice(0, 7), baselineSha: entry.baseline.slice(0, 7),
      url: `${REPOSITORY}/commit/${entry.commit}`,
      compareUrl: `${REPOSITORY}/compare/${entry.baseline}...${entry.commit}` };
  }).sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
}

export function systems(history) {
  return [...new Set(history.map(entry => entry.os))].sort();
}

// One line per scenario across one operating system's runs, gaps left empty.
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

export function changeText(change) {
  const percent = value => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
  return `${percent(change.ratio - 1)} (${percent(change.low - 1)} to ${percent(change.high - 1)})`;
}
