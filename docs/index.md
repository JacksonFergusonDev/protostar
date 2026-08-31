---
title: Protostar
icon: material/home
hide:
  - navigation
  - toc
---

<div class="protostar-home" markdown>

<nav class="protostar-home-nav" aria-label="Primary site navigation">
  <a class="protostar-home-nav__docs" href="getting-started.md">Documentation</a>
  <a href="why-protostar.md">Why Protostar?</a>
  <a href="https://github.com/jacksonfergusondev/protostar">GitHub</a>
</nav>

<div class="protostar-hero">
  <div class="hero-content">
    <h1>Modular. Declarative. Fast.</h1>
    <p class="protostar-lede">
      Protostar bootstraps development environments with a manifest-first, non-destructive architecture designed for speed, clarity, and low entropy.
    </p>
  </div>
</div>

<div class="protostar-command-label">Install globally via uv</div>
<div class="protostar-install" aria-label="Install command">
  <code>uv tool install protostar</code>
  <button type="button" class="protostar-copy" data-copy="uv tool install protostar" aria-label="Copy install command">Copy command</button>
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
mkdir hyperdrive-cli
cd hyperdrive-cli
protostar init --template cli
```

</div>

<div class="protostar-asciinema" data-asciinema="./assets/demo_headless.cast"></div>

This initializes a working environment quickly while preserving explicit control over tools and context.

## Flight paths

- Read **[Why Protostar?](./why-protostar.md)** to see how it compares to general-purpose templaters like Copier.
- Head to **[Getting Started](./getting-started.md)** to get Protostar onto your system.
- Use **[Environment Initialization](./usage/init.md)** to learn the `init` workflow.
- Read **[Mechanics: Executor](./mechanics/executor.md)** to see how Protostar safely merges a `pyproject.toml` without breaking existing keys or stripping your comments
- Visit **[Developer Guide](./developer/overview.md)** for architecture, philosophy, and advanced guidance.
