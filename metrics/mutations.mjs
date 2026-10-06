// Percentages use the same decided-mutant denominator as mutation_report.py.
export function mutationScore(modules) {
  const caught = modules.reduce((sum, row) => sum + row.killed + row.timeout, 0);
  const decided = modules.reduce((sum, row) => sum + row.killed + row.timeout + row.survived + row.suspicious, 0);
  return decided ? 100 * caught / decided : null;
}

export function mutationHistory(entries) {
  if (!Array.isArray(entries)) throw new Error('Mutation history must be an array');
  const counts = ['killed', 'timeout', 'survived', 'suspicious', 'no_tests'];
  const history = entries.map(entry => {
    if (!entry || !/^[a-f0-9]{40}$/i.test(entry.commit) ||
        typeof entry.date !== 'string' || !Number.isFinite(Date.parse(entry.date)) ||
        !Array.isArray(entry.modules) || !entry.modules.length ||
        entry.modules.some(row => !row || typeof row.module !== 'string' || !row.module.trim() ||
          counts.some(key => !Number.isSafeInteger(row[key]) || row[key] < 0)) ||
        new Set(entry.modules.map(row => row.module)).size !== entry.modules.length) {
      throw new Error('Invalid mutation history entry');
    }
    const modules = [...entry.modules].sort((a, b) => a.module.localeCompare(b.module));
    return { ...entry, modules, value: mutationScore(modules), shortSha: entry.commit.slice(0, 7),
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

export function mutationSeries(history) {
  const names = [...new Set(history.flatMap(entry => entry.modules.map(row => row.module)))].sort();
  return [
    { name: 'Overall', type: 'line', data: history.map(entry => entry.value), lineStyle: { width: 3 } },
    ...names.map(name => ({ name, type: 'line', lineStyle: { width: 1, type: 'dashed' },
      data: history.map(entry => {
        const row = entry.modules.find(row => row.module === name);
        return row ? mutationScore([row]) : null;
      }) })),
  ].map(series => ({ ...series, connectNulls: false, smooth: false, symbolSize: 6 }));
}
