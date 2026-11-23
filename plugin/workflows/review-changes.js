// ABOUTME: Compost's review workflow: Standards and Spec reviewers in parallel over a branch diff, or one reviewer on both for a small one.
// ABOUTME: Skeptics try to refute each finding worth one (Jev's triage, else every blocker and major); survivors, refutations, and unjudged findings come back side by side.
export const meta = {
  name: 'review-changes',
  description: 'Review a branch along two axes, Standards and Spec (one reviewer on both for a small, non-structural diff), then have skeptics try to refute every finding worth one (by Jev triage, else every blocker and major)',
  whenToUse: 'compost:review is the normal entry point: it runs this workflow, runs the harness code review beside it, and works through the findings; call this directly only for the two axes alone. After verify passes on an issue, or whenever a branch or work-in-progress diff needs review, whatever its size. Pass {base, head, issue, spec, since, prior, skeptics, jev, full}, all optional: base defaults to the merge-base with the default branch, head to HEAD, issue to one found in the commits or branch name, spec (the issue text, fetched by the caller; scope then fetches nothing) to none, since (the head the last review round reviewed; reviewers then judge only what changed after it) and prior (the findings and rulings of that round, which reviewers and skeptics are told) to none, skeptics (votes per finding worth a skeptic) to 1, jev (the path to compost scripts/jev.py, which ranks files by structural risk) to this plugin\'s own copy, full (force separate Standards and Spec reviewers on a small diff) to false. A diff of 50 changed lines or fewer that Jev ranks and finds not structural gets one reviewer covering both axes. A bare string is treated as base.',
  phases: [
    { title: 'Scope', detail: 'pin the base, the diff, the spec, and the standards sources; rank files by structural risk' },
    { title: 'Standards', detail: 'reviewer against instructions files, CONTEXT.md, ADRs, the canon, and the REVIEW.md checks the diff triggers (on a small diff, one light reviewer covers both axes here); skeptics refute each finding worth one' },
    { title: 'Spec', detail: 'reviewer against the issue AC-N and interfaces; skeptics refute each finding worth one' },
  ],
}

const input = typeof args === 'object' && args !== null ? args : { base: args }
const skepticsPerFinding = input.skeptics || 1
const head = input.head || 'HEAD'
const jevScript = input.jev || ''
// A caller holding the issue text (one whose tracker the lean scope agent cannot read, such as an MCP-only one) passes it in.
const givenSpec = typeof input.spec === 'string' && input.spec.trim() ? input.spec : ''
// The workflow runs the two axes and their skeptics; the harness's own code review is the caller's to run.
const NOT_RUN = ['harness code review: not part of this workflow; compost:review runs it beside this one on a diff that changes executable code']
const forceFull = Boolean(input.full)
// A re-review round names the head the last round reviewed (since) and that round's findings with their rulings (prior).
const since = typeof input.since === 'string' ? input.since.trim() : ''
const prior = typeof input.prior === 'string' ? input.prior.trim() : ''
// At or under this many changed lines, with Jev finding no structural file, one reviewer covers both axes.
const LIGHT_MAX_CHANGED_LINES = 50

// The new-side lines a diff changed, per file: what tells a finding about this diff from one about code it left alone.
const CHANGED_SCHEMA = {
  type: 'array',
  description: 'For each changed file, the new-side line ranges its hunks cover, inclusive',
  items: {
    type: 'object',
    required: ['file', 'lines'],
    properties: {
      file: { type: 'string' },
      lines: { type: 'array', items: { type: 'array', items: { type: 'integer' }, minItems: 2, maxItems: 2 } },
    },
  },
}

const SCOPE_SCHEMA = {
  type: 'object',
  required: ['base', 'head', 'repo', 'diffCommand', 'shortstat', 'commits', 'files', 'standardsSources', 'spec'],
  properties: {
    repo: { type: 'string', description: 'The repository under review: owner/name from the origin remote, or the top-level directory name without one' },
    base: { type: 'string', description: 'Resolved commit SHA of the fixed point' },
    head: { type: 'string', description: 'Resolved commit SHA of the head under review' },
    diffCommand: { type: 'string' },
    shortstat: { type: 'string', description: 'The line git diff --shortstat prints, verbatim; empty when it could not be read' },
    commits: { type: 'array', items: { type: 'string' } },
    files: { type: 'array', items: { type: 'string' } },
    changed: CHANGED_SCHEMA,
    dirty: { type: 'boolean', description: 'True when git status --porcelain shows uncommitted edits to a changed file' },
    guide: {
      type: 'object',
      description: 'The review guide in force: the repo root REVIEW.md, or the defaults when it has none',
      required: ['source', 'minorCap'],
      properties: {
        source: { type: 'string', enum: ['REVIEW.md', 'defaults'] },
        minorCap: { type: 'integer', description: 'Most minor findings the whole review keeps' },
        failure: { type: 'string', description: "REVIEW.md's Failure section, verbatim; empty for the defaults" },
        skip: { type: 'string', description: "REVIEW.md's Skip section, verbatim; empty for the defaults" },
        checks: { type: 'string', description: "REVIEW.md's Checks section, verbatim; empty when it has none" },
        problem: { type: 'string', description: 'Why a REVIEW.md value could not be read; empty otherwise' },
      },
    },
    skipped: { type: 'array', items: { type: 'string' }, description: 'The changed files a skip rule of the guide covers' },
    triggers: {
      type: 'array',
      description: "One entry per check in the guide's Checks section: whether this diff trips its Trigger",
      items: {
        type: 'object',
        required: ['name', 'triggered', 'why'],
        properties: {
          name: { type: 'string', description: 'The check\'s bold name, as REVIEW.md writes it' },
          triggered: { type: 'boolean' },
          why: { type: 'string', description: 'The changed file and hunk that trips the trigger, or what the trigger needs that the diff lacks' },
        },
      },
    },
    delta: {
      type: 'object',
      description: 'Only when a since commit was given: the lines changed since the last round',
      required: ['used', 'since', 'changed'],
      properties: {
        used: { type: 'boolean', description: 'false when since does not resolve or is not an ancestor of the head' },
        since: { type: 'string', description: 'The resolved since SHA, or since as given when it did not resolve' },
        changed: CHANGED_SCHEMA,
        problem: { type: 'string', description: 'Why the delta was not used; empty otherwise' },
      },
    },
    standardsSources: { type: 'array', items: { type: 'string' } },
    spec: {
      type: 'object',
      required: ['found', 'source', 'id', 'text'],
      properties: {
        found: { type: 'boolean' },
        source: { type: 'string', description: 'Issue URL, issue id, or file path; empty when not found' },
        id: { type: 'string', description: 'The id of the issue fetched, exactly as the tracker writes it (42, bd-a1b2.3, group/project#12, or a local tracker issue file path as given); empty for a spec file found without an issue, or when not found' },
        text: { type: 'string', description: 'User stories, AC-N, and interfaces verbatim; empty when not found' },
        problem: { type: 'string', description: 'Why a given issue could not be fetched; empty otherwise' },
      },
    },
    problem: { type: 'string', description: 'Why scoping failed; empty on success' },
    risk: {
      type: 'object',
      description: 'Copied from jev.py review-risk; omit when no jev path was given',
      required: ['ranked', 'structural', 'files'],
      properties: {
        ranked: { type: 'boolean', description: 'false when review-risk exited non-zero' },
        structural: { type: 'boolean' },
        files: {
          type: 'array',
          items: {
            type: 'object',
            required: ['file', 'score', 'structural'],
            properties: { file: { type: 'string' }, score: { type: 'number' }, structural: { type: 'boolean' } },
          },
        },
        problem: { type: 'string', description: 'The first line of stderr when review-risk failed' },
      },
    },
  },
}

// A reviewer that found nothing and one that looked at nothing both return no findings; this record tells them apart.
const CHECKED_SCHEMA = {
  type: 'array',
  description: 'What you checked: each rule read against the diff, each changed file opened, and on Spec one entry per AC-N. An entry without a file:line does not count; an AC-N with no line to cite is a finding whose claim names it instead.',
  items: {
    type: 'object',
    required: ['item', 'at'],
    properties: {
      item: { type: 'string', description: 'The rule, file, or AC-N checked, with your verdict on it' },
      at: { type: 'string', description: 'The file:line you read to check it' },
    },
  },
}

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings', 'checked'],
  properties: {
    checked: CHECKED_SCHEMA,
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['file', 'line', 'severity', 'claim', 'evidence'],
        properties: {
          file: { type: 'string' },
          line: { type: ['integer', 'null'], description: 'null when the finding is about something absent from the diff' },
          severity: {
            type: 'string',
            enum: ['blocker', 'major', 'minor', 'pre-existing'],
            description: 'pre-existing: a real bug at a line this diff did not change, recorded apart and never fixed on this branch',
          },
          claim: { type: 'string' },
          evidence: { type: 'string', description: 'The rule or AC-N quoted with its file, plus the code quoted at file:line' },
          skeptic: { type: 'boolean', description: 'worth_skeptic from jev.py triage-finding; omit when Jev was unavailable' },
        },
      },
    },
  },
}

// A spec can span repositories, each built and reviewed on its own branch; an AC-N the spec places in another one is listed, not judged.
const ELSEWHERE_SCHEMA = {
  type: 'array',
  description: 'Each AC-N the spec itself places in another repository, so this diff cannot meet it. Leave out every AC-N the spec does not place elsewhere.',
  items: {
    type: 'object',
    required: ['ac', 'repo'],
    properties: {
      ac: { type: 'string', description: 'The AC-N, as the spec writes it' },
      repo: { type: 'string', description: 'The other repository, exactly as the spec names it where it places the AC-N' },
    },
  },
}

const SPEC_FINDINGS_SCHEMA = {
  ...FINDINGS_SCHEMA,
  properties: { ...FINDINGS_SCHEMA.properties, elsewhere: ELSEWHERE_SCHEMA },
}

function lightFindingsSchema(axisNames) {
  const item = FINDINGS_SCHEMA.properties.findings.items
  return {
    type: 'object',
    required: ['findings', 'checked'],
    properties: {
      findings: {
        type: 'array',
        items: {
          ...item,
          required: [...item.required, 'axis'],
          properties: { ...item.properties, axis: { type: 'string', enum: axisNames } },
        },
      },
      checked: {
        type: 'object',
        description: 'For each axis, what you checked on it',
        required: axisNames,
        properties: Object.fromEntries(axisNames.map(name => [name, CHECKED_SCHEMA])),
      },
      ...(axisNames.includes('Spec') ? { elsewhere: ELSEWHERE_SCHEMA } : {}),
    },
  }
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['refuted', 'reason'],
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string', description: 'What you checked, with file:line, and what it showed' },
  },
}

const SMELL_BASELINE = `Smell baseline (Fowler, Refactoring ch. 3). Each is a judgement call, never a hard violation, and a documented repo standard overrides it:
- Mysterious Name: a name that does not reveal what it does or holds.
- Duplicated Code: the same logic shape in more than one hunk or file of the change.
- Feature Envy: a function reaching into another object's data more than its own.
- Data Clumps: the same few fields or params travelling together.
- Primitive Obsession: a primitive standing in for a domain concept that deserves a type.
- Repeated Switches: the same switch or if-cascade on the same type recurring.
- Shotgun Surgery: one logical change forcing scattered edits across many files.
- Divergent Change: one module edited for several unrelated reasons.
- Speculative Generality: abstraction, parameters, or hooks the spec does not need.
- Message Chains: long a.b().c().d() navigation the caller should not depend on.
- Middle Man: a class or function that mostly delegates onward.
- Refused Bequest: an implementer that ignores or overrides most of what it inherits.`

phase('Scope')

const baseHint = input.base
  ? `The fixed point is \`${input.base}\`.`
  : `No fixed point was given: use the merge-base of \`${head}\` with the default branch (\`git merge-base ${head} origin/HEAD\`, falling back to \`main\` then \`master\`).`

// Tracker ids are strings: a bare number reads as #42, while bd-a1b2.3 or group/project#12 stand as written.
function issueRef(id) {
  const bare = String(id).replace(/^#/, '')
  return /^\d+$/.test(bare) ? `#${bare}` : bare
}
const issueId = input.issue ? String(input.issue).replace(/^#/, '') : ''

const issueHint = input.issue
  ? `The originating issue is \`${issueId}\` and no other: fetch it even if the conversation names a different one.`
  : 'No issue was given: look for issue references in the commit messages (#123, Closes #45) and in the branch name, then for a spec file under docs/, specs/, or .scratch/ matching the branch.'

const specStep = givenSpec
  ? 'The spec was passed in by the caller: do not fetch any issue or spec file. Set spec to `{found: false, source: "", id: "", text: ""}`; the workflow uses the text it was given.'
  : `${issueHint} Fetch it, with its comments, using the read command docs/agents/issue-tracker.md gives for this repo's tracker, and pass the id to it exactly as written: it may be dotted (bd-a1b2.3) or name another project (group/project#12), so never turn it into a number or drop its project. Only if that file is missing, use \`gh api repos/{owner}/{repo}/issues/<n>\` and \`gh api repos/{owner}/{repo}/issues/<n>/comments --paginate\`. Wherever the read goes through \`gh\`, use \`gh api\` (REST): \`gh issue view\` goes through GraphQL, which cloud sessions block. Copy the spec into spec.text with every heading in it, verbatim: its user stories, every AC-N, and any interfaces, under the headings they sit under (a heading can say which repository a criterion belongs to). If an issue was given and fetching it fails, set spec to \`{found: false, source: "", id: "", text: "", problem: "<the error you got>"}\` and carry on with the rest. Set spec.id to the id of the issue you fetched, as the tracker writes it, or "" for a spec file.`

const jevCommand = jevScript ? `\`uv run ${jevScript} review-risk --input <file>\`` : 'review-risk with the jev.py your agent definition names'
const deltaStep = since
  ? `\n5. This is a re-review: the last round reviewed \`${since}\`. Resolve it with \`git rev-parse\` and check \`git merge-base --is-ancestor <since-sha> <head-sha>\`. If it does not resolve or is not an ancestor (the branch was rebased), set delta to \`{used: false, since: "${since}", changed: [], problem: "<why>"}\`. Otherwise set delta to \`{used: true, since: "<since-sha>", changed}\`, reading changed from \`git diff -U0 <since-sha> <head-sha> -- <the changed files>\` the same way as in step 1.`
  : ''
const riskStep = `\n4. Rank the changed files by structural risk: write \`{"base": "<base-sha>", "head": "<head-sha>"}\` to a temp file and run ${jevCommand}. Set risk to \`{ranked: true, structural, files}\` from its output, keeping each file's file, score, and structural. If it exits non-zero, set risk to \`{ranked: false, structural: false, files: [], problem: "<first line of stderr>"}\`.`

const scope = await agent(
  `Scope a code review of the changes up to \`${head}\`. Do not review anything yet.

${baseHint} The head under review is \`${head}\`.
1. Resolve the fixed point and the head with \`git rev-parse\`. Set dirty to true when \`git status --porcelain\` lists a changed file with uncommitted edits. Record repo as the owner/name in \`git remote get-url origin\` (no host, no .git), or the name of the directory \`git rev-parse --show-toplevel\` prints when there is no origin. Record diffCommand as \`git diff <base-sha>...<head-sha>\` (three dots, against the merge-base), shortstat as the line \`git diff --shortstat <base-sha>...<head-sha>\` prints, verbatim, the commits from \`git log --oneline <base-sha>..<head-sha>\`, and the changed files from \`git diff --name-only <base-sha>...<head-sha>\`. Record changed from \`git diff -U0 <base-sha>...<head-sha>\`: for each file, every hunk header \`@@ -a,b +c,d @@\` gives the range [c, c+d-1] (d left out means 1), and a pure deletion (d is 0) gives [c, c+1], the lines around the cut.
2. ${specStep}
3. List the standards sources as they stand at the fixed point, never from disk: list them with \`git ls-tree -r --name-only <base-sha>\` and read each with \`git show <base-sha>:<path>\`, so a branch is judged by the rules of the branch it merges into, not by its own edits to them. They are CLAUDE.md and AGENTS.md at the root and in directories the diff touches, CONTEXT.md or CONTEXT-MAP.md, docs/adr/*.md, CODING_STANDARDS.md, CONTRIBUTING.md, and linter or formatter configs (so reviewers know what tooling already enforces). When the fixed point has a REVIEW.md at its root, list it too and set guide from it: source "REVIEW.md", failure, skip, and checks from its Failure, Skip, and Checks sections verbatim (checks "" when it has no Checks section), and minorCap from its Minor cap section as a whole number (if it holds none, use 5 and say why in guide.problem). Without one, set guide to \`{source: "defaults", minorCap: 5, failure: "", skip: ""}\`. Then set skipped to the changed files a skip rule covers: REVIEW.md's, or by default generated files (a generated-file header, *_pb2.py, minified bundles), vendored ones (vendor/, third_party/), and lock files (uv.lock, package-lock.json, *.lock, requirements*.lock). For each check in guide.checks (one bullet each, \`- **<name>**: Trigger: ... Check: ... Source: ...\`), read its Trigger against \`git diff <base-sha>...<head-sha>\` and add \`{name, triggered, why}\` to triggers, with why naming the changed file and hunk that trips it, or what the trigger needs that the diff lacks. Decide triggers only; answering a check is the reviewers' job. When unsure, it is triggered.${riskStep}${deltaStep}

If the fixed point does not resolve or the diff is empty, say so in problem and return every other field empty: base, head, repo, diffCommand, and shortstat as "", commits, files, and standardsSources as [], and spec as \`{found: false, source: "", id: "", text: ""}\`.`,
  { label: 'scope', phase: 'Scope', schema: SCOPE_SCHEMA, effort: 'low', agentType: 'compost:scope' },
)

if (!scope || scope.problem || scope.files.length === 0) {
  const problem = scope ? scope.problem || 'The diff is empty.' : 'The scoping agent did not return.'
  log(problem)
  return { complete: false, problem, notRun: NOT_RUN }
}

const specSource = input.issue ? issueRef(issueId) : givenSpec ? 'the spec passed in' : scope.spec.source
const specDoc = givenSpec ? { found: true, source: specSource, id: issueId, text: givenSpec } : scope.spec

function issueFetchProblem() {
  if (givenSpec || !input.issue) return ''
  if (!scope.spec.found) return scope.spec.problem || 'the scoping agent returned no spec'
  // A local tracker's issue is a markdown file whose only id is its path: scope may report it as the source alone.
  const isFile = /\.md$/i.test(issueId)
  const fetched = issueRef(scope.spec.id || (isFile ? scope.spec.source : ''))
  if (fetched !== specSource) return `the scoping agent fetched ${fetched} instead`
  return ''
}

const fetchProblem = issueFetchProblem()
const specProblem = fetchProblem ? `issue ${specSource} could not be fetched: ${fetchProblem}` : ''
if (specProblem) log(specProblem)

log(`Reviewing ${scope.files.length} files across ${scope.commits.length} commits since ${scope.base.slice(0, 8)}`)

// Line numbers decide pre-existing routing and the delta filter, so reviewers read the committed head whenever disk may differ.
const readAtHead = head === 'HEAD' && !scope.dirty
  ? ''
  : `\nThe working tree may not be at the head under review: read changed files with \`git show ${scope.head}:<path>\`, not from disk.`

const risk = scope.risk && scope.risk.ranked
  ? { ranked: true, structural: scope.risk.structural, files: scope.risk.files }
  : { ranked: false, structural: null, files: [], problem: riskProblem() }

function riskProblem() {
  if (!scope.risk) return 'the scoping agent returned no risk ranking'
  return scope.risk.problem || 'review-risk failed'
}

const fileList = risk.ranked
  ? `Changed files, riskiest first (structural risk 0-4 from Jev; read the top ones first):
${risk.files.map(f => `${f.file} (${f.score.toFixed(2)}${f.structural ? ', structural' : ''})`).join('\n')}`
  : `Changed files:
${scope.files.join('\n')}`

// A delta the scoping agent could not establish is a full review, said so in the result.
const delta = since
  ? scope.delta && scope.delta.used && Array.isArray(scope.delta.changed)
    ? { used: true, since: scope.delta.since, changed: scope.delta.changed }
    : { used: false, since, problem: (scope.delta && scope.delta.problem) || 'the scoping agent returned no delta' }
  : null
if (delta && !delta.used) log(`Reviewing the whole branch: ${delta.problem}`)

const deltaNote = delta && delta.used
  ? `\nThis is a re-review. Judge only the lines changed since the last round, \`git diff ${delta.since} ${scope.head}\`; read the branch diff above for context. The workflow drops a finding at a line outside that diff, so a bug those lines cause elsewhere (a caller they break) is cited at the changed line that causes it, with the broken line in the evidence.`
  : ''

// Without a REVIEW.md, every repo gets the same short guide, which the starter compost:setup offers writes out.
const DEFAULT_MINOR_CAP = 5
const MINOR_ORDER = "List your most important minor first: the workflow keeps Standards' minors first, then Spec's, each in the order listed, up to the cap."

const guide = scope.guide && ['REVIEW.md', 'defaults'].includes(scope.guide.source)
  ? scope.guide
  : { source: 'defaults', minorCap: DEFAULT_MINOR_CAP, problem: 'the scoping agent returned no review guide' }
const minorCap = Number.isInteger(guide.minorCap) && guide.minorCap >= 0 ? guide.minorCap : DEFAULT_MINOR_CAP
const guideProblem = guide.problem || (minorCap === guide.minorCap ? '' : `minor cap ${JSON.stringify(guide.minorCap)} is not a whole number; using ${DEFAULT_MINOR_CAP}`)
const skippedFiles = new Set(Array.isArray(scope.skipped) ? scope.skipped : [])

const guideNote = guide.source === 'REVIEW.md'
  ? `\nReview guide: this repo's REVIEW.md at the base, among the standards sources; read it whole, and it overrides your defaults where it speaks.
- Failure: ${guide.failure || '(not stated; a change that breaks behaviour, loses or leaks data, or blocks a rollback)'}
- Minors: at most ${minorCap} for the whole review. ${MINOR_ORDER}
- Skip: ${guide.skip || '(not stated)'}`
  : `\nReview guide (defaults; the base has no REVIEW.md):
- Failure: a change that breaks behaviour, loses or leaks data, or blocks a rollback.
- Minors: at most ${minorCap} for the whole review. ${MINOR_ORDER}
- Skip: generated, vendored, and lock files, and anything a configured linter or formatter enforces.
- Evidence: every behaviour claim cites a file:line, not an inference from naming.`

// A check is one bullet of the guide's Checks section, `- **<name>**: Trigger: ... Check: ... Source: ...`, its
// continuation lines folded in. The scope agent decides each trigger; a check it gave no decision on runs.
function parseChecks(section) {
  const items = []
  for (const line of String(section || '').split('\n')) {
    const bullet = line.match(/^ {0,3}[-*+]\s+(.*)$/)
    if (bullet) items.push(bullet[1].trim())
    else if (items.length && line.trim()) items[items.length - 1] += ` ${line.trim()}`
  }
  const named = items.map(text => ({ name: ((text.match(/^\*\*(.+?)\*\*/) || text.match(/^([^:]+):/) || [])[1] || '').trim(), text }))
  return named.filter((check, i) => check.name && named.findIndex(other => sameName(other.name, check.name)) === i)
}
const sameName = (a, b) => String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase()

const guideChecks = guide.source === 'REVIEW.md' ? parseChecks(guide.checks) : []
const checks = guideChecks.map(check => {
  const decided = (Array.isArray(scope.triggers) ? scope.triggers : []).find(entry => entry && sameName(entry.name, check.name))
  if (!decided) return { ...check, status: 'triggered', why: 'the scoping agent gave no decision on it, so it runs' }
  return { ...check, status: decided.triggered === false ? 'not triggered' : 'triggered', why: String(decided.why || '') }
})
const triggeredChecks = checks.filter(check => check.status === 'triggered')

const skipNote = skippedFiles.size
  ? `\nSkipped by the review guide; raise nothing in these: ${[...skippedFiles].join(', ')}`
  : ''

const priorNote = prior
  ? `\nEarlier rounds' findings and their rulings:\n${prior}\nDo not raise one of these again unless the lines changed since the last round change it: a fix stands, a pushback stands with its reason, and a pre-existing finding is already recorded.`
  : ''

const diffContext = `Diff: \`${scope.diffCommand}\`${readAtHead}
Commits:
${scope.commits.join('\n')}
${fileList}${guideNote}${skipNote}${deltaNote}${priorNote}`

const repoUnderReview = String(scope.repo || '')
const IN_REPO = `This diff is in ${repoUnderReview || 'a repository the scoping agent could not name'}.`

const SPEC_ONLY = `Grade only against the spec text in this prompt. Do not fetch any issue or spec file yourself (no \`gh issue view\`, no \`gh api\` on issues), even when the diff, the commits, or the conversation name a different one.`

function checksNote() {
  if (!triggeredChecks.length) return ''
  return `

Checks this diff triggers, from the base's REVIEW.md. Answer each check's question against the code. Under checked, give each its own entry whose item starts with the check's name as written here and gives your yes or no, at the file:line that shows it; the workflow fails this axis when a triggered check has no such entry. A check whose answer is a problem is also a finding, citing REVIEW.md and the check.
${triggeredChecks.map(check => `- ${check.text} (triggered: ${check.why})`).join('\n')}`
}

const AXES = [
  {
    name: 'Standards',
    question: "does the code follow this repo's documented standards and domain language?",
    active: true,
    checks: `Standards sources, as they stand at the base ${scope.base} (read each with \`git show ${scope.base}:<path>\`; the branch's own edits to them take effect once it merges, so review those edits as changes, not as rules):
${scope.standardsSources.join('\n') || '(none documented)'}

Check the diff against:
- Every rule in the instructions files and contributing guides above. Cite the file and the rule.
- CONTEXT.md vocabulary: names in the diff that contradict or bypass the glossary's terms.
- ADRs in docs/adr/: changes that go against a recorded decision without a superseding ADR.
- Doc drift: a line in an instructions file, README, or other doc that describes the changed code and no longer matches it after this diff. Cite the doc's file and line.
- The compost canon essays your agent definition points you to, where one applies.
- The smell baseline below.

${SMELL_BASELINE}

Skip anything a linter, formatter, or type checker configured in this repo already enforces.

Under checked, list each rule you read against the diff and each changed file you opened, at the file:line you read.${checksNote()}`,
  },
  {
    name: 'Spec',
    question: 'does the code do what the originating issue asked, no more and no less?',
    active: specDoc.found && !specProblem,
    problem: specProblem,
    schema: SPEC_FINDINGS_SCHEMA,
    checks: `Spec source: ${specSource}
${specDoc.text}

${SPEC_ONLY}

${IN_REPO} A spec can span several repositories, each built and reviewed on its own branch. When the spec itself places an AC-N in another repository (it names that repo on the line defining the AC-N, before its id, or in a heading over that line), this diff cannot meet it: raise no finding for it, and list it under elsewhere with the repo exactly as the spec names it there. The workflow keeps an entry only when that name is on the AC-N's defining line before its id or in a heading over that line. An AC-N the spec does not place in another repository belongs to this one, however unlikely that looks: judge it here. An AC-N with a part in each repo is judged here on this repo's part.

Report:
- Each AC-N that is missing or only partly met. Quote the AC-N; point at the test that should prove it, or say none exists.
- Each interface in the spec whose shape in the code differs from what the spec states.
- Behaviour in the diff nobody asked for (scope creep), at file:line.
- Each AC-N that looks implemented but where the implementation looks wrong.

Under checked, map every acceptance criterion not under elsewhere, across the whole branch even on a re-review: one entry per AC-N, naming it and its verdict (met, partly met, unmet), at the test or code line that shows it. An AC-N with no code or test to point at is a finding (line null) whose claim names it instead.`,
  },
]

function axisPrompt(axis) {
  return `Review this diff on the ${axis.name} axis: ${axis.question}

${diffContext}

${axis.checks}`
}

function lightPrompt(axes) {
  const names = axes.map(axis => axis.name)
  const sections = axes.map(axis => `## ${axis.name} axis: ${axis.question}\n\n${axis.checks}`).join('\n\n')
  return `This diff is small, so you review it alone on ${names.length === 1 ? 'one axis' : 'both axes'}: ${names.join(' and ')}. Keep the axes apart as two reviewers would: set each finding's axis to ${names.map(name => `"${name}"`).join(' or ')}, and under checked list for each axis what you checked on it, each at a file:line, so an axis with no findings reads as looked at, not skipped. Small is no reason to look less hard; it is a reason one reviewer can hold the whole diff.

${diffContext}

${sections}`
}

function skepticPrompt(axis, finding, elsewhere) {
  const location = finding.line === null ? finding.file : `${finding.file}:${finding.line}`
  const placed = elsewhere.length
    ? `${IN_REPO} The spec places ${elsewhereNote(elsewhere)} in another repository, so this diff cannot meet them: a finding that one of them is missing here is refuted. Every other AC-N belongs to this repo.\n`
    : ''
  const specText = axis.name === 'Spec' ? `\nThe spec the finding was judged against:\n${specDoc.text}\n${SPEC_ONLY}\n${placed}` : ''
  const ruled = prior
    ? `\nEarlier rounds ruled on these findings:\n${prior}\nA finding that repeats one pushed back on there is refuted, unless the code it cites changed since ${delta && delta.used ? delta.since : 'the last round'}.\n`
    : ''
  return `A reviewer made the ${axis.name} finding below about the diff \`${scope.diffCommand}\`. Your job is to refute it.${readAtHead}
${specText}${ruled}
Finding (${finding.severity}) at ${location}:
Claim: ${finding.claim}
Evidence: ${finding.evidence}

Read the code it cites and what that depends on, and check that the rule (as the base has it) or AC-N exists and says what is claimed and that nothing elsewhere (a test, a caller, a later hunk) already answers it; a nit a configured linter owns, or an ask for something nobody uses, is refuted. Set refuted to true unless you confirmed the finding yourself against the code. When you are uncertain, it is refuted.`
}

async function judge(axis, finding, index, elsewhere) {
  const votes = await parallel(
    Array.from({ length: skepticsPerFinding }, (_, vote) => () =>
      agent(skepticPrompt(axis, finding, elsewhere), {
        label: `${axis.name} skeptic ${index + 1}.${vote + 1}`,
        phase: axis.name,
        schema: VERDICT_SCHEMA,
        agentType: 'compost:skeptic',
      }),
    ),
  )
  const cast = votes.filter(Boolean)
  const upheld = cast.filter(v => !v.refuted).length
  let verdict = 'refuted'
  if (cast.length === 0) verdict = 'unjudged'
  else if (upheld * 2 > cast.length) verdict = 'survived'
  return {
    finding,
    verdict,
    failed: votes.length - cast.length,
    reasons: cast.map(v => v.reason),
  }
}

// Reviewers cite paths from the repo root; a './' prefix or an absolute path is mapped back to the changed file it ends with.
function repoPath(file) {
  const path = String(file || '').replace(/^\.\//, '')
  if (!path.startsWith('/')) return path
  return scope.files.find(changedFile => path.endsWith(`/${changedFile}`)) || path
}

// A finding's line is changed when a hunk of the diff covers it; a null line is about something absent, never a changed line.
function isChanged(changed, file, line) {
  if (line === null || line === undefined) return false
  const entry = (Array.isArray(changed) ? changed : []).find(e => e && e.file === file)
  return Boolean(entry) && (entry.lines || []).some(([start, end]) => line >= start && line <= end)
}

// A pre-existing finding is believed only where the diff provably left the line alone; at a changed line, or one
// nobody can place, it is the diff's and is judged as a major.
function placedOutsideDiff(finding) {
  return Array.isArray(scope.changed) && typeof finding.line === 'number' && !isChanged(scope.changed, finding.file, finding.line)
}

function routePreExisting(findings) {
  const routed = { kept: [], preExisting: [] }
  for (const finding of findings) {
    if (finding.severity !== 'pre-existing') routed.kept.push(finding)
    else if (placedOutsideDiff(finding)) routed.preExisting.push(finding)
    else routed.kept.push({ ...finding, severity: 'major', skeptic: true })
  }
  return routed
}

const listingKey = finding => `${finding.file}:${finding.line}:${finding.claim}`

function worthSkeptic(finding) {
  return typeof finding.skeptic === 'boolean' ? finding.skeptic : finding.severity !== 'minor'
}

function unjudgedAfterThrow(finding) {
  return { finding, verdict: 'unjudged', failed: skepticsPerFinding, reasons: ['the skeptic stage threw'] }
}

function failedAxis(name, status) {
  return { axis: name, status: `failed: ${status}`, complete: false, survivors: [], refuted: [], unjudged: [], preExisting: [] }
}

function changedLines(shortstat) {
  const count = kind => Number((String(shortstat || '').match(new RegExp(`(\\d+) ${kind}`)) || [0, 0])[1])
  return /\d+ files? changed/.test(shortstat || '') ? count('insertion') + count('deletion') : null
}

// A light review has to prove the diff small and not structural; an unreadable line count, or structural risk
// nobody ranked, runs it in full.
const lineCount = changedLines(scope.shortstat)
const light = !forceFull
  && lineCount !== null
  && lineCount <= LIGHT_MAX_CHANGED_LINES
  && risk.structural === false

const FILE_LINE = /[\w./-]+(:|#L)\d+/
const specAcs = [...new Set(String(specDoc.text || '').match(/\bAC-\d+\b/g) || [])]
  .map(id => ({ id, named: new RegExp(`\\b${id}\\b`) }))

const specLines = String(specDoc.text || '').split('\n')
// Lines inside a fenced code block, so a shell comment there ("# install the CLI") is never read as a heading. As in
// CommonMark, a fence opens with three or more backticks or tildes indented at most three spaces (a backtick run with
// another backtick after it is inline code), and closes only with a run of the same character at least as long and
// nothing after it; an unclosed fence runs to the end. A heading, likewise, is indented at most three spaces.
const fencedLines = new Set()
for (let i = 0, open = ''; i < specLines.length; i++) {
  const [, run = '', rest = ''] = specLines[i].match(/^ {0,3}(`{3,}|~{3,})(.*)$/) || []
  if (open) {
    fencedLines.add(i)
    if (run[0] === open[0] && run.length >= open.length && !rest.trim()) open = ''
  } else if (run && !(run[0] === '`' && rest.includes('`'))) {
    fencedLines.add(i)
    open = run
  }
}
const headingLevel = (line, i) => (fencedLines.has(i) ? 0 : ((line.match(/^ {0,3}(#{1,6})\s/) || [])[1] || '').length)

// The line that defines an AC-N: one it leads, after markup only ("#### AC-3", "- **AC-3** Given"), or one where its id
// is followed by a colon ("- web-ui: AC-3:"), so a story or another criterion that mentions it first does not decide
// where it lives. Without one, its first mention. Lines in a code fence (sample output) count only when nothing else does.
function definitionOf(ac) {
  const leads = new RegExp(`^(\\s|#|[-*+]|\\[[ xX]\\]|\\d+\\.)*${ac.named.source}`)
  const colon = new RegExp(`${ac.named.source}\\**\\s*:`)
  const prose = (line, i) => !fencedLines.has(i)
  const at = specLines.findIndex((line, i) => prose(line, i) && (leads.test(line) || colon.test(line)))
  if (at >= 0) return at
  const mention = specLines.findIndex((line, i) => prose(line, i) && ac.named.test(line))
  return mention >= 0 ? mention : specLines.findIndex(line => ac.named.test(line))
}

// The spec text that can place an AC-N in a repo: its defining line before its id, and the headings over that line.
function placementOf(ac) {
  const at = definitionOf(ac)
  const placing = [specLines[at].slice(0, specLines[at].search(ac.named))]
  let level = headingLevel(specLines[at], at) || 7
  for (let i = at - 1; i >= 0; i--) {
    const line = specLines[i]
    const own = headingLevel(line, i)
    if (own && own < level) {
      placing.push(line)
      level = own
    }
  }
  return placing
}

const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const namesRepo = (text, repo) => new RegExp(`(^|[^\\w./-])${escapeRegExp(repo)}($|[^\\w./-])`, 'i').test(text)
// A fork can share its upstream's name, and its origin is the fork: compare names alone, and on a tie judge the AC-N here.
const repoName = repo => repo.toLowerCase().split('/').pop()

// Returns why the spec does not place this AC-N in that other repo, or '' when it does.
function elsewhereRefusal(ac, repo) {
  if (!repoUnderReview) return 'the repo under review is unknown'
  if (!repo) return 'it names no repo'
  if (repoName(repo) === repoName(repoUnderReview)) return `${repo} is the repo under review`
  if (!placementOf(ac).some(text => namesRepo(text, repo))) {
    return `the spec does not place it in ${repo} (on its defining line before its id, or in a heading over that line)`
  }
  return ''
}

// Splits the reviewer's elsewhere list into the entries the spec backs and the first reason each other AC-N was refused.
function partitionElsewhere(entries) {
  const accepted = []
  const refused = {}
  for (const entry of Array.isArray(entries) ? entries : []) {
    const ac = specAcs.find(known => entry && known.id.toLowerCase() === String(entry.ac || '').trim().toLowerCase())
    if (!ac || accepted.some(kept => kept.ac === ac.id)) continue
    const repo = String(entry.repo || '').trim()
    const why = elsewhereRefusal(ac, repo)
    if (!why) accepted.push({ ac: ac.id, repo })
    else if (!refused[ac.id]) refused[ac.id] = why
  }
  return { accepted, refused }
}

// Groups the accepted AC-N by repo, in the order the reviewer listed them, under each repo's first spelling.
function elsewhereNote(accepted) {
  const groups = new Map()
  for (const { ac, repo } of accepted) {
    const key = repo.toLowerCase()
    if (!groups.has(key)) groups.set(key, { repo, acs: [] })
    groups.get(key).acs.push(ac)
  }
  return [...groups.values()].map(group => `${group.acs.join(', ')} (${group.repo})`).join('; ')
}

// Returns why the reviewer's record of what it checked falls short, or '' when it holds.
function uncheckedReason(axis, review, placed, kept) {
  const entries = Array.isArray(review.checked) ? review.checked : []
  if (entries.length === 0) {
    return review.findings.length ? 'the reviewer did not say what it checked' : 'the reviewer returned no findings and no record of what it checked'
  }
  const cited = entries.filter(entry => entry && FILE_LINE.test(String(entry.at || '')))
  if (cited.length === 0) return 'the reviewer cited no file:line for anything it checked'
  if (axis.name === 'Standards') {
    // As with an AC-N on Spec, a triggered check counts as answered only by a cited entry that names it.
    const unanswered = triggeredChecks
      .filter(check => !cited.some(entry => String(entry.item || '').toLowerCase().includes(check.name.toLowerCase())))
      .map(check => check.name)
    return unanswered.length ? `the reviewer did not answer check${unanswered.length > 1 ? 's' : ''} ${unanswered.join(', ')} at a file:line` : ''
  }
  if (axis.name !== 'Spec') return ''
  // A finding about an AC-N (one with no line to cite, or one only partly met) maps it too. Its claim must
  // name the AC-N: evidence quotes AC-Ns in passing, which says nothing about whether they were checked.
  const named = [...cited.map(entry => entry.item), ...kept.map(f => f.claim)].map(String)
  const unmapped = specAcs
    .filter(ac => !named.some(text => ac.named.test(text)) && !placed.accepted.some(entry => entry.ac === ac.id))
    .map(ac => ac.id)
  const refusals = unmapped.filter(id => placed.refused[id]).map(id => `refused ${id} elsewhere: ${placed.refused[id]}`)
  if (!unmapped.length) return ''
  return `the reviewer did not map ${unmapped.join(', ')} to the code${refusals.length ? ` (${refusals.join('; ')})` : ''}`
}

async function settleAxis(review, axis) {
  if (review && review.skipped && axis.problem) return failedAxis(axis.name, axis.problem)
  if (review && review.skipped) {
    return { axis: axis.name, status: 'skipped: no spec found', complete: true, survivors: [], refuted: [], unjudged: [], preExisting: [] }
  }
  if (!review) return failedAxis(axis.name, 'the reviewer did not return')
  // A failed record fails the axis but keeps its findings: losing a real blocker is worse than a skimpy review.
  const placed = axis.name === 'Spec' ? partitionElsewhere(review.elsewhere) : null
  review = { ...review, findings: review.findings.map(finding => ({ ...finding, file: repoPath(finding.file) })) }
  const notVerifiableHere = placed && placed.accepted.length ? `; not verifiable here: ${elsewhereNote(placed.accepted)}` : ''
  const skippedOut = review.findings.filter(finding => skippedFiles.has(finding.file))
  const skipOutNote = skippedOut.length ? `, ${skippedOut.length} in skipped files dropped` : ''
  const routed = routePreExisting(review.findings.filter(finding => !skippedOut.includes(finding)))
  const { preExisting } = routed
  const preExistingNote = preExisting.length ? `, ${preExisting.length} pre-existing` : ''
  // On a re-review, a finding at a line nobody touched since the last round was that round's to raise; a Spec
  // finding that names an AC-N stays, since Spec maps every AC-N across the whole branch every round.
  const namesAc = finding => axis.name === 'Spec' && specAcs.some(ac => ac.named.test(String(finding.claim)))
  const outsideDelta = delta && delta.used
    ? routed.kept.filter(finding => typeof finding.line === 'number' && !namesAc(finding) && !isChanged(delta.changed, finding.file, finding.line))
    : []
  const kept = routed.kept.filter(finding => !outsideDelta.includes(finding))
  // Only a finding the workflow keeps maps an AC-N: one it dropped or set apart says nothing the caller will see.
  const unchecked = uncheckedReason(axis, review, placed, kept)
  const outsideNote = outsideDelta.length ? `, ${outsideDelta.length} outside the delta dropped` : ''
  const serious = kept.filter(worthSkeptic)
  const unverified = kept
    .filter(finding => !worthSkeptic(finding))
    .map(finding => ({ ...finding, unverified: true }))
  const judged = (await pipeline(serious, (finding, _item, index) => judge(axis, finding, index, placed ? placed.accepted : [])))
    .map((j, i) => j || unjudgedAfterThrow(serious[i]))
  const withVerdict = verdict => judged.filter(j => j.verdict === verdict)
  const unjudged = withVerdict('unjudged')
  if (unjudged.length > 0) log(`${axis.name}: ${unjudged.length} findings have no skeptic verdict`)
  return {
    axis: axis.name,
    status: unchecked
      ? `failed: ${unchecked}${skipOutNote}${preExistingNote}${outsideNote}${notVerifiableHere}`
      : `${light ? 'reviewed (light)' : 'reviewed'}: ${review.findings.length} findings raised, ${unverified.length} left unverified${skipOutNote}${preExistingNote}${outsideNote}${notVerifiableHere}`,
    complete: !unchecked,
    checked: review.checked,
    ...(placed ? { elsewhere: placed.accepted } : {}),
    survivors: [
      ...withVerdict('survived').map(j => ({ ...j.finding, upheldBecause: j.reasons, failedVotes: j.failed })),
      ...unverified,
    ],
    refuted: withVerdict('refuted').map(j => ({ ...j.finding, refutedBecause: j.reasons, failedVotes: j.failed })),
    unjudged: unjudged.map(j => ({ ...j.finding, reasons: j.reasons, failedVotes: j.failed })),
    preExisting,
    listed: kept.map(listingKey),
  }
}

function reviewOne(axis) {
  if (!axis.active) return { skipped: true, findings: [] }
  return agent(axisPrompt(axis), {
    label: `${axis.name} reviewer`,
    phase: axis.name,
    schema: axis.schema || FINDINGS_SCHEMA,
    agentType: 'compost:reviewer',
  })
}

async function reviewLight() {
  const active = AXES.filter(axis => axis.active)
  const review = await agent(lightPrompt(active), {
    label: 'Light reviewer',
    phase: 'Standards',
    schema: lightFindingsSchema(active.map(axis => axis.name)),
    agentType: 'compost:reviewer',
  }).catch(() => null)
  // The schema allows only active axes; a finding that slips through untagged stays under Standards, never dropped.
  const axisOf = finding => (active.some(axis => axis.name === finding.axis) ? finding.axis : 'Standards')
  const share = axis => review && {
    findings: review.findings.filter(finding => axisOf(finding) === axis.name),
    checked: (review.checked || {})[axis.name],
    elsewhere: review.elsewhere,
  }
  return pipeline(AXES, axis => (axis.active ? share(axis) : { skipped: true, findings: [] }), settleAxis)
}

const results = light ? await reviewLight() : await pipeline(AXES, reviewOne, settleAxis)

const [standards, spec] = results.map((result, i) => result || failedAxis(AXES[i].name, 'the review stage threw'))

// The guide's minor cap holds for the whole review: Standards' minors first, each axis in the order its reviewer
// listed them. Unjudged minors count too, since the caller treats them as survivors.
let minorBudget = minorCap
let minorsCut = 0
for (const axisResult of [standards, spec]) {
  const listed = axisResult.listed || []
  const minors = [...axisResult.survivors, ...axisResult.unjudged]
    .filter(finding => finding.severity === 'minor')
    .sort((a, b) => listed.indexOf(listingKey(a)) - listed.indexOf(listingKey(b)))
  const cut = minors.slice(minorBudget)
  minorBudget = Math.max(0, minorBudget - minors.length)
  minorsCut += cut.length
  axisResult.survivors = axisResult.survivors.filter(finding => !cut.includes(finding))
  axisResult.unjudged = axisResult.unjudged.filter(finding => !cut.includes(finding))
  if (cut.length) axisResult.status += `, ${cut.length} minors cut by the cap`
  delete axisResult.listed
}

function worst(axisResult) {
  const order = ['blocker', 'major', 'minor']
  const sorted = [...axisResult.survivors].sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity))
  return sorted.length ? `${sorted[0].severity}: ${sorted[0].claim}` : 'none'
}

const complete = standards.complete && spec.complete

return {
  base: scope.base,
  head: scope.head,
  specSource,
  risk,
  path: light ? 'light' : 'full',
  ...(delta ? { delta: delta.used ? { used: true, since: delta.since } : delta } : {}),
  complete,
  ...(complete ? {} : { problem: [standards, spec].filter(a => !a.complete).map(a => `${a.axis} ${a.status}`).join('; ') }),
  standards,
  spec,
  guide: { source: guide.source, minorCap, ...(guideProblem ? { problem: guideProblem } : {}) },
  ...(checks.length ? { checks: checks.map(({ name, status, why }) => ({ name, status, why })) } : {}),
  notRun: NOT_RUN,
  summary: [
    ...[standards, spec]
      .map(a => `${a.axis}: ${a.status}, ${a.survivors.length} survived, ${a.refuted.length} refuted, ${a.unjudged.length} unjudged; worst ${worst(a)}`),
    `Review guide: ${guide.source}; minor cap ${minorCap}, ${minorsCut} cut${guideProblem ? ` (${guideProblem})` : ''}`,
    ...(checks.length ? [`Checks: ${checks.map(check => `${check.name} ${check.status}`).join('; ')}`] : []),
    `Not run here: ${NOT_RUN.join('; ')}`,
  ].join('\n'),
}
