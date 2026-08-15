<div class="protostar-hero">
  <div class="hero-content">
    <div class="protostar-kicker">High-velocity environment scaffolding</div>
    <h1>Launch faster. Drift less.</h1>
    <p class="protostar-muted">
      Protostar bootstraps development environments with a manifest-first,
      non-destructive architecture designed for speed, clarity, and low entropy.
    </p>
  </div>
  <div class="hero-visual">
    <img class="hero-img-light" src="./assets/favicon.svg" alt="Logo" />
    <img class="hero-img-dark" src="./assets/favicon.svg" alt="Logo" />
  </div>
</div>

## First light

Protostar is a modular CLI for initializing repositories and generating repeatable boilerplate.
It is designed to automate environment setup while staying out of your way.

<div class="protostar-grid">
  <div class="protostar-card">
    <h3>Manifest-first</h3>
    <p>State is declared before side effects execute, reducing partial failures and setup drift.</p>
  </div>
  <div class="protostar-card">
    <h3>Non-destructive</h3>
    <p>Existing files are respected, merged carefully, or left untouched when collisions occur.</p>
  </div>
  <div class="protostar-card">
    <h3>Actionable telemetry</h3>
    <p>Errors surface clearly, with useful diagnostics instead of opaque setup failures.</p>
  </div>
</div>

## Launch sequence

<div class="protostar-terminal">

```bash
mkdir orbital-mechanics-sim
cd orbital-mechanics-sim
protostar init --template scientific --pytest --markdownlint
```

</div>

![Headless Scaffolding](../assets/demo_headless.gif){ width="700" }

This initializes a working environment quickly while preserving explicit control over tools and context.

## Flight paths

- Head to **[Getting Started](./getting-started.md)** to get Protostar onto your system.
- Use **[Environment Initialization](./usage/init.md)** to learn the `init` workflow.
- Read **[Mechanics: Executor](../mechanics/executor.md)** to see how Protostar safely merges a `pyproject.toml` without breaking existing keys or stripping your comments
- Visit **[Mission Control](./mission-control/overview.md)** for architecture, philosophy, and advanced guidance.
