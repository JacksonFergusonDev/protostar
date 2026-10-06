let loading;
export function loadCharts() {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/echarts@6.1.0/dist/echarts.min.js';
    script.integrity = 'sha384-C2iskrW/uPW46KzOjrvJIQo4YkV8lkD+QS0CrDN18IIPIpT/g2USu8bTP3nvmIAD';
    script.crossOrigin = 'anonymous';
    script.onload = resolve;
    script.onerror = reject;
    document.body.appendChild(script);
  });
  return loading;
}
