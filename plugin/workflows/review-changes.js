// ABOUTME: Compost's review workflow: Standards and Spec reviewers in parallel over a branch diff, or one reviewer on both for a small one.
// ABOUTME: Skeptics try to refute each finding worth one (Jev's triage, else every blocker and major); survivors, refutations, and unjudged findings come back side by side.
export const meta = {
  name: 'review-changes',
  description: 'Review a branch along two axes, Standards and Spec (one reviewer on both for a small, non-structural diff), then have skeptics try to refute every finding worth one (by Jev triage, else every blocker and major)',
  whenToUse: 'After verify passes on an issue, or whenever a branch or work-in-progress diff needs review, whatever its size. Pass {base, head, issue, skeptics, jev, full}, all optional: base defaults to the merge-base with the default branch, head to HEAD, issue to one found in the commits or branch name, skeptics (votes per finding worth a skeptic) to 1, jev (the path to compost scripts/jev.py, which ranks files by structural risk) to none, full (force separate Standards and Spec reviewers on a small diff) to false. A diff of 50 changed lines or fewer that Jev ranks and finds not structural gets one reviewer covering both axes. A bare string is treated as base.',
  phases: [
    { title: 'Scope', detail: 'pin the base, the diff, the spec, and the standards sources; rank files by structural risk' },
    { title: 'Standards', detail: 'reviewer against instructions files, CONTEXT.md, ADRs, and the canon (on a small diff, one light reviewer covers both axes here); skeptics refute each finding worth one' },
    { title: 'Spec', detail: 'reviewer against the issue AC-N and interfaces; skeptics refute each finding worth one' },
  ],
}

const input = typeof args === 'object' && args !== null ? args : { base: args }
const skepticsPerFinding = input.skeptics || 1
const head = input.head || 'HEAD'
const jevScript = input.jev || ''
const forceFull = Boolean(input.full)
// At or under this many changed lines, with Jev finding no structural file, one reviewer covers both axes.
const LIGHT_MAX_CHANGED_LINES = 50

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
    standardsSources: { type: 'array', items: { type: 'string' } },
    spec: {
      type: 'object',
      required: ['found', 'source', 'id', 'text'],
      properties: {
        found: { type: 'boolean' },
        source: { type: 'string', description: 'Issue URL, issue id, or file path; empty when not found' },
        id: { type: 'string', description: 'The id of the issue fetched, exactly as the tracker writes it (42, bd-a1b2.3, group/project#12); empty for a spec file or when not found' },
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
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
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

const riskStep = jevScript
  ? `\n4. Rank the changed files by structural risk: write \`{"base": "<base-sha>", "head": "<head-sha>"}\` to a temp file and run \`uv run ${jevScript} review-risk --input <file>\`. Set risk to \`{ranked: true, structural, files}\` from its output, keeping each file's file, score, and structural. If it exits non-zero, set risk to \`{ranked: false, structural: false, files: [], problem: "<first line of stderr>"}\`.`
  : ''

const scope = await agent(
  `Scope a code review of the changes up to \`${head}\`. Do not review anything yet.

${baseHint} The head under review is \`${head}\`.
1. Resolve the fixed point and the head with \`git rev-parse\`. Record repo as the owner/name in \`git remote get-url origin\` (no host, no .git), or the name of the directory \`git rev-parse --show-toplevel\` prints when there is no origin. Record diffCommand as \`git diff <base-sha>...<head-sha>\` (three dots, against the merge-base), shortstat as the line \`git diff --shortstat <base-sha>...<head-sha>\` prints, verbatim, the commits from \`git log --oneline <base-sha>..<head-sha>\`, and the changed files from \`git diff --name-only <base-sha>...<head-sha>\`.
2. ${issueHint} Fetch it, with its comments, using the read command docs/agents/issue-tracker.md gives for this repo's tracker, and pass the id to it exactly as written: it may be dotted (bd-a1b2.3) or name another project (group/project#12), so never turn it into a number or drop its project. Only if that file is missing, use \`gh api repos/{owner}/{repo}/issues/<n>\` and \`gh api repos/{owner}/{repo}/issues/<n>/comments --paginate\`. Wherever the read goes through \`gh\`, use \`gh api\` (REST): \`gh issue view\` goes through GraphQL, which cloud sessions block. Copy the spec into spec.text with every heading in it, verbatim: its user stories, every AC-N, and any interfaces, under the headings they sit under (a heading can say which repository a criterion belongs to). If an issue was given and fetching it fails, set spec to \`{found: false, source: "", id: "", text: "", problem: "<the error you got>"}\` and carry on with the rest. Set spec.id to the id of the issue you fetched, as the tracker writes it, or "" for a spec file.
3. List the standards sources that exist: CLAUDE.md and AGENTS.md at the root and in directories the diff touches, CONTEXT.md or CONTEXT-MAP.md, docs/adr/*.md, CODING_STANDARDS.md, CONTRIBUTING.md, and linter or formatter configs (so reviewers know what tooling already enforces).${riskStep}

If the fixed point does not resolve or the diff is empty, say so in problem and return every other field empty: base, head, repo, diffCommand, and shortstat as "", commits, files, and standardsSources as [], and spec as \`{found: false, source: "", id: "", text: ""}\`.`,
  { label: 'scope', phase: 'Scope', schema: SCOPE_SCHEMA, effort: 'low' },
)

if (!scope || scope.problem || scope.files.length === 0) {
  const problem = scope ? scope.problem || 'The diff is empty.' : 'The scoping agent did not return.'
  log(problem)
  return { complete: false, problem }
}

const specSource = input.issue ? issueRef(issueId) : scope.spec.source

function issueFetchProblem() {
  if (!input.issue) return ''
  if (!scope.spec.found) return scope.spec.problem || 'the scoping agent returned no spec'
  if (issueRef(scope.spec.id) !== specSource) return `the scoping agent fetched ${issueRef(scope.spec.id)} instead`
  return ''
}

const fetchProblem = issueFetchProblem()
const specProblem = fetchProblem ? `issue ${specSource} could not be fetched: ${fetchProblem}` : ''
if (specProblem) log(specProblem)

log(`Reviewing ${scope.files.length} files across ${scope.commits.length} commits since ${scope.base.slice(0, 8)}`)

const readAtHead = head === 'HEAD'
  ? ''
  : `\nThe working tree may not be at the head under review: read changed files with \`git show ${scope.head}:<path>\`, not from disk.`

const risk = jevScript && scope.risk && scope.risk.ranked
  ? { ranked: true, structural: scope.risk.structural, files: scope.risk.files }
  : { ranked: false, structural: null, files: [], problem: riskProblem() }

function riskProblem() {
  if (!jevScript) return 'no jev path given'
  if (!scope.risk) return 'the scoping agent returned no risk ranking'
  return scope.risk.problem || 'review-risk failed'
}

const fileList = risk.ranked
  ? `Changed files, riskiest first (structural risk 0-4 from Jev; read the top ones first):
${risk.files.map(f => `${f.file} (${f.score.toFixed(2)}${f.structural ? ', structural' : ''})`).join('\n')}`
  : `Changed files:
${scope.files.join('\n')}`

const diffContext = `Diff: \`${scope.diffCommand}\`${readAtHead}
Commits:
${scope.commits.join('\n')}
${fileList}`

const repoUnderReview = String(scope.repo || '')
const IN_REPO = `This diff is in ${repoUnderReview || 'a repository the scoping agent could not name'}.`

const SPEC_ONLY = `Grade only against the spec text in this prompt. Do not fetch any issue or spec file yourself (no \`gh issue view\`, no \`gh api\` on issues), even when the diff, the commits, or the conversation name a different one.`

const AXES = [
  {
    name: 'Standards',
    question: "does the code follow this repo's documented standards and domain language?",
    active: true,
    checks: `Standards sources in this repo:
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

Under checked, list each rule you read against the diff and each changed file you opened, at the file:line you read.`,
  },
  {
    name: 'Spec',
    question: 'does the code do what the originating issue asked, no more and no less?',
    active: scope.spec.found && !specProblem,
    problem: specProblem,
    schema: SPEC_FINDINGS_SCHEMA,
    checks: `Spec source: ${specSource}
${scope.spec.text}

${SPEC_ONLY}

${IN_REPO} A spec can span several repositories, each built and reviewed on its own branch. When the spec itself places an AC-N in another repository (it names that repo on the AC-N's line before its id, or in a heading over it), this diff cannot meet it: raise no finding for it, and list it under elsewhere with the repo exactly as the spec names it there. The workflow keeps an entry only when that name is on the AC-N's own line before its id or in a heading over it. An AC-N the spec does not place in another repository belongs to this one, however unlikely that looks: judge it here. An AC-N with a part in each repo is judged here on this repo's part.

Report:
- Each AC-N that is missing or only partly met. Quote the AC-N; point at the test that should prove it, or say none exists.
- Each interface in the spec whose shape in the code differs from what the spec states.
- Behaviour in the diff nobody asked for (scope creep), at file:line.
- Each AC-N that looks implemented but where the implementation looks wrong.

Under checked, map every acceptance criterion not under elsewhere: one entry per AC-N, naming it and its verdict (met, partly met, unmet), at the test or code line that shows it. An AC-N with no code or test to point at is a finding (line null) whose claim names it instead.`,
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
  const specText = axis.name === 'Spec' ? `\nThe spec the finding was judged against:\n${scope.spec.text}\n${SPEC_ONLY}\n${placed}` : ''
  return `A reviewer made the ${axis.name} finding below about the diff \`${scope.diffCommand}\`. Your job is to refute it.${readAtHead}
${specText}
Finding (${finding.severity}) at ${location}:
Claim: ${finding.claim}
Evidence: ${finding.evidence}

Read the code at that location and whatever it depends on. Check that the quoted rule or AC-N exists and says what the reviewer claims, that the code does what the claim says, and that nothing elsewhere (a test, a caller, a documented exception, a later hunk) already answers it. A finding that is a style nit a configured linter owns, or that asks for something nobody uses (YAGNI), is refuted.

Set refuted to true unless you confirmed the finding yourself against the code. When you are uncertain, it is refuted.`
}

async function judge(axis, finding, index, elsewhere) {
  const votes = await parallel(
    Array.from({ length: skepticsPerFinding }, (_, vote) => () =>
      agent(skepticPrompt(axis, finding, elsewhere), {
        label: `${axis.name} skeptic ${index + 1}.${vote + 1}`,
        phase: axis.name,
        schema: VERDICT_SCHEMA,
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

function worthSkeptic(finding) {
  return typeof finding.skeptic === 'boolean' ? finding.skeptic : finding.severity !== 'minor'
}

function unjudgedAfterThrow(finding) {
  return { finding, verdict: 'unjudged', failed: skepticsPerFinding, reasons: ['the skeptic stage threw'] }
}

function failedAxis(name, status) {
  return { axis: name, status: `failed: ${status}`, complete: false, survivors: [], refuted: [], unjudged: [] }
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
const specAcs = [...new Set(String(scope.spec.text || '').match(/\bAC-\d+\b/g) || [])]
  .map(id => ({ id, named: new RegExp(`\\b${id}\\b`) }))

const specLines = String(scope.spec.text || '').split('\n')
const headingLevel = line => ((line.match(/^\s*(#{1,6})\s/) || [])[1] || '').length

// The line that defines an AC-N, its id followed by a colon ("#### AC-3:", "- **AC-3**:"), so a story or another
// criterion that mentions it first does not decide where it lives. Without one, its first mention.
function definitionOf(ac) {
  const defines = new RegExp(`${ac.named.source}\\**\\s*:`)
  const at = specLines.findIndex(line => defines.test(line))
  return at >= 0 ? at : specLines.findIndex(line => ac.named.test(line))
}

// The spec text that can place an AC-N in a repo: its defining line before its id, and the headings over that line.
function placementOf(ac) {
  const at = definitionOf(ac)
  const placing = [specLines[at].slice(0, specLines[at].search(ac.named))]
  let level = headingLevel(specLines[at]) || 7
  for (const line of specLines.slice(0, at).reverse()) {
    const own = headingLevel(line)
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
    return `the spec does not place it in ${repo} (on its line before its id, or in a heading over it)`
  }
  return ''
}

// Splits the reviewer's elsewhere list into the entries the spec backs and the first reason each other AC-N was refused.
function sortElsewhere(entries) {
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
function uncheckedReason(axis, review, placed) {
  const entries = Array.isArray(review.checked) ? review.checked : []
  if (entries.length === 0) {
    return review.findings.length ? 'the reviewer did not say what it checked' : 'the reviewer returned no findings and no record of what it checked'
  }
  const cited = entries.filter(entry => entry && FILE_LINE.test(String(entry.at || '')))
  if (cited.length === 0) return 'the reviewer cited no file:line for anything it checked'
  if (axis.name !== 'Spec') return ''
  // A finding about an AC-N (one with no line to cite, or one only partly met) maps it too. Its claim must
  // name the AC-N: evidence quotes AC-Ns in passing, which says nothing about whether they were checked.
  const named = [...cited.map(entry => entry.item), ...review.findings.map(f => f.claim)].map(String)
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
    return { axis: axis.name, status: 'skipped: no spec found', complete: true, survivors: [], refuted: [], unjudged: [] }
  }
  if (!review) return failedAxis(axis.name, 'the reviewer did not return')
  // A failed record fails the axis but keeps its findings: losing a real blocker is worse than a skimpy review.
  const placed = axis.name === 'Spec' ? sortElsewhere(review.elsewhere) : null
  const unchecked = uncheckedReason(axis, review, placed)
  const notVerifiableHere = placed && placed.accepted.length ? `; not verifiable here: ${elsewhereNote(placed.accepted)}` : ''
  const serious = review.findings.filter(worthSkeptic)
  const unverified = review.findings
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
      ? `failed: ${unchecked}${notVerifiableHere}`
      : `${light ? 'reviewed (light)' : 'reviewed'}: ${review.findings.length} findings raised, ${unverified.length} left unverified${notVerifiableHere}`,
    complete: !unchecked,
    checked: review.checked,
    ...(placed ? { elsewhere: placed.accepted } : {}),
    survivors: [
      ...withVerdict('survived').map(j => ({ ...j.finding, upheldBecause: j.reasons, failedVotes: j.failed })),
      ...unverified,
    ],
    refuted: withVerdict('refuted').map(j => ({ ...j.finding, refutedBecause: j.reasons, failedVotes: j.failed })),
    unjudged: unjudged.map(j => ({ ...j.finding, reasons: j.reasons, failedVotes: j.failed })),
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
  complete,
  ...(complete ? {} : { problem: [standards, spec].filter(a => !a.complete).map(a => `${a.axis} ${a.status}`).join('; ') }),
  standards,
  spec,
  summary: [standards, spec]
    .map(a => `${a.axis}: ${a.status}, ${a.survivors.length} survived, ${a.refuted.length} refuted, ${a.unjudged.length} unjudged; worst ${worst(a)}`)
    .join('\n'),
}
