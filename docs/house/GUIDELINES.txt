# House style guidelines

The design and writing rules every site in the family follows: [jacksonferguson.me](https://jacksonferguson.me) and the project sites on its subdomains. The CSS and scripts here implement most of them. The rest are judgment calls a stylesheet can't make, so they're written down here, and each site's `AGENTS.md` points at this file.

A site may add its own rules, but it never contradicts these. When a rule here is wrong, change it here and release a new version, rather than working around it in one site.

## Color and type

- **Read the tokens, never raw values.** Colors, typefaces, and sizes come from `css/tokens.css`. A value a site needs that no token covers is a sign the token is missing.
- **Cyan is the only accent.** `--accent` marks what the reader can act on and what's current. Green, amber, and red only report an outcome. The `--prompt` green belongs to the terminal.
- **Dark first.** The palette is dark. A site may offer a light scheme by redefining the tokens it reads, but terminals, recordings, and install boxes stay dark in both.
- **Two typefaces.** DM Sans for prose and headings, JetBrains Mono for code, commands, labels, and section markers. Headings are weight 500 with tight tracking, never bold.
- **One type scale.** Each tier has one token (`--fs-h1` to `--fs-label`), and the tiers shrink together on phones. Components never set their own sizes.

## Page anatomy

- **Sections open with a numbered marker.** `<div class="hs-section-marker"><span>01 / ABOUT</span></div>`, then an H2 that says something the marker doesn't. Only top-level sections are numbered.
- **Card eyebrows are unnumbered labels** (`FEATURED PROJECT`), in mono at `--fs-label`.
- **Cards are panels with a line border** (`--panel`, `--line`, 5px radius), and are never nested inside cards. A card that links lightens its border on hover; it never lifts, glows, or casts a shadow.
- **A page that scrolls far has a grid behind its sections**: 80px lines in the line color, faint enough to read as texture.

## Navigation and icons

- **Every link that stands on its own carries an icon that says where it goes.** That covers buttons, text links outside a sentence, cards, and jump links. The icon comes after the label, in the text's color:

  | Icon | Where the link goes |
  | --- | --- |
  | `arrow-down` | Further down the same page |
  | `arrow-up` | Back up the same page |
  | `arrow-right` | The next page, or a closely related page on the same site |
  | `arrow-left` | The previous page, or back to where the reader came from |
  | `arrow-up-right` | Another site, or a page only loosely related to this one |

- **Brand links carry their brand.** A link to GitHub, LinkedIn, Python, or email shows its `brand-*` icon before the label instead of an arrow. A link to jacksonferguson.me from a project site shows `icons/jacksonferguson.svg`.
- **A link inside a sentence takes no icon.** It reads as part of the prose.
- **Use only the icons in `icons/`.** Never a text arrow (`→`), an emoji, or another icon set. A site that can inline SVG inlines these files; any other site uses `css/icons.css`. A missing icon is added here first.
- **Icons are decoration.** Mark them `aria-hidden="true"`; the label carries the meaning.

## Terminals and recordings

- **Every terminal is an `.hs-terminal` window**, whether it holds a recording or a screenshot. A screenshot generated as an image draws the same window: the same bar, border, title color, and traffic-light dots.
- **A recording starts itself once most of it is in view**, loops, and never shows a play button over it first. Readers who asked for reduced motion get a still first frame and the play button instead.
- **The player loads only when a recording nears the viewport.** A page without a recording loads none of it.

## Motion and loading

- **The first screen is text.** Nothing heavy (an image, a recording, a canvas, a library) holds up the first paint. Load it after the page is up, or when the reader scrolls toward it.
- **Background motion is texture, not a centerpiece.** An animated field behind a hero stays in the dark cyan family, sits well below the text in contrast, and never competes with it.
- **Motion can be stopped.** Anything that moves on its own for more than a few seconds has a visible pause control, stops when it's off screen or the tab is hidden, and stays still for readers who asked for reduced motion.

## Writing

Every site speaks in one voice: calm, clear, and precise. What changes from page to page is who the page is for, which sets how much it assumes and how much detail it gives.

### The voice

- **Name the concrete thing.** Say the file, the command, the place, or the number, rather than the category it belongs to: "restores `pyproject.toml`", not "restores project state"; "granite slabs above the valley", not "stunning scenery".
- **Lead with what the reader needs.** Open a page, a section, or a paragraph with the answer or the action. Reasons and exceptions follow it.
- **One claim per sentence.** Length matters less than how much the reader has to hold at once. When a sentence carries three or more parallel outcomes or conditions, make them a list.
- **Every claim can be checked.** A number says how it was measured, or links to where it was. A word like "fast", "robust", or "reliable" needs the measurement behind it, or it goes.
- **Plain, not grand.** Prefer the ordinary word: "use", not "leverage"; "set up", not "orchestrate". Write no hype ("seamless", "powerful", "effortless"), no "simply" or "just" softening a step, and no superlative that isn't measured. Turn abstraction into what actually happens: "deterministic, transaction-aware scaffolding" says less than "if a step fails, every file goes back to how it was".
- **State limits as plainly as strengths.** Say what a thing doesn't do, and when something else fits better.
- **Headings say something.** A heading tells the reader what its section answers or does, not only its topic.
- **Punctuation stays quiet.** Reach for a comma, a colon, or a new sentence before an em dash. Bold only labels the start of a list item, as in this list. No exclamation marks.
- **Person follows the site.** A personal site speaks as "I". Documentation speaks to the reader as "you".
- **Never hard-wrap Markdown prose.** Each paragraph and list item is one line, however long.

### Audiences

Each page has one primary audience:

| Audience | Who reads it | What it assumes | What it gives |
| --- | --- | --- | --- |
| General | Hiring managers, coworkers, curious visitors, and technical readers on their first look | No knowledge of the tool, the field, or its vocabulary | What the thing is, why it matters, and what using it is like, with links onward for depth |
| Users | People using the tool to get something done | The goal, not the tool's concepts | Steps and their outcomes, with each term defined where it first appears |
| Technical | Contributors, evaluators, and readers who want the mechanics | The user-level pages | Precise detail and internal names, each defined once on the page that owns it |

- **A homepage, a project card, a README, and a documentation landing page are General.** Everyone lands there first, so they explain plainly and hand off to the pages that go further.
- **A page's opening serves its primary audience.** Deeper material can follow under its own heading, or on a linked page.
- **Define a term where it first appears**, or link to where it's defined. Never assume the reader came from the page before.
- **Technical pages may be denser, never harder.** They use more internal names and less explanation, but the voice still holds: one claim per sentence, concrete names, and the answer first.

## Documentation sites

Rules for project documentation built on a docs theme (Zensical or Material for MkDocs). The landing page is a house page and follows everything above; the inner pages keep the theme's layout with the house tokens, fonts, and terminal window.

- **Each section of the navigation serves one audience.** Installation, tutorials, and user guides serve Users. Architecture, internals, and contributor guides serve Technical readers. Reference pages serve Users looking something up: complete, terse, one entry per item.
- **Each rule is stated once.** One page owns it, and every other page links there instead of restating it.
- **Only top-level pages carry a navigation icon.** A page that sits directly in the navigation, outside any section, sets `icon:` in its front matter, and it shows beside the page in the left navigation. A page inside a section sets none. Pick icons that say what the page is for, and never repeat one.
- **Cards at the top of a page are optional.** Add them only when they genuinely help a reader choose where to go, or see a page's main points before the detail. A page that reads well without them has none.
- **Cards come in twos, fours, or sixes.** Each card has to earn its place: if only five say something worth saying, use four. Never pad a grid to reach an even count, and never repeat in a card what the heading under it already says.
- **Every page has a `description`** in its front matter.
- **Terminal output is shown, not described.** Use a recording or a generated screenshot in the house terminal window rather than pasting long output into a code block, and keep code blocks for what the reader types.

## Interaction

- **Focus is always visible:** a 2px `--accent` outline.
- **One install box per product**, with uv first.
- **Copy buttons confirm.** They say `Copied!` or `Failed` for a moment, then show their label again (`js/copy-command.js` does this).
