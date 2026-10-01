---
title: Protostar
icon: material/home
description: "Simple Python project scaffolding that understands your tools."
template: home.html
hide:
  - navigation
  - toc
  - footer
---

<div class="ps-home">

<header class="ps-bar">
  <div class="ps-bar__inner">
    <a class="ps-bar__mark" href="./"><img src="assets/favicon.svg" alt="" width="30" height="30"> Protostar</a>
    <nav class="ps-console" aria-label="Primary">
      <a href="getting-started.md">Docs</a>
      <a class="ps-wide" href="why-protostar.md">Why Protostar?</a>
      <a class="ps-wide" href="usage/cli-reference.md">Reference</a>
    </nav>
    <div class="ps-bar__end">
      <button type="button" class="ps-bar__icon" data-ps-search aria-label="Search the documentation">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>
      </button>
      <button type="button" class="ps-bar__icon" data-ps-theme aria-label="Switch color scheme">
        <svg class="ps-icon-dark" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"/></svg>
        <svg class="ps-icon-light" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></svg>
      </button>
      <a class="ps-bar__link" href="https://github.com/jacksonfergusondev/protostar"><span class="hs-icon hs-icon-brand-github" aria-hidden="true"></span>GitHub</a>
      <a class="ps-bar__link ps-wide" href="https://jacksonferguson.me"><img src="house/icons/jacksonferguson.svg" alt="" width="18" height="18">jacksonferguson.me</a>
    </div>
  </div>
</header>

<section class="ps-hero">
  <canvas class="ps-field" aria-hidden="true"></canvas>
  <button type="button" class="ps-motion" data-ps-motion aria-pressed="false" aria-label="Pause background animation" hidden><span data-ps-motion-label>Pause motion</span><span class="hs-icon hs-icon-pause" aria-hidden="true"></span></button>
  <h1>Simple Python project scaffolding that understands your tools.</h1>
  <p class="ps-hero__lede">Pick your tools, and Protostar writes their configuration, hooks, and CI. When your template improves, updates merge into your files by meaning, so your edits stay.</p>
  <div class="hs-install-header">
    <span class="hs-install-label">Install globally</span>
    <div class="hs-install-toggle" role="tablist" aria-label="Installation method">
      <button type="button" role="tab" aria-selected="true" aria-controls="protostar-install" class="hs-install-tab is-active" data-command="uv tool install protostar">uv</button>
      <button type="button" role="tab" aria-selected="false" aria-controls="protostar-install" class="hs-install-tab" data-command="brew install jacksonfergusondev/tap/protostar">brew</button>
    </div>
  </div>
  <div class="hs-install" id="protostar-install" aria-label="Install command">
    <code>uv tool install protostar</code>
    <button type="button" class="hs-install-copy" data-copy="uv tool install protostar" aria-label="Copy install command">Copy<span class="hs-install-copy-long"> command</span></button>
  </div>
  <div class="ps-hero__actions">
    <a class="hs-button hs-button--primary" href="getting-started.md">Get started<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a>
    <a class="ps-text-link" href="why-protostar.md">Why Protostar?<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a>
  </div>
  <nav class="ps-hero__bottom" aria-label="On this page">
    <a href="#init">01 / INIT<span class="hs-icon hs-icon-arrow-down" aria-hidden="true"></span></a>
    <a href="#sync">02 / SYNC<span class="hs-icon hs-icon-arrow-down" aria-hidden="true"></span></a>
    <a href="#commands">03 / COMMANDS<span class="hs-icon hs-icon-arrow-down" aria-hidden="true"></span></a>
    <a href="#guarantees">04 / GUARANTEES<span class="hs-icon hs-icon-arrow-down" aria-hidden="true"></span></a>
    <a href="#docs">05 / DOCS<span class="hs-icon hs-icon-arrow-down" aria-hidden="true"></span></a>
  </nav>
</section>

<section class="ps-section ps-init" id="init" aria-labelledby="ps-init">
  <div class="ps-init__text">
    <div class="hs-section-marker"><span>01 / INIT</span></div>
    <h2 id="ps-init">Choose your tools in a recipe editor. Review every file before it's written.</h2>
    <p class="ps-section__lede">Run <code>protostar init</code> in an empty folder, or in a project you already have. Pick a template, switch tools on and off, and watch the file tree change. Nothing touches the disk until you apply the review.</p>
    <ul class="ps-tags" aria-label="Some of the tools Protostar configures">
      <li>ruff</li><li>mypy</li><li>ty</li><li>pyrefly</li><li>pytest</li><li>prek</li><li>pre-commit</li><li>GitHub Actions</li><li>Renovate</li><li>Codecov</li><li>Zensical</li><li>Read the Docs</li><li>Docker</li><li>just</li><li>direnv</li><li>rumdl</li><li>Commitizen</li><li>AGENTS.md</li>
    </ul>
    <p class="ps-note"><a class="ps-text-link" href="usage/tooling-matrix.md">Every tool and its flag<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></p>
  </div>
  <div class="hs-terminal ps-demo">
    <div class="hs-terminal-bar">
      <div class="hs-terminal-dots" aria-hidden="true">
        <span class="dot dot-close"></span>
        <span class="dot dot-minimize"></span>
        <span class="dot dot-maximize"></span>
      </div>
      <span class="hs-terminal-title">protostar init</span>
    </div>
    <div class="hs-terminal-screen" data-asciinema="assets/demo_init_interactive.cast">
      <noscript><a href="assets/demo_init_interactive.cast">Download the terminal recording</a></noscript>
    </div>
  </div>
</section>

<section class="ps-section" id="sync" aria-labelledby="ps-sync">
  <div class="hs-section-marker"><span>02 / SYNC</span></div>
  <h2 id="ps-sync">Template updates merge by meaning. Your edits stay.</h2>
  <p class="ps-section__lede">Protostar knows <code>pyproject.toml</code> key by key, workflows job by job, and dependencies through uv. An update that would collide in a line-based merge simply combines. A real conflict is one setting, with both sides and a command for each choice.</p>
  <div class="ps-merge">
    <figure class="ps-merge__pane">
      <figcaption><span>YOUR PROJECT</span><span class="ps-merge__file">pyproject.toml</span></figcaption>
      <div class="ps-code" role="img" aria-label="Your pyproject.toml, with line-length changed to 100">
        <div class="ps-code__line"><span class="tk-table">[tool.ruff]</span></div>
        <div class="ps-code__line is-yours"><span class="tk-key">line-length</span> = <span class="tk-num">100</span>  <span class="tk-comment"># wide monitors</span></div>
        <div class="ps-code__line"> </div>
        <div class="ps-code__line"><span class="tk-table">[tool.ruff.lint]</span></div>
        <div class="ps-code__line"><span class="tk-key">select</span> = [<span class="tk-str">"E"</span>, <span class="tk-str">"F"</span>, <span class="tk-str">"I"</span>]</div>
      </div>
    </figure>
    <figure class="ps-merge__pane">
      <figcaption><span>TEMPLATE UPDATE</span><span class="ps-merge__file">pyproject.toml</span></figcaption>
      <div class="ps-code" role="img" aria-label="The template's new pyproject.toml, which adds extend-select">
        <div class="ps-code__line"><span class="tk-table">[tool.ruff]</span></div>
        <div class="ps-code__line"><span class="tk-key">line-length</span> = <span class="tk-num">88</span></div>
        <div class="ps-code__line"> </div>
        <div class="ps-code__line"><span class="tk-table">[tool.ruff.lint]</span></div>
        <div class="ps-code__line"><span class="tk-key">select</span> = [<span class="tk-str">"E"</span>, <span class="tk-str">"F"</span>, <span class="tk-str">"I"</span>]</div>
        <div class="ps-code__line is-added"><span class="tk-key">extend-select</span> = [<span class="tk-str">"B"</span>]</div>
      </div>
    </figure>
    <figure class="ps-merge__pane ps-merge__pane--result">
      <figcaption><span>AFTER PROTOSTAR SYNC</span><span class="ps-merge__file">pyproject.toml</span></figcaption>
      <div class="ps-code" role="img" aria-label="The merged pyproject.toml: your line-length and comment are kept, and extend-select is added">
        <div class="ps-code__line"><span class="tk-table">[tool.ruff]</span></div>
        <div class="ps-code__line is-yours"><span class="tk-key">line-length</span> = <span class="tk-num">100</span>  <span class="tk-comment"># wide monitors</span><span class="ps-code__tag">kept</span></div>
        <div class="ps-code__line"> </div>
        <div class="ps-code__line"><span class="tk-table">[tool.ruff.lint]</span></div>
        <div class="ps-code__line"><span class="tk-key">select</span> = [<span class="tk-str">"E"</span>, <span class="tk-str">"F"</span>, <span class="tk-str">"I"</span>]</div>
        <div class="ps-code__line is-added"><span class="tk-key">extend-select</span> = [<span class="tk-str">"B"</span>]<span class="ps-code__tag">new</span></div>
      </div>
    </figure>
  </div>
  <p class="ps-note">Your line length and its comment stay where they are, and <code>protostar status</code> lists the kept edit with the command that takes the template's value instead. <a class="ps-text-link" href="usage/lifecycle.md">How updates work<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></p>
</section>

<section class="ps-section" id="commands" aria-labelledby="ps-commands">
  <div class="hs-section-marker"><span>03 / COMMANDS</span></div>
  <h2 id="ps-commands">One lifecycle, from the first commit to the next template release.</h2>
  <dl class="ps-commands">
    <div><dt><code>protostar init</code></dt><dd>Choose a template and tools, preview every file, and review the changes before anything is written.</dd></div>
    <div><dt><code>protostar status</code></dt><dd>See what an update would change, every conflict, and each edit of yours that stays.</dd></div>
    <div><dt><code>protostar diff</code></dt><dd>Read those changes line by line. Like <code>status</code>, it never writes a file.</dd></div>
    <div><dt><code>protostar sync</code></dt><dd>Apply the update. Safe changes land, conflicts wait for your choice, and your edits stay.</dd></div>
    <div><dt><code>protostar sync --to latest</code></dt><dd>Move to the template's newest release and review it like any other update.</dd></div>
    <div><dt><code>protostar sync --check</code></dt><dd>Fail CI when the project has fallen behind its recipe or has an open conflict.</dd></div>
    <div><dt><code>protostar guide</code></dt><dd>Show how to run, test, check, and document this project.</dd></div>
  </dl>
  <p class="ps-note"><a class="ps-text-link" href="usage/cli-reference.md">CLI reference<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></p>
</section>

<section class="ps-section" id="guarantees" aria-labelledby="ps-guarantees">
  <div class="hs-section-marker"><span>04 / GUARANTEES</span></div>
  <h2 id="ps-guarantees">Nothing changes that you didn't see, and nothing stops halfway.</h2>
  <ul class="ps-principles">
    <li><h3>Rolls back on failure</h3><p>If a run fails or you press <kbd>Ctrl</kbd>+<kbd>C</kbd>, every file Protostar wrote goes back to its original bytes.</p><a class="ps-text-link" href="usage/rollback.md">How rollback works<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></li>
    <li><h3>Merges, never overwrites</h3><p>Existing files are merged, not replaced. Where your content and the template disagree, yours stays until you choose.</p><a class="ps-text-link" href="usage/lifecycle.md#resolve-conflicts">How conflicts are resolved<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></li>
    <li><h3>Adopts existing projects</h3><p>Point it at a repository you already have. It reads the tools you use, proposes each change, and lets you keep all of yours.</p><a class="ps-text-link" href="usage/init.md#existing-projects">Set up an existing project<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></li>
    <li><h3>Asks before running commands</h3><p>A template you haven't trusted runs no command until you confirm it, on <code>init</code> and on <code>sync</code>.</p><a class="ps-text-link" href="usage/templates.md#security-model-the-remote-trust-dialog">How template trust works<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></li>
    <li><h3>Previews are read-only</h3><p><code>--dry-run</code>, <code>status</code>, and <code>diff</code> never write a file or run a command.</p><a class="ps-text-link" href="usage/lifecycle.md#review-apply-repeat">Preview project changes<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></li>
    <li><h3>Built for automation</h3><p><code>--json</code> puts one payload on stdout and never prompts, so scripts, CI, and coding agents can drive every command.</p><a class="ps-text-link" href="usage/agent-interface.md">The machine interface<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></a></li>
  </ul>
</section>

<section class="ps-section" id="docs" aria-labelledby="ps-docs">
  <div class="hs-section-marker"><span>05 / DOCS</span></div>
  <h2 id="ps-docs">Explore the docs.</h2>
  <nav class="ps-index" aria-label="Documentation">
    <a href="installation.md"><strong>Installation<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>Protostar, uv, and git on macOS, Linux, or Windows.</span></a>
    <a href="first-project.md"><strong>Your first project<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>From nothing installed to a project you've run, changed, and checked.</span></a>
    <a href="getting-started.md"><strong>Getting started<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>The recipe editor, headless runs, and shell completion.</span></a>
    <a href="why-protostar.md"><strong>Why Protostar?<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>How it compares to Copier, Cookiecutter, and friends.</span></a>
    <a href="usage/templates.md"><strong>Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>Built-in project shapes, and your team's from a Git repository.</span></a>
    <a href="usage/authoring-templates.md"><strong>Authoring templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>Write, check, version, and publish your own.</span></a>
    <a href="usage/lifecycle.md"><strong>Project lifecycle<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>Status, diff, sync, conflicts, and kept edits.</span></a>
    <a href="usage/agent-interface.md"><strong>Agents and machines<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>JSON payloads, exit codes, and headless runs.</span></a>
    <a href="developer/overview.md"><strong>Developer guide<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span></strong><span>Contribute to Protostar and learn how its engine works.</span></a>
  </nav>
</section>

</div>

<script type="module">
import { initCopyCommands } from "./house/js/copy-command.js";

// The landing page hides the theme's header; these drive its controls.
const home = document.querySelector(".ps-home");
if (home && !home.dataset.psReady) {
  home.dataset.psReady = "true";
  initCopyCommands(home);
  home.querySelector("[data-ps-search]").addEventListener("click", () => {
    document.querySelector(".md-search__button")?.click();
  });
  home.querySelector("[data-ps-theme]").addEventListener("click", () => {
    document.querySelector("[data-md-component=palette] label:not([hidden])")?.click();
  });

  // The background field loads after the page is up, so the first screen is text.
  const startField = () => {
    const idle = window.requestIdleCallback ?? ((callback) => window.setTimeout(callback, 200));
    idle(() => {
      import("./javascripts/field.js")
        .then(({ startField }) => startField(home.querySelector(".ps-field"), home.querySelector("[data-ps-motion]")))
        .catch(() => {});
    });
  };
  if (document.readyState === "complete") {
    startField();
  } else {
    window.addEventListener("load", startField, { once: true });
  }
}
</script>
