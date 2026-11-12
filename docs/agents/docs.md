# Docs

The code is the source of truth. Docs hold only what the code can't say, and live in the core
docs below. Anything else in markdown is a candidate for `compost:prune`.

## Core docs

| Doc | Holds |
|---|---|
| `README.md` | What compost is and how to install it |
| `AGENTS.md` | How to work here: layout, versioning, commands, conventions |
| `plugin/README.md` | The skills, how they connect, and plugin development |
| `plugin/CONTEXT.md` | compost's vocabulary |
| `docs/adr/` | Why decisions were made; records, never edited to match the code |
| `docs/agents/` | How the compost skills work in this repo |
| `plugin/CHANGELOG.md` | What changed, release by release |

Core patterns beyond the defaults, one per line:

```
```

## Not documentation

Product, not prose about it: never pruned, never scanned. The plugin README and glossary stay
core, since a core doc is never excluded. One pattern per line:

```
plugin/**
experiments/**
```

`plugin/**` is shipped skill, agent, canon, and reference text; `experiments/**` holds eval
harnesses and their outputs.

## Before writing something down

Put it in the first place that holds it: a name, a type or a check, a test, a comment where the
code lives (why, never what), and only then a core doc. Don't add a markdown file outside the core
docs; if one is truly needed, add its pattern above in the same change. Plans and specs go in the
issue tracker, not in `docs/`.

When docs and code disagree, the code is the likely truth: run `compost:prune`.
