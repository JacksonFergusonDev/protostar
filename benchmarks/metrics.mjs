// The stored names identify measurements, not presentation labels.
export function metricHistory(runs, name) {
  const history = [];
  for (const entry of runs) {
    const commit = entry.commit;
    const date = entry.date ?? Date.parse(commit?.timestamp);
    if (!commit || !/^[a-f0-9]{40}$/i.test(commit.id) || !Number.isFinite(date)) continue;
    for (const bench of entry.benches ?? []) {
      if (bench.name !== name || bench.unit !== 'ms' ||
          !Number.isFinite(bench.value) || bench.value < 0) continue;
      history.push({
        date,
        value: bench.value,
        unit: bench.unit,
        shortSha: commit.id.slice(0, 7),
        message: commit.message ?? '',
        author: commit.author?.name ?? commit.committer?.name ?? 'Unknown',
        url: `https://github.com/JacksonFergusonDev/protostar/commit/${commit.id}`,
      });
    }
  }
  return history.sort((a, b) => a.date - b.date);
}

export function precedingAverage(history, count) {
  const preceding = history.slice(Math.max(0, history.length - count - 1), -1);
  if (!preceding.length) return null;
  return {
    value: preceding.reduce((sum, item) => sum + item.value, 0) / preceding.length,
    count: preceding.length,
  };
}

export function escapeHtml(value) {
  const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(value).replace(/[&<>"']/g, character => entities[character]);
}
