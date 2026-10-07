// A fault is one injected failure the project was restored from. Counts are
// kept per operating system and template, so the total stays correct when
// either set grows.
const cellKey = cell => `${cell.os}/${cell.template}`;

export function rollbackTotal(cells) {
  return cells.reduce((sum, cell) => sum + cell.passed, 0);
}

export function rollbackHistory(entries) {
  if (!Array.isArray(entries)) throw new Error('Rollback history must be an array');
  const history = entries.map(entry => {
    if (!entry || !/^[a-f0-9]{40}$/i.test(entry.commit) ||
        typeof entry.date !== 'string' || !Number.isFinite(Date.parse(entry.date)) ||
        !Array.isArray(entry.cells) || !entry.cells.length ||
        entry.cells.some(cell => !cell || typeof cell.os !== 'string' || !cell.os.trim() ||
          typeof cell.template !== 'string' || !cell.template.trim() ||
          !Number.isSafeInteger(cell.passed) || cell.passed < 0) ||
        new Set(entry.cells.map(cellKey)).size !== entry.cells.length) {
      throw new Error('Invalid rollback history entry');
    }
    const cells = [...entry.cells].sort((a, b) => cellKey(a).localeCompare(cellKey(b)));
    return { ...entry, cells, value: rollbackTotal(cells), shortSha: entry.commit.slice(0, 7),
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
export function rollbackSeries(history) {
  const total = (entry, field, name) => {
    const rows = entry.cells.filter(cell => cell[field] === name);
    return rows.length ? rollbackTotal(rows) : null;
  };
  const names = field => [...new Set(history.flatMap(entry => entry.cells.map(cell => cell[field])))].sort();
  return [
    { name: 'Overall', type: 'line', data: history.map(entry => entry.value), lineStyle: { width: 3 } },
    ...['os', 'template'].flatMap(field => names(field).map(name => ({
      name, type: 'line', lineStyle: { width: 1, type: 'dashed' },
      data: history.map(entry => total(entry, field, name)) }))),
  ].map(series => ({ ...series, connectNulls: false, smooth: false, symbolSize: 6 }));
}
