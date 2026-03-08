window.BENCHMARK_DATA = {
  "lastUpdate": 1772935815727,
  "repoUrl": "https://github.com/JacksonFergusonDev/protostar",
  "entries": {
    "Protostar Initialization Latency": [
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1fddaefa15b1f1ad7a8865a68e00ac3c6b05a4b2",
          "message": "chore: migrate to hyperfine, decouple workflows, and add rigorous benchmark tier (#41)\n\n- Replace `pytest-benchmark` with `hyperfine` for accurate out-of-process latency measurement.\n- Split CI logic: `benchmark.yml` (state mutator with write perms) and `ci.yml` (read-only regression gatekeeper).\n- Add `test-benchmark-slower` to Makefile (30 warmup, 90 runs) to resolve hyperfine caching/outlier warnings.\n- Configure `benchmark.yml` to use the rigorous benchmark tier for high-precision historical tracking on `main`.\n- Keep `ci.yml` on the faster benchmark tier to maintain PR velocity.\n- Remove latency badge generation/push logic to prevent reporting volatile CI VM metrics as true performance.\n- Update README to reflect accurate local M3 benchmark metrics (~83.7 ms) and remove badge references.",
          "timestamp": "2026-03-07T18:09:07-08:00",
          "tree_id": "2b158d9991db5b0b9af5c889c3a3fcb7c4029681",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1fddaefa15b1f1ad7a8865a68e00ac3c6b05a4b2"
        },
        "date": 1772935814932,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Initialization Latency",
            "value": 130.56,
            "unit": "ms"
          }
        ]
      }
    ]
  }
}