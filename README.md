# compost

One software-engineering workflow for Claude Code, made by breaking down the best skill
collections and rebuilding them into one: Matt Pocock's skills, obra's superpowers, Lauren Tan's
pstack, Imbue's blueprint, and more. It doesn't fork them and forget. `plugin/pile.toml` pins each
upstream, records which files fed which skill, and `compost:turn` checks them for changes worth
working in.

**spec** → **slice** → **implement** (build, verify, review per issue) → **finish**, with
**diagnose**, **deepen**, **prune**, **thin**, and **turn** for when the work steps sideways.

## Install

```
claude plugin marketplace add JoshuaOliphant/compost
claude plugin install compost@compost
```

Then run `/compost:setup` in each repo. compost is also listed in the
[oliphant-plugins](https://github.com/JoshuaOliphant/claude-plugins) marketplace as
`compost@oliphant-plugins`. Install it one way, not both, or Claude sees every skill twice.

## Read more

- [plugin/README.md](plugin/README.md): every skill, when it runs, and how they connect
- [plugin/canon/](plugin/canon/): the essays the skills point to
- [plugin/pile.toml](plugin/pile.toml) and [plugin/NOTICE](plugin/NOTICE): where compost came from
- [experiments/](experiments/): measured runs behind skill changes
- [plugin/CHANGELOG.md](plugin/CHANGELOG.md)

MIT licensed.
