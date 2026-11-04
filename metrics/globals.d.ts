// Runtime scripts are loaded from the CDN and archived data.js, not the local dependencies.
declare const echarts: typeof import('echarts');

interface Window {
  BENCHMARK_DATA?: { entries?: Record<string, unknown[]> };
}
