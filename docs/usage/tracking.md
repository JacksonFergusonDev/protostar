---
description: "How Protostar tells its own content from yours, and decides what an update may change: the ideas behind status, sync, and every decision they show."
---

# How Protostar Tracks Your Files

Protostar can update a project years after creating it without overwriting your work. This page explains how, in the words the rest of the docs use. Once these ideas are clear, every screen and message `status` and `sync` show follows from them.

## Two Records

A tracked project carries two records. Commit both.

| Record | Where | What it holds |
| :--- | :--- | :--- |
| **The recipe** | `[tool.protostar]` in `pyproject.toml` | What you asked for: the template, the tools you turned on or off, its options, tier, and variables. See [Project Recipes](project-recipes.md). |
| **The lock** | `protostar.lock` | What Protostar actually wrote: for each file, the version of its content it last applied, and the Protostar release that wrote it. |

The recipe says what the project should be; the lock says what Protostar last did about it. Editing the recipe, upgrading Protostar, or moving to a new template release changes what the project should be, and `protostar status` shows the difference.

## Protostar's Content and Yours

The lock is how Protostar tells its own content from yours. A setting, file, or dependency Protostar wrote, and recorded in the lock, is **Protostar's**. Everything else is **yours**: what you added, and what the project had before Protostar arrived, even when it is identical to what Protostar would write.

Protostar keeps its own content current. When it would change content of yours, it says so first: the change is a **proposed change**, listed in the review, and you can keep it out.

"Content" means the smallest piece each file has a meaning for:

- In `pyproject.toml` and other configuration files, a single key or table. Lists such as Ruff's `select` are a set of members.
- In a GitHub Actions workflow, a job, or a step within one.
- In the hook configuration, a hook.
- In a `justfile`, a `Dockerfile`, or a managed block of `AGENTS.md` or `CONTRIBUTING.md`, a line.
- A dependency, through uv. `uv.lock` is never merged as text.

So your own key in `[tool.ruff]` sits beside Protostar's keys, each with its own owner.

## How an Update Is Decided

For each piece of Protostar's content, an update compares three versions: what Protostar last applied (from the lock), what your file holds now, and what the update wants.

| You changed it | The update changed it | What happens |
| :--- | :--- | :--- |
| No | Yes | The update applies. |
| Yes | No | Your edit stays. It's a **kept edit**, and `sync --check` still passes. |
| Yes | Yes, differently | A **conflict**: your version stays until you choose. |
| You deleted it | No | It stays deleted. |
| You deleted it | Yes | A conflict: it stays deleted until you choose. |
| No | It's gone from the update | It's removed. |
| Yes | It's gone from the update | A conflict: your edited copy stays until you choose to keep or remove it. |

Content leaves an update when you turn a tool off, choose a template option that drops it, or move to a template release that no longer ships it. Protostar takes back what it added, and nothing else.

Starter files are the exception. A file a template ships in `[files]` or `template/` is written once and then belongs to the project, so later releases never change it. A template release can move or retire one with a [migration](releasing-templates.md#migrations).

## The Three Kinds of Decision

Every decision `status`, `sync`, and the change review show is one of three kinds:

| Kind | What it is | What happens unless you choose |
| :--- | :--- | :--- |
| **Conflict** | You and the update both changed the same thing, or the update can't apply without changing something of yours. | Your version stays, and `sync --check` fails until you choose. |
| **Proposed change** | A change into a file Protostar has never written to, such as the keys it adds to your existing `pyproject.toml` the first time you run `init`. | It applies. |
| **Kept edit** | An edit or deletion of yours to Protostar's content, which the update didn't change. | It stays, and `sync --check` passes. |

Each decision has two sides: **yours** and **the update's**. Choosing yours keeps your content; choosing the update's writes Protostar's. For overlapping lines in a text file, you can also keep both. Either way, the update becomes Protostar's new record for that content, so the same decision never comes back for the same update. If you keep yours, a later update that changes it again shows a new decision.

Keeping a proposed change out works the same way: Protostar records its version without writing it, so it reads as your deletion from then on, and you can take it later.

Each decision has an `id`, derived from its location and both sides. `protostar status` prints the command for each choice, such as `protostar sync --resolve 76d476390115=desired`, and an `id` stops matching as soon as either side changes, so a choice can never apply to content you didn't review. See [Resolve Conflicts](lifecycle.md#resolve-conflicts).

## Adopting a File

A file Protostar never wrote, such as a `justfile` you already had, is yours, and Protostar can't merge into it. It shows as a conflict. Choosing **Keep mine** adopts it: the file stays exactly as it is, and from then on Protostar treats it as its own content with your edits, merging updates into it line by line. Choosing **Take update** replaces it.

Choosing yours is the only way Protostar takes over content you wrote. **Keep all mine**, in the change review, chooses yours for every decision at once: the project stays exactly as it is, and each file Protostar couldn't merge into is adopted.

## Words in JSON

The JSON payloads use shorter names for the same ideas:

| JSON | Means |
| :--- | :--- |
| `local` | Your side |
| `desired` | The update's side |
| `both` | Keep both, for overlapping lines |
| `base` | What Protostar last applied |
| `review.conflicts` | Conflicts still open |
| `review.proposals` | Proposed changes |
| `review.preserved` | Kept edits |
| `review.resolved` | Decisions settled in this run |

Each decision also carries a `reason`:

--8<-- "table_schema_reasons.md"

See the [machine interface](agent-interface.md) for the full payloads.

## Next Steps

- **[Project Lifecycle<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](lifecycle.md):** Review, apply, and settle updates with `status`, `diff`, and `sync`.
- **[Project Recipes<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](project-recipes.md):** Everything the recipe records, and which choice wins.
- **[Automatic Rollback<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](rollback.md):** What happens when a run fails part-way.
