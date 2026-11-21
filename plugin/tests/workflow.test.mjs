// ABOUTME: Runs workflows/review-changes.js against stub agent/parallel/pipeline hooks that follow the Workflow
// ABOUTME: tool's contract (a failed agent returns null, parallel and pipeline turn throws into null) to pin its verdicts.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const source = readFileSync(new URL('../workflows/review-changes.js', import.meta.url), 'utf8')
const AsyncFunction = (async () => {}).constructor
const script = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', source.replace('export const meta', 'const meta'))

const SCOPE = {
  base: 'b'.repeat(40),
  head: 'h'.repeat(40),
  diffCommand: 'git diff bbb...hhh',
  commits: ['abc1234 add export'],
  files: ['app/export.py'],
  standardsSources: ['CLAUDE.md'],
  spec: { found: true, source: '#7', id: '7', text: 'AC-1: Given a list, When exported, Then a CSV downloads' },
}
const BLOCKER = { file: 'app/export.py', line: 12, severity: 'blocker', claim: 'CSV is not escaped', evidence: 'AC-1 at #7; app/export.py:12' }
const MINOR = { file: 'app/export.py', line: 3, severity: 'minor', claim: 'name drifts from CONTEXT.md', evidence: 'CONTEXT.md: Reading list' }
const STANDARDS_CHECKED = [{ item: 'CLAUDE.md: escape every export', at: 'app/export.py:12' }]
const SPEC_CHECKED = [{ item: 'AC-1 met by test_export_csv', at: 'tests/test_export.py:8' }]

async function run(args, answer) {
  const prompts = {}
  const schemas = {}
  const agentTypes = {}
  const agent = async (prompt, opts) => {
    prompts[opts.label] = prompt
    schemas[opts.label] = opts.schema
    agentTypes[opts.label] = opts.agentType
    return answer(opts.label, prompt)
  }
  const parallel = thunks => Promise.all(thunks.map(thunk => thunk().catch(() => null)))
  const pipeline = (items, ...stages) =>
    Promise.all(items.map(async (item, index) => {
      try {
        let previous = item
        for (const stage of stages) previous = await stage(previous, item, index)
        return previous
      } catch {
        return null
      }
    }))
  const result = await script(args, agent, parallel, pipeline, () => {}, () => {})
  return { result, prompts, schemas, agentTypes }
}

function reviewers({ standards = { findings: [BLOCKER, MINOR], checked: STANDARDS_CHECKED }, spec = { findings: [], checked: SPEC_CHECKED }, light = { findings: [], checked: { Standards: STANDARDS_CHECKED, Spec: SPEC_CHECKED } }, skeptic = { refuted: false, reason: 'confirmed' }, scope = SCOPE } = {}) {
  return label => {
    if (label === 'scope') return scope
    if (label === 'Standards reviewer') return typeof standards === 'function' ? standards() : standards
    if (label === 'Spec reviewer') return spec
    if (label === 'Light reviewer') return typeof light === 'function' ? light() : light
    return typeof skeptic === 'function' ? skeptic(label) : skeptic
  }
}

test('a confirmed blocker survives and a minor finding is kept unverified without a skeptic', async () => {
  const { result, prompts } = await run({ issue: 7 }, reviewers())
  assert.equal(result.complete, true)
  assert.deepEqual(result.standards.survivors.map(f => f.severity), ['blocker', 'minor'])
  assert.equal(result.standards.survivors[1].unverified, true)
  assert.deepEqual(Object.keys(prompts).filter(label => label.includes('skeptic')), ['Standards skeptic 1.1'])
  assert.match(result.summary, /Standards: reviewed: 2 findings raised, 1 left unverified, 2 survived, 0 refuted, 0 unjudged; worst blocker/)
})

test('with Jev triage, the skeptic flag decides who gets a skeptic, whatever the severity', async () => {
  const confidentMajor = { ...BLOCKER, severity: 'major', line: 20, skeptic: false }
  const unsureMinor = { ...MINOR, skeptic: true }
  const { result, prompts } = await run({}, reviewers({ standards: { findings: [confidentMajor, unsureMinor], checked: STANDARDS_CHECKED } }))
  assert.deepEqual(Object.keys(prompts).filter(label => label.includes('skeptic')), ['Standards skeptic 1.1'])
  assert.match(prompts['Standards skeptic 1.1'], /name drifts from CONTEXT\.md/)
  assert.deepEqual(result.standards.survivors.map(f => [f.line, f.unverified === true]), [[3, false], [20, true]])
})

test('given a jev path, scope ranks files by structural risk and reviewers read the riskiest first', async () => {
  const risk = {
    ranked: true,
    structural: true,
    files: [{ file: 'app/cache.py', score: 3.4, structural: true }, { file: 'app/export.py', score: 1.2, structural: false }],
  }
  const { result, prompts } = await run({ jev: '/plugin/scripts/jev.py' }, reviewers({ scope: { ...SCOPE, risk } }))
  assert.match(prompts.scope, /uv run \/plugin\/scripts\/jev\.py review-risk --input/)
  assert.match(prompts['Standards reviewer'], /riskiest first[^\n]*\napp\/cache\.py \(3\.40, structural\)\napp\/export\.py \(1\.20\)/)
  assert.deepEqual(result.risk, risk)
})

test('without a jev path, the scope agent ranks with the jev.py its agent definition names', async () => {
  const risk = { ranked: true, structural: false, files: [{ file: 'app/export.py', score: 1.2, structural: false }] }
  const { result, prompts } = await run({}, reviewers({ scope: { ...SCOPE, risk } }))
  assert.match(prompts.scope, /run review-risk with the jev\.py your agent definition names/)
  assert.doesNotMatch(prompts.scope, /uv run  review-risk/)
  assert.deepEqual(result.risk, risk)
})

test('when review-risk fails or returns nothing, files keep scope order and structural risk is unknown', async () => {
  const plain = await run({}, reviewers())
  assert.match(plain.prompts['Standards reviewer'], /Changed files:\napp\/export\.py/)
  assert.deepEqual(plain.result.risk, { ranked: false, structural: null, files: [], problem: 'the scoping agent returned no risk ranking' })
  const failedRisk = { ranked: false, structural: false, files: [], problem: 'jev unavailable: no key' }
  const failed = await run({ jev: '/plugin/scripts/jev.py' }, reviewers({ scope: { ...SCOPE, risk: failedRisk } }))
  assert.equal(failed.result.risk.structural, null)
  assert.equal(failed.result.risk.problem, 'jev unavailable: no key')
  const silent = await run({ jev: '/plugin/scripts/jev.py' }, reviewers({ scope: { ...SCOPE, risk: { ...failedRisk, problem: undefined } } }))
  assert.equal(silent.result.risk.problem, 'review-risk failed')
  const unranked = await run({ jev: '/plugin/scripts/jev.py' }, reviewers())
  assert.equal(unranked.result.risk.problem, 'the scoping agent returned no risk ranking')
})

test('scope and skeptics run as their own lean agent types, beside the reviewers', async () => {
  const { agentTypes, prompts } = await run({ issue: 7 }, reviewers())
  assert.deepEqual(agentTypes, {
    scope: 'compost:scope',
    'Standards reviewer': 'compost:reviewer',
    'Spec reviewer': 'compost:reviewer',
    'Standards skeptic 1.1': 'compost:skeptic',
  })
  // The checklist travels in the prompt too, so a skeptic whose definition did not load still knows what to check.
  assert.match(prompts['Standards skeptic 1.1'], /Read the code it cites and what that depends on.*nothing elsewhere \(a test, a caller, a later hunk\) already answers it/)
})

test('a spec passed in is graded as given, and the scope agent is told not to fetch one', async () => {
  const text = '## In ledger\nAC-1: Given a list, When exported, Then a CSV downloads'
  const unfetched = { ...SCOPE, spec: { found: false, source: '', id: '', text: '' } }
  for (const [args, source] of [[{ issue: 'OLI-66', spec: text }, 'OLI-66'], [{ spec: text }, 'the spec passed in']]) {
    const { result, prompts } = await run(args, reviewers({ scope: unfetched, spec: { findings: [BLOCKER], checked: SPEC_CHECKED } }))
    assert.match(prompts.scope, /The spec was passed in by the caller: do not fetch any issue or spec file/)
    assert.doesNotMatch(prompts.scope, /read command docs\/agents\/issue-tracker\.md gives/)
    assert.equal(result.specSource, source)
    assert.ok(prompts['Spec reviewer'].includes(`Spec source: ${source}\n${text}`), 'the Spec reviewer grades the given text')
    assert.ok(prompts['Spec skeptic 1.1'].includes(text), 'the Spec skeptic sees the given text')
    assert.equal(result.spec.complete, true)
  }
})

test('every result names the harness code review as not run here, and whenToUse sends callers to compost:review', async () => {
  const { result } = await run({}, reviewers())
  assert.deepEqual(result.notRun, [NOT_RUN])
  assert.match(result.summary, /\nNot run here: harness code review: not part of this workflow/)
  assert.match(source, /whenToUse: 'compost:review is the normal entry point/)
})

const NOT_RUN = 'harness code review: not part of this workflow; compost:review runs it beside this one on a diff that changes executable code'

const CHANGED = [{ file: 'app/export.py', lines: [[10, 14], [20, 21]] }]
const PRE_EXISTING = { file: 'app/books.py', line: 13, severity: 'pre-existing', claim: 'total_pages skips the last book', evidence: 'app/books.py:13 range(len(books) - 1)' }

test('a pre-existing finding at a line the diff left alone is recorded apart, with no skeptic, on either path', async () => {
  const untouched = [PRE_EXISTING, { ...PRE_EXISTING, file: 'app/export.py', line: 3 }]
  const full = await run({ issue: 7 }, reviewers({ scope: { ...SCOPE, changed: CHANGED }, standards: { findings: [BLOCKER, ...untouched], checked: STANDARDS_CHECKED } }))
  assert.deepEqual(full.result.standards.preExisting, untouched)
  assert.deepEqual(full.result.standards.survivors.map(f => f.claim), [BLOCKER.claim])
  assert.deepEqual(Object.keys(full.prompts).filter(label => label.includes('skeptic')), ['Standards skeptic 1.1'])
  assert.equal(full.result.complete, true)
  assert.match(full.result.summary, /Standards: reviewed: 3 findings raised, 0 left unverified, 2 pre-existing, 1 survived/)
  assert.deepEqual(full.result.spec.preExisting, [])

  const light = await run(JEV, reviewers({
    scope: { ...SMALL, changed: CHANGED },
    light: { findings: [{ ...PRE_EXISTING, axis: 'Spec' }], checked: CHECKED },
  }))
  assert.equal(light.result.path, 'light')
  assert.deepEqual(light.result.spec.preExisting.map(f => f.claim), [PRE_EXISTING.claim])
  assert.equal(light.result.spec.survivors.length, 0)
})

test('a pre-existing finding at a changed line, with no line, or with no changed lines to check is judged as a major', async () => {
  const cases = [
    [{ ...SCOPE, changed: CHANGED }, { ...PRE_EXISTING, file: 'app/export.py', line: 12 }],
    [{ ...SCOPE, changed: CHANGED }, { ...PRE_EXISTING, line: null }],
    [SCOPE, PRE_EXISTING],
  ]
  for (const [scope, finding] of cases) {
    const { result, prompts } = await run({}, reviewers({ scope, standards: { findings: [finding], checked: STANDARDS_CHECKED } }))
    assert.deepEqual(result.standards.preExisting, [])
    assert.equal(result.standards.survivors[0].severity, 'major', JSON.stringify(finding))
    assert.match(prompts['Standards skeptic 1.1'], /Finding \(major\)/)
  }
})

test('a failed or skipped axis carries an empty pre-existing list', async () => {
  const { result } = await run({}, reviewers({ standards: null, scope: { ...SCOPE, spec: { found: false, source: '', id: '', text: '' } } }))
  assert.deepEqual([result.standards.preExisting, result.spec.preExisting], [[], []])
})

const SINCE = 's'.repeat(40)
const DELTA = { used: true, since: SINCE, changed: [{ file: 'app/export.py', lines: [[12, 12]] }] }
const PRIOR = '- major app/export.py:3 name drifts from CONTEXT.md: pushed back, the glossary term is Export'

test('a re-review tells every reviewer to judge the lines changed since the last round, and Spec still maps every AC-N', async () => {
  const { prompts, result } = await run({ issue: 7, since: 'abc1234' }, reviewers({ scope: { ...SCOPE, changed: CHANGED, delta: DELTA } }))
  assert.match(prompts.scope, /This is a re-review: the last round reviewed `abc1234`/)
  for (const label of ['Standards reviewer', 'Spec reviewer']) {
    assert.match(prompts[label], new RegExp(`Judge only the lines changed since the last round, \`git diff ${SINCE} h{40}\``))
  }
  assert.match(prompts['Spec reviewer'], /map every acceptance criterion not under elsewhere, across the whole branch even on a re-review/)
  assert.deepEqual(result.delta, { used: true, since: SINCE })
  const first = await run({ issue: 7 }, reviewers())
  assert.doesNotMatch(first.prompts.scope, /This is a re-review/)
  assert.doesNotMatch(first.prompts['Standards reviewer'], /Judge only the lines changed/)
  assert.equal(first.result.delta, undefined)
})

test('on a re-review, findings at lines untouched since the last round are dropped before any skeptic; a null line stays', async () => {
  const stale = { ...BLOCKER, line: 20 }
  const absent = { ...BLOCKER, line: null, claim: 'AC-1 has no test' }
  for (const path of ['full', 'light']) {
    const scope = { ...(path === 'light' ? SMALL : SCOPE), changed: CHANGED, delta: DELTA }
    const findings = [BLOCKER, stale, absent, PRE_EXISTING]
    const answer = path === 'light'
      ? reviewers({ scope, light: { findings: findings.map(f => ({ ...f, axis: 'Standards' })), checked: CHECKED } })
      : reviewers({ scope, standards: { findings, checked: STANDARDS_CHECKED } })
    const { result, prompts } = await run({ ...JEV, since: 'abc1234' }, answer)
    assert.equal(result.path, path)
    assert.deepEqual(result.standards.survivors.map(f => f.line), [12, null], path)
    assert.deepEqual(result.standards.preExisting.map(f => f.claim), [PRE_EXISTING.claim], path)
    assert.equal(Object.keys(prompts).filter(label => label.includes('skeptic')).length, 2, path)
    assert.match(result.standards.status, /4 findings raised, 0 left unverified, 1 pre-existing, 1 outside the delta dropped/, path)
  }
})

test('prior rulings reach the reviewers and the skeptics, who refute a repeat of a pushed-back finding', async () => {
  const { prompts } = await run({ since: 'abc1234', prior: PRIOR }, reviewers({ scope: { ...SCOPE, delta: DELTA } }))
  for (const label of ['Standards reviewer', 'Spec reviewer', 'Standards skeptic 1.1']) {
    assert.ok(prompts[label].includes(PRIOR), `${label} sees the prior rulings`)
  }
  assert.match(prompts['Standards skeptic 1.1'], new RegExp(`repeats one pushed back on there is refuted, unless the code it cites changed since ${SINCE}`))
  const none = await run({}, reviewers())
  assert.doesNotMatch(none.prompts['Standards skeptic 1.1'], /Earlier rounds ruled/)
})

test('a since that does not resolve, is not an ancestor, or comes back unread gives a whole-branch review that says why', async () => {
  const cases = [
    [{ used: false, since: 'abc1234', changed: [], problem: 'abc1234 is not an ancestor of the head' }, 'abc1234 is not an ancestor of the head'],
    [undefined, 'the scoping agent returned no delta'],
  ]
  for (const [scopeDelta, problem] of cases) {
    const stale = { ...BLOCKER, line: 20 }
    const { result, prompts } = await run({ since: 'abc1234' }, reviewers({ scope: { ...SCOPE, changed: CHANGED, delta: scopeDelta }, standards: { findings: [stale], checked: STANDARDS_CHECKED } }))
    assert.deepEqual(result.delta, { used: false, since: 'abc1234', problem })
    assert.doesNotMatch(prompts['Standards reviewer'], /Judge only the lines changed/)
    assert.deepEqual(result.standards.survivors.map(f => f.line), [20])
  }
})

const minors = (n, file = 'app/export.py') => Array.from({ length: n }, (_, i) => ({ ...MINOR, file, line: 30 + i, claim: `minor ${file} ${i}` }))
const GUIDE = { source: 'REVIEW.md', minorCap: 2, failure: 'a change that drops a reading list entry', skip: 'migrations/' }

test('without a REVIEW.md, every reviewer gets the default guide and the result names it', async () => {
  const { result, prompts } = await run({}, reviewers({ scope: { ...SCOPE, guide: { source: 'defaults', minorCap: 5, failure: '', skip: '' } } }))
  for (const label of ['Standards reviewer', 'Spec reviewer']) {
    assert.match(prompts[label], /Review guide \(defaults; this repo has no REVIEW\.md\)/)
    assert.match(prompts[label], /breaks behaviour, loses or leaks data, or blocks a rollback/)
    assert.match(prompts[label], /at most 5 for the whole review/)
    assert.match(prompts[label], /generated, vendored, and lock files/)
    assert.match(prompts[label], /cites a file:line/)
  }
  assert.deepEqual(result.guide, { source: 'defaults', minorCap: 5 })
  assert.match(result.summary, /Review guide: defaults; minor cap 5, 0 cut/)
  assert.match(prompts.scope, /REVIEW\.md/)
})

test('a REVIEW.md sets what failure means, the minor cap, and what to skip, and the scope agent reads it', async () => {
  const { result, prompts } = await run({}, reviewers({ scope: { ...SCOPE, guide: GUIDE } }))
  assert.match(prompts['Standards reviewer'], /this repo's REVIEW\.md/)
  assert.match(prompts['Standards reviewer'], /Failure: a change that drops a reading list entry/)
  assert.match(prompts['Standards reviewer'], /at most 2 for the whole review/)
  assert.match(prompts['Standards reviewer'], /Skip: migrations\//)
  assert.deepEqual(result.guide, { source: 'REVIEW.md', minorCap: 2 })
})

test('a missing or unreadable guide falls back to the defaults and says why', async () => {
  for (const [guide, problem] of [
    [undefined, 'the scoping agent returned no review guide'],
    [{ source: 'REVIEW.md', minorCap: -1 }, 'minor cap -1 is not a whole number; using 5'],
    [{ source: 'REVIEW.md', minorCap: 3, problem: 'Minor cap says "a few"' }, 'Minor cap says "a few"'],
  ]) {
    const { result } = await run({}, reviewers({ scope: { ...SCOPE, guide } }))
    assert.equal(result.guide.problem, problem)
    assert.match(result.summary, new RegExp(`\\(${problem.replace(/[()"]/g, '.')}\\)`))
  }
})

for (const [cap, standardsMinors, specMinors, keptStandards, keptSpec, cut] of [
  [5, 7, 0, 5, 0, 2],
  [2, 1, 1, 1, 1, 0],
  [0, 2, 1, 0, 0, 3],
  [3, 2, 2, 2, 1, 1],
]) {
  test(`a minor cap of ${cap} over ${standardsMinors} Standards and ${specMinors} Spec minors keeps ${keptStandards} and ${keptSpec}, Standards first`, async () => {
    const { result } = await run({}, reviewers({
      scope: { ...SCOPE, guide: { source: 'REVIEW.md', minorCap: cap } },
      standards: { findings: [BLOCKER, ...minors(standardsMinors)], checked: STANDARDS_CHECKED },
      spec: { findings: minors(specMinors, 'app/spec.py'), checked: SPEC_CHECKED },
    }))
    const keptMinors = axis => result[axis].survivors.filter(f => f.severity === 'minor').map(f => f.claim)
    assert.deepEqual(keptMinors('standards'), minors(standardsMinors).slice(0, keptStandards).map(f => f.claim))
    assert.deepEqual(keptMinors('spec'), minors(specMinors, 'app/spec.py').slice(0, keptSpec).map(f => f.claim))
    assert.ok(result.standards.survivors.some(f => f.severity === 'blocker'), 'the cap leaves blockers alone')
    assert.match(result.summary, new RegExp(`minor cap ${cap}, ${cut} cut`))
    assert.equal('listed' in result.standards, false)
    assert.equal('listed' in result.spec, false)
  })
}

test('the minor cap keeps the reviewer\'s listed order, however the survivors were settled', async () => {
  const listed = minors(3).reverse()
  const { result } = await run({}, reviewers({
    scope: { ...SCOPE, guide: { source: 'defaults', minorCap: 1 } },
    standards: { findings: listed, checked: STANDARDS_CHECKED },
  }))
  assert.deepEqual(result.standards.survivors.map(f => f.claim), [listed[0].claim])
  assert.match(result.standards.status, /2 minors cut by the cap/)
})

test('an unjudged minor counts against the cap like a survivor, in the reviewer\'s listed order', async () => {
  const [unsure, plain] = minors(2)
  const { result } = await run({}, reviewers({
    scope: { ...SCOPE, guide: { source: 'defaults', minorCap: 1 } },
    standards: { findings: [{ ...unsure, skeptic: true }, plain], checked: STANDARDS_CHECKED },
    skeptic: null,
  }))
  assert.deepEqual(result.standards.unjudged.map(f => f.claim), [unsure.claim])
  assert.deepEqual(result.standards.survivors.map(f => f.claim), [])
  assert.match(result.summary, /minor cap 1, 1 cut/)
})

test('the default guide the reviewers get is the one the REVIEW.md starter writes out', async () => {
  const starter = readFileSync(new URL('../skills/setup/references/review-md.md', import.meta.url), 'utf8')
  const { prompts } = await run({}, reviewers())
  const defaults = prompts['Standards reviewer'].split('Review guide (defaults; this repo has no REVIEW.md):\n')[1].split('\n').slice(0, 4)
  const sections = Object.fromEntries(starter.split('\n## ').slice(1).map(part => [part.split('\n')[0], part.split('\n').slice(1).join(' ').trim()]))
  const said = line => line.replace(/^- \w+: /, '').toLowerCase()
  assert.equal(defaults.length, 4)
  assert.equal(said(defaults[0]), sections.Failure.split('```')[0].trim().toLowerCase())
  assert.match(defaults[1], new RegExp(`at most ${sections['Minor cap'].split(' ')[0]} for the whole review`))
  assert.equal(said(defaults[2]), sections.Skip.toLowerCase())
  assert.equal(said(defaults[3]), sections.Evidence.split('```')[0].trim().toLowerCase())
})

test('findings in files the guide skips are dropped before any skeptic, and reviewers are told which files those are', async () => {
  const lockFinding = { ...BLOCKER, file: 'requirements.lock', line: 2, claim: 'pinned version is old' }
  const { result, prompts } = await run({}, reviewers({
    scope: { ...SCOPE, files: ['app/export.py', 'requirements.lock'], skipped: ['requirements.lock'] },
    standards: { findings: [BLOCKER, lockFinding], checked: STANDARDS_CHECKED },
  }))
  assert.match(prompts['Standards reviewer'], /Skipped by the review guide; raise nothing in these: requirements\.lock/)
  assert.deepEqual(result.standards.survivors.map(f => f.file), ['app/export.py'])
  assert.equal(Object.keys(prompts).filter(label => label.includes('skeptic')).length, 1)
  assert.match(result.standards.status, /2 findings raised, 0 left unverified, 1 in skipped files dropped/)
})

test('on a re-review, a Spec finding that names an AC-N stays wherever its line is, and only kept findings map an AC-N', async () => {
  const unmetAc = { ...BLOCKER, line: 40, claim: 'AC-1 is only partly met: no test exports a quoted title' }
  const { result } = await run({ since: SINCE }, reviewers({
    scope: { ...SCOPE, delta: DELTA },
    standards: { findings: [{ ...BLOCKER, line: 40, claim: 'a style lapse at an untouched line' }], checked: STANDARDS_CHECKED },
    spec: { findings: [unmetAc], checked: [{ item: 'read the export module', at: 'app/export.py:1' }] },
  }))
  assert.deepEqual(result.standards.survivors, [])
  assert.deepEqual(result.spec.survivors.map(f => f.claim), [unmetAc.claim])
  assert.equal(result.spec.complete, true)

  const dropped = await run({}, reviewers({
    scope: { ...SCOPE, files: ['app/export.py', 'gen/schema_pb2.py'], skipped: ['gen/schema_pb2.py'] },
    spec: { findings: [{ ...unmetAc, file: 'gen/schema_pb2.py', line: 2 }], checked: [{ item: 'read the export module', at: 'app/export.py:1' }] },
  }))
  assert.match(dropped.result.spec.status, /^failed: the reviewer did not map AC-1 to the code/)
})

test('a finding cited with a ./ prefix or an absolute path is matched to the changed file it names', async () => {
  for (const file of ['./app/export.py', '/home/dev/repo/app/export.py']) {
    const { result, prompts } = await run({}, reviewers({
      scope: { ...SCOPE, changed: CHANGED },
      standards: { findings: [{ ...PRE_EXISTING, file, line: 12 }], checked: STANDARDS_CHECKED },
    }))
    assert.deepEqual(result.standards.preExisting, [], file)
    assert.deepEqual(result.standards.survivors.map(f => [f.file, f.severity]), [['app/export.py', 'major']], file)
    assert.ok(prompts['Standards skeptic 1.1'], file)
  }
})

test('with uncommitted edits to a changed file, every agent reads the committed head, since line numbers decide routing', async () => {
  const { prompts } = await run({}, reviewers({ scope: { ...SCOPE, dirty: true } }))
  for (const label of ['Standards reviewer', 'Spec reviewer', 'Standards skeptic 1.1']) {
    assert.match(prompts[label], new RegExp(`git show ${SCOPE.head}:<path>`), label)
  }
  const clean = await run({}, reviewers())
  assert.doesNotMatch(clean.prompts['Standards reviewer'], /git show/)
  assert.match(clean.prompts.scope, /git status --porcelain/)
})

test('a blocker whose every skeptic failed is unjudged, not refuted', async () => {
  const { result } = await run({}, reviewers({ skeptic: null }))
  assert.deepEqual(result.standards.refuted, [])
  assert.equal(result.standards.unjudged.length, 1)
  assert.equal(result.standards.unjudged[0].failedVotes, 1)
  assert.equal(result.complete, true)
})

test('with three skeptics, a failed vote does not count and a split among the rest refutes', async () => {
  const votes = { '1': null, '2': { refuted: false, reason: 'holds' }, '3': { refuted: true, reason: 'tested elsewhere' } }
  const skeptic = label => votes[label.split('.').pop()]
  const { result } = await run({ skeptics: 3 }, reviewers({ skeptic }))
  assert.equal(result.standards.refuted.length, 1)
  assert.equal(result.standards.refuted[0].failedVotes, 1)
  assert.deepEqual(result.standards.refuted[0].refutedBecause, ['holds', 'tested elsewhere'])
})

test('a reviewer that returns nothing or throws marks its axis and the review incomplete', async () => {
  const silent = await run({}, reviewers({ standards: null }))
  assert.equal(silent.result.standards.status, 'failed: the reviewer did not return')
  assert.equal(silent.result.complete, false)
  const thrown = await run({}, reviewers({ standards: () => { throw new Error('boom') } }))
  assert.equal(thrown.result.standards.status, 'failed: the review stage threw')
  assert.equal(thrown.result.complete, false)
})

test('an issue that cannot be fetched fails the Spec axis instead of skipping it', async () => {
  const scope = { ...SCOPE, spec: { found: false, source: '', id: '', text: '', problem: 'gh: not authenticated' } }
  const { result, prompts } = await run({ issue: 42 }, reviewers({ scope }))
  assert.equal(result.spec.status, 'failed: issue #42 could not be fetched: gh: not authenticated')
  assert.equal(result.complete, false)
  assert.equal(prompts['Spec reviewer'], undefined)
})

test('a given issue is the only spec source, whatever issue the scoping agent picked from the conversation', async () => {
  const relayed = { ...SCOPE, spec: { ...SCOPE.spec, source: '#53' } }
  const graded = await run({ issue: 7 }, reviewers({ scope: relayed, spec: { findings: [BLOCKER], checked: SPEC_CHECKED } }))
  assert.equal(graded.result.specSource, '#7')
  assert.match(graded.prompts['Spec reviewer'], /Spec source: #7\n/)
  for (const label of ['Spec reviewer', 'Spec skeptic 1.1']) {
    const prompt = graded.prompts[label]
    assert.ok(prompt.includes(SCOPE.spec.text), `${label} carries the spec text`)
    assert.match(prompt, /Grade only against the spec text in this prompt\. Do not fetch any issue or spec file yourself/)
  }

  const swapped = { ...SCOPE, spec: { found: true, source: '#53', id: '53', text: 'AC-1: Given issue 53' } }
  const refused = await run({ issue: 7 }, reviewers({ scope: swapped }))
  assert.equal(refused.result.specSource, '#7')
  assert.equal(refused.result.spec.status, 'failed: issue #7 could not be fetched: the scoping agent fetched #53 instead')
  assert.equal(refused.result.complete, false)
  assert.equal(refused.prompts['Spec reviewer'], undefined)
})

test('a dotted beads id or a cross-project GitLab issue is fetched and graded as written', async () => {
  for (const id of ['bd-a1b2.3', 'group/project#12']) {
    const fetched = { ...SCOPE, spec: { ...SCOPE.spec, source: id, id } }
    const { result, prompts } = await run({ issue: id }, reviewers({ scope: fetched, spec: { findings: [BLOCKER], checked: SPEC_CHECKED } }))
    assert.equal(result.specSource, id)
    assert.ok(prompts.scope.includes(`The originating issue is \`${id}\``), `${id} reaches the scoping agent verbatim`)
    assert.match(prompts.scope, /read command docs\/agents\/issue-tracker\.md gives/)
    assert.match(prompts['Spec reviewer'], new RegExp(`Spec source: ${id.replace(/[.#/]/g, '\\$&')}\\n`))
    assert.deepEqual(result.spec.survivors.map(f => f.claim), [BLOCKER.claim])
  }

  const sibling = { ...SCOPE, spec: { ...SCOPE.spec, source: 'bd-a1b2.4', id: 'bd-a1b2.4' } }
  const refused = await run({ issue: 'bd-a1b2.3' }, reviewers({ scope: sibling }))
  assert.equal(refused.result.spec.status, 'failed: issue bd-a1b2.3 could not be fetched: the scoping agent fetched bd-a1b2.4 instead')
  assert.equal(refused.prompts['Spec reviewer'], undefined)
})

test('an issue given as a "#42" string matches a fetched 42 and refuses a fetched 43', async () => {
  const fetched = id => ({ ...SCOPE, spec: { ...SCOPE.spec, source: `#${id}`, id } })
  const matched = await run({ issue: '#42' }, reviewers({ scope: fetched('42') }))
  assert.equal(matched.result.specSource, '#42')
  assert.ok(matched.prompts['Spec reviewer'], 'the Spec reviewer runs')

  const swapped = await run({ issue: '#42' }, reviewers({ scope: fetched('43') }))
  assert.equal(swapped.result.spec.status, 'failed: issue #42 could not be fetched: the scoping agent fetched #43 instead')
})

test('without an issue, the spec source is what scope found, and a missing spec skips the Spec axis', async () => {
  const specFile = { ...SCOPE, spec: { found: true, source: 'docs/specs/export.md', id: '', text: 'AC-1: Given a list' } }
  const found = await run({}, reviewers({ scope: specFile }))
  assert.equal(found.result.specSource, 'docs/specs/export.md')
  assert.match(found.prompts['Spec reviewer'], /Spec source: docs\/specs\/export\.md\n/)

  const scope = { ...SCOPE, spec: { found: false, source: '', id: '', text: '' } }
  const { result } = await run({}, reviewers({ scope }))
  assert.equal(result.spec.status, 'skipped: no spec found')
  assert.equal(result.specSource, '')
  assert.equal(result.complete, true)
})

test('a failed scope or an empty diff returns the problem and spawns no reviewers', async () => {
  for (const [scope, problem] of [[null, 'The scoping agent did not return.'], [{ ...SCOPE, files: [] }, 'The diff is empty.']]) {
    const { result, prompts } = await run({}, reviewers({ scope }))
    assert.deepEqual(result, { complete: false, problem, notRun: [NOT_RUN] })
    assert.deepEqual(Object.keys(prompts), ['scope'])
  }
})

test('a bare string is the base, and a head other than HEAD tells every agent to read files at that commit', async () => {
  const bare = await run('release-1.2', reviewers())
  assert.match(bare.prompts.scope, /release-1\.2/)
  const pinned = await run({ base: 'abc^1', head: 'abc^2' }, reviewers())
  assert.match(pinned.prompts['Standards reviewer'], /git show h{40}:<path>/)
  assert.match(pinned.prompts['Standards skeptic 1.1'], /git show h{40}:<path>/)
})

const NOT_STRUCTURAL = { ranked: true, structural: false, files: [{ file: 'app/export.py', score: 0.4, structural: false }] }
const SMALL = { ...SCOPE, shortstat: ' 3 files changed, 40 insertions(+), 10 deletions(-)', risk: NOT_STRUCTURAL }
const JEV = { jev: '/plugin/scripts/jev.py' }
const CHECKED = { Standards: STANDARDS_CHECKED, Spec: SPEC_CHECKED }
const reviewerLabels = prompts => Object.keys(prompts).filter(label => label.endsWith('reviewer'))

test('a diff of 50 changed lines or fewer that Jev ranks not structural gets one reviewer on both axes, split by axis tag', async () => {
  const specBlocker = { ...BLOCKER, line: 30, claim: 'AC-1 has no test', axis: 'Spec' }
  const light = { findings: [{ ...BLOCKER, axis: 'Standards' }, { ...MINOR, axis: 'Standards' }, specBlocker], checked: CHECKED }
  const { result, prompts, schemas } = await run({ ...JEV, issue: 7 }, reviewers({ scope: SMALL, light }))
  assert.equal(result.path, 'light')
  assert.deepEqual(reviewerLabels(prompts), ['Light reviewer'])
  assert.deepEqual(schemas['Light reviewer'].properties.findings.items.properties.axis.enum, ['Standards', 'Spec'])
  assert.match(prompts['Light reviewer'], /Standards axis/)
  assert.match(prompts['Light reviewer'], /Spec axis/)
  assert.ok(prompts['Light reviewer'].includes(SCOPE.spec.text))
  assert.match(prompts['Light reviewer'], /Grade only against the spec text in this prompt/)
  assert.deepEqual(result.standards.survivors.map(f => f.claim), ['CSV is not escaped', 'name drifts from CONTEXT.md'])
  assert.deepEqual(result.spec.survivors.map(f => f.claim), ['AC-1 has no test'])
  assert.equal(result.spec.checked, CHECKED.Spec)
  assert.deepEqual(Object.keys(prompts).filter(label => label.includes('skeptic')).sort(), ['Spec skeptic 1.1', 'Standards skeptic 1.1'])
  assert.equal(result.complete, true)
  assert.match(result.summary, /Standards: reviewed \(light\): 2 findings raised, 1 left unverified/)
})

test('the changed line count is insertions plus deletions parsed from the scope agent\'s shortstat line', async () => {
  const cases = [
    [' 3 files changed, 40 insertions(+), 10 deletions(-)', 'light'],
    [' 3 files changed, 40 insertions(+), 11 deletions(-)', 'full'],
    [' 1 file changed, 50 deletions(-)', 'light'],
    [' 1 file changed, 51 insertions(+)', 'full'],
    ['', 'full'],
    [undefined, 'full'],
  ]
  for (const [shortstat, path] of cases) {
    const { result } = await run(JEV, reviewers({ scope: { ...SMALL, shortstat }, light: { findings: [], checked: CHECKED } }))
    assert.equal(result.path, path, JSON.stringify(shortstat))
  }
  const { prompts } = await run({}, reviewers())
  assert.match(prompts.scope, /git diff --shortstat/)
})

test('a structural file, Jev unavailable or never run, or a truthy full runs the two-reviewer path', async () => {
  const structural = { ranked: true, structural: true, files: [{ file: 'app/export.py', score: 3.1, structural: true }] }
  const cases = [
    [JEV, { ...SMALL, risk: structural }],
    [{}, { ...SMALL, risk: undefined }],
    [JEV, { ...SMALL, risk: { ranked: false, structural: false, files: [], problem: 'jev unavailable' } }],
    [JEV, { ...SMALL, risk: undefined }],
    [{ ...JEV, full: true }, SMALL],
    [{ ...JEV, full: 'true' }, SMALL],
  ]
  for (const [args, scope] of cases) {
    const { result, prompts } = await run(args, reviewers({ scope }))
    assert.equal(result.path, 'full', JSON.stringify(args) + JSON.stringify(scope.risk))
    assert.deepEqual(reviewerLabels(prompts), ['Standards reviewer', 'Spec reviewer'])
  }
})

test('on the light path, a reviewer that returns nothing or throws fails every active axis', async () => {
  for (const light of [null, () => { throw new Error('boom') }]) {
    const { result } = await run({ ...JEV, issue: 7 }, reviewers({ scope: SMALL, light }))
    assert.equal(result.standards.status, 'failed: the reviewer did not return')
    assert.equal(result.spec.status, 'failed: the reviewer did not return')
    assert.equal(result.complete, false)
  }
})

test('on the light path, an axis the reviewer did not say it checked fails, however few its findings', async () => {
  const light = { findings: [{ ...MINOR, axis: 'Standards' }], checked: { Standards: CHECKED.Standards, Spec: [] } }
  const { result } = await run({ ...JEV, issue: 7 }, reviewers({ scope: SMALL, light }))
  assert.equal(result.standards.complete, true)
  assert.equal(result.spec.status, 'failed: the reviewer returned no findings and no record of what it checked')
  assert.equal(result.complete, false)
})

test('on the light path, an unfetchable issue fails the Spec axis, a missing spec skips it, and only active axes can be tagged', async () => {
  const unfetched = { ...SMALL, spec: { found: false, source: '', id: '', text: '', problem: 'gh: not authenticated' } }
  const standardsOnly = { findings: [{ ...MINOR, axis: 'Standards' }], checked: { Standards: CHECKED.Standards } }
  const failed = await run({ ...JEV, issue: 42 }, reviewers({ scope: unfetched, light: standardsOnly }))
  assert.equal(failed.result.spec.status, 'failed: issue #42 could not be fetched: gh: not authenticated')
  assert.equal(failed.result.standards.survivors.length, 1)
  assert.doesNotMatch(failed.prompts['Light reviewer'], /Spec axis/)
  assert.deepEqual(failed.schemas['Light reviewer'].properties.findings.items.properties.axis.enum, ['Standards'])
  assert.deepEqual(failed.schemas['Light reviewer'].properties.checked.required, ['Standards'])
  assert.equal(failed.result.complete, false)

  const missing = { ...SMALL, spec: { found: false, source: '', id: '', text: '' } }
  const strayTag = { ...standardsOnly, findings: [{ ...MINOR, axis: 'Spec' }, { ...BLOCKER }] }
  const skipped = await run(JEV, reviewers({ scope: missing, light: strayTag }))
  assert.equal(skipped.result.spec.status, 'skipped: no spec found')
  assert.equal(skipped.result.standards.survivors.length, 2, 'findings tagged for no active axis stay under Standards')
  assert.equal(skipped.result.complete, true)
})

test('a reviewer that returns no findings and no record of what it checked fails its axis and says why', async () => {
  for (const spec of [{ findings: [] }, { findings: [], checked: [] }]) {
    const { result } = await run({ issue: 7 }, reviewers({ spec }))
    assert.equal(result.spec.status, 'failed: the reviewer returned no findings and no record of what it checked')
    assert.equal(result.spec.complete, false)
    assert.equal(result.complete, false)
    assert.equal(result.problem, 'Spec failed: the reviewer returned no findings and no record of what it checked')
    assert.match(result.summary, /Spec: failed: the reviewer returned no findings and no record/)
  }
  const { result, prompts } = await run({ issue: 7 }, reviewers({ standards: { findings: [BLOCKER, MINOR] } }))
  assert.equal(result.standards.status, 'failed: the reviewer did not say what it checked')
  assert.equal(result.complete, false)
  assert.deepEqual(result.standards.survivors.map(f => f.claim), [BLOCKER.claim, MINOR.claim], 'findings from an unchecked review are kept')
  assert.ok(prompts['Standards skeptic 1.1'], 'and still go to a skeptic')
})

test('a record of what was checked counts only where it cites a file:line', async () => {
  const anchored = await run({ issue: 7 }, reviewers({ standards: { findings: [], checked: [{ item: 'CLAUDE.md rules', at: 'CLAUDE.md#L4' }] } }))
  assert.equal(anchored.result.standards.complete, true, 'a file#L anchor is a file:line')
  const uncited = [{ item: 'read CLAUDE.md', at: 'CLAUDE.md' }, { item: 'ran the greps', at: '' }]
  const { result } = await run({ issue: 7 }, reviewers({ standards: { findings: [], checked: uncited } }))
  assert.equal(result.standards.status, 'failed: the reviewer cited no file:line for anything it checked')
  assert.equal(result.complete, false)
})

test('a reviewer with no findings and a cited record of what it checked is complete and shows that record', async () => {
  const { result, schemas, prompts } = await run({ issue: 7 }, reviewers({ standards: { findings: [], checked: STANDARDS_CHECKED } }))
  assert.match(prompts['Standards reviewer'], /Under checked, list each rule you read against the diff and each changed file you opened, at the file:line/)
  assert.equal(result.complete, true)
  assert.equal(result.problem, undefined)
  assert.equal(result.standards.status, 'reviewed: 0 findings raised, 0 left unverified')
  assert.deepEqual(result.standards.checked, STANDARDS_CHECKED)
  assert.deepEqual(result.spec.checked, SPEC_CHECKED)
  for (const label of ['Standards reviewer', 'Spec reviewer']) {
    assert.deepEqual(schemas[label].required, ['findings', 'checked'], `${label} must say what it checked`)
  }
})

test('a clean Spec review maps every AC-N in the spec, and one that leaves an AC-N out fails', async () => {
  const text = 'AC-1: Given a list, Then a CSV\nAC-2: Given an empty list, Then a header row\nAC-10: Given unicode, Then UTF-8'
  const scope = { ...SCOPE, spec: { ...SCOPE.spec, text } }
  const all = [
    { item: 'AC-1 met by test_export_csv', at: 'tests/test_export.py:8' },
    { item: 'AC-2 met by test_empty_export', at: 'tests/test_export.py:20' },
    { item: 'AC-10 met by test_unicode', at: 'tests/test_export.py:31' },
  ]
  const mapped = await run({ issue: 7 }, reviewers({ scope, spec: { findings: [], checked: all } }))
  assert.equal(mapped.result.complete, true)
  assert.deepEqual(mapped.result.spec.checked.map(entry => entry.item.split(' ')[0]), ['AC-1', 'AC-2', 'AC-10'])
  assert.match(mapped.prompts['Spec reviewer'], /one entry per AC-N/)

  const uncitedAc2 = { item: 'AC-2 met', at: 'tests' }
  const gaps = await run({ issue: 7 }, reviewers({ scope, spec: { findings: [], checked: [all[0], uncitedAc2] } }))
  assert.equal(gaps.result.spec.status, 'failed: the reviewer did not map AC-2, AC-10 to the code')
  assert.equal(gaps.result.complete, false)

  const missingAc2 = { file: 'app/export.py', line: null, severity: 'blocker', claim: 'AC-2 has no code or test', evidence: 'AC-2 at #7' }
  const named = await run({ issue: 7 }, reviewers({ scope, spec: { findings: [missingAc2], checked: [all[0], all[2]] } }))
  assert.equal(named.result.spec.complete, true, 'an AC-N with no line to cite is mapped by the finding that names it')

  const inPassing = { ...BLOCKER, claim: 'CSV is not escaped', evidence: 'AC-2 at #7; app/export.py:12' }
  const incidental = await run({ issue: 7 }, reviewers({ scope, spec: { findings: [inPassing], checked: [all[0], all[2]] } }))
  assert.equal(incidental.result.spec.status, 'failed: the reviewer did not map AC-2 to the code', 'an AC-N quoted only in evidence is not mapped')

  const prefixOnly = await run({ issue: 7 }, reviewers({ scope, spec: { findings: [], checked: all.slice(1) } }))
  assert.equal(prefixOnly.result.spec.status, 'failed: the reviewer did not map AC-1 to the code', 'AC-10 does not map AC-1')
})

const SPLIT_SPEC = '## In notes-fork\n\n### 1. Export\n\n#### AC-1: Given a list, When exported, Then a CSV downloads\n\n## In agent-plugins\n\n### 2. Skill\n\n#### AC-2: Given the export skill, When loaded, Then it lists CSV\n- notes-web: AC-3: Given the web view, Then a webhook fires'
const SPLIT_SCOPE = { ...SCOPE, repo: 'JoshuaOliphant/notes-fork', spec: { ...SCOPE.spec, text: SPLIT_SPEC } }
const ELSEWHERE = { ac: 'AC-2', repo: 'agent-plugins' }
const AC3_CHECKED = [...SPEC_CHECKED, { item: 'AC-3 met by test_webhook', at: 'tests/test_web.py:4' }]

test('an AC-N the spec places in another repo is listed as not verifiable here, on the full and the light path', async () => {
  const unmetAc2 = { file: 'app/export.py', line: null, severity: 'blocker', claim: 'AC-2 has no code in this diff', evidence: 'AC-2 at #7' }
  const full = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [], checked: AC3_CHECKED, elsewhere: [ELSEWHERE] } }))
  assert.equal(full.result.complete, true)
  assert.deepEqual(full.result.spec.elsewhere, [ELSEWHERE])
  assert.equal(full.result.spec.status, 'reviewed: 0 findings raised, 0 left unverified; not verifiable here: AC-2 (agent-plugins)')
  assert.match(full.result.summary, /Spec: reviewed: 0 findings raised, 0 left unverified; not verifiable here: AC-2 \(agent-plugins\), 0 survived/)
  assert.match(full.prompts.scope, /git remote get-url origin/)
  assert.match(full.prompts.scope, /every heading in it, verbatim/)
  assert.match(full.prompts['Spec reviewer'], /This diff is in JoshuaOliphant\/notes-fork\./)
  assert.match(full.prompts['Spec reviewer'], /under elsewhere/)
  assert.ok(full.schemas['Spec reviewer'].properties.elsewhere, 'the Spec reviewer can return elsewhere')
  assert.equal(full.schemas['Standards reviewer'].properties.elsewhere, undefined)

  const skeptics = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [unmetAc2], checked: AC3_CHECKED, elsewhere: [ELSEWHERE] } }))
  assert.match(skeptics.prompts['Spec skeptic 1.1'], /This diff is in JoshuaOliphant\/notes-fork\. The spec places AC-2 \(agent-plugins\) in another repository, so this diff cannot meet them: a finding that one of them is missing here is refuted\. Every other AC-N belongs to this repo\./)
  const none = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [unmetAc2], checked: AC3_CHECKED } }))
  assert.equal(none.result.complete, true, 'the finding maps AC-2')
  assert.doesNotMatch(none.prompts['Spec skeptic 1.1'], /another repository/, 'with nothing placed elsewhere, skeptics get no repo rule')

  const light = { findings: [], checked: { ...CHECKED, Spec: AC3_CHECKED }, elsewhere: [ELSEWHERE] }
  const small = await run({ ...JEV, issue: 7 }, reviewers({ scope: { ...SMALL, ...SPLIT_SCOPE }, light }))
  assert.equal(small.result.path, 'light')
  assert.equal(small.result.complete, true)
  assert.deepEqual(small.result.spec.elsewhere, [ELSEWHERE])
  assert.equal(small.result.standards.elsewhere, undefined, 'elsewhere belongs to the Spec axis only')
  assert.ok(small.schemas['Light reviewer'].properties.elsewhere, 'the light reviewer can return elsewhere')
  assert.match(small.prompts['Light reviewer'], /This diff is in JoshuaOliphant\/notes-fork\./)
})

test('the spec places an AC-N elsewhere only on its own line before its id or in a heading over it', async () => {
  const placed = [
    [{ ac: 'AC-2', repo: 'Agent-Plugins' }, 'a heading over the AC-N, any case'],
    [{ ac: 'ac-2 ', repo: 'agent-plugins' }, 'the AC-N id in any case or spacing'],
    [{ ac: 'AC-3', repo: 'notes-web' }, 'its own line before its id'],
  ]
  for (const [entry, why] of placed) {
    const ac = entry.ac.trim().toUpperCase()
    const checked = AC3_CHECKED.filter(item => !item.item.startsWith(ac))
    const elsewhere = ac === 'AC-2' ? [entry] : [ELSEWHERE, entry]
    const { result } = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [], checked, elsewhere } }))
    assert.equal(result.complete, true, why)
  }
  const refused = [
    [{ ac: 'AC-3', repo: 'web' }, 'AC-3', 'the spec does not place it in web (on its defining line before its id, or in a heading over that line)'],
    [{ ac: 'AC-3', repo: 'notes' }, 'AC-3', 'the spec does not place it in notes (on its defining line before its id, or in a heading over that line)'],
    [{ ac: 'AC-1', repo: 'agent-plugins' }, 'AC-1', 'the spec does not place it in agent-plugins (on its defining line before its id, or in a heading over that line)'],
    [{ ac: 'AC-2', repo: 'agent.plugins' }, 'AC-2', 'the spec does not place it in agent.plugins (on its defining line before its id, or in a heading over that line)'],
    [{ ac: 'AC-2', repo: ' ' }, 'AC-2', 'it names no repo'],
    [{ ac: 'AC-2', repo: 'notes-fork' }, 'AC-2', 'notes-fork is the repo under review'],
    [{ ac: 'AC-2', repo: 'upstream/NOTES-FORK' }, 'AC-2', 'upstream/NOTES-FORK is the repo under review'],
  ]
  for (const [entry, ac, why] of refused) {
    const checked = AC3_CHECKED.filter(item => !item.item.startsWith(ac))
    const elsewhere = ac === 'AC-2' ? [entry] : [ELSEWHERE, entry]
    const { result } = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [], checked, elsewhere } }))
    const note = ac === 'AC-2' ? '' : '; not verifiable here: AC-2 (agent-plugins)'
    assert.equal(result.spec.status, `failed: the reviewer did not map ${ac} to the code (refused ${ac} elsewhere: ${why})${note}`, why)
    assert.equal(result.complete, false)
  }
  const later = { ...SPLIT_SCOPE, spec: { ...SPLIT_SCOPE.spec, text: '## In agent-plugins\n#### AC-2: two\n## In notes-fork\n#### AC-1: one' } }
  const sibling = await run({ issue: 7 }, reviewers({ scope: later, spec: { findings: [], checked: [{ item: 'spec read', at: 'docs/spec.md:1' }], elsewhere: [ELSEWHERE, { ac: 'AC-1', repo: 'agent-plugins' }] } }))
  assert.match(sibling.result.spec.status, /refused AC-1 elsewhere: the spec does not place it in agent-plugins/, 'a heading closed by a later one of its level does not place what follows')

  const fenced = '## In notes-fork\n```sh\n# install agent-plugins first\n```\n~~~~\n## In agent-plugins\n```\n~~~~\n#### AC-1: one\n## In agent-plugins\n````md\n# notes-fork\n````\n#### AC-2: two'
  const fence = { ...SPLIT_SCOPE, spec: { ...SPLIT_SCOPE.spec, text: fenced } }
  const comment = await run({ issue: 7 }, reviewers({ scope: fence, spec: { findings: [], checked: [{ item: 'spec read', at: 'docs/spec.md:1' }], elsewhere: [ELSEWHERE, { ac: 'AC-1', repo: 'agent-plugins' }] } }))
  assert.match(comment.result.spec.status, /refused AC-1 elsewhere: the spec does not place it in agent-plugins/, 'a "# " line inside a code fence (``` or ~~~, closed only by its own kind) is not a heading')
  const real = await run({ issue: 7 }, reviewers({ scope: fence, spec: { findings: [], checked: [{ item: 'AC-1 met', at: 'tests/t.py:1' }], elsewhere: [ELSEWHERE] } }))
  assert.equal(real.result.complete, true, 'a real heading outside any fence still places the AC-N under it')

  const crossRef = { ...SPLIT_SCOPE, spec: { ...SPLIT_SCOPE.spec, text: 'As a user (see AC-2, AC-3)\n## In notes-fork\n#### AC-1: keeps AC-2 and AC-3 working\n## Elsewhere\n- **AC-2** in agent-plugins? no: two\n- web-ui: AC-3: three' } }
  const crossElsewhere = [{ ac: 'AC-2', repo: 'Elsewhere' }, { ac: 'AC-3', repo: 'web-ui' }]
  const defined = await run({ issue: 7 }, reviewers({ scope: crossRef, spec: { findings: [], checked: [{ item: 'AC-1 met', at: 'tests/t.py:1' }], elsewhere: crossElsewhere } }))
  assert.equal(defined.result.complete, true, 'placement is read where the AC-N is defined (leading its line, or followed by a colon), not where it is first mentioned')

  const unknownRepo = await run({ issue: 7 }, reviewers({ scope: { ...SPLIT_SCOPE, repo: '' }, spec: { findings: [], checked: AC3_CHECKED, elsewhere: [ELSEWHERE] } }))
  assert.equal(unknownRepo.result.spec.status, 'failed: the reviewer did not map AC-2 to the code (refused AC-2 elsewhere: the repo under review is unknown)')

  const noise = [{ ac: 'AC-2', repo: 'notes-fork' }, ELSEWHERE, { ...ELSEWHERE, repo: 'AGENT-PLUGINS' }, { ac: 'AC-2)', repo: 'agent-plugins' }, { ac: 'AC-9', repo: 'x' }, null]
  const deduped = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [], checked: AC3_CHECKED, elsewhere: noise } }))
  assert.deepEqual(deduped.result.spec.elsewhere, [ELSEWHERE], 'an AC-N is listed once; an id the spec lacks, regex characters and all, not at all')
  const firstReason = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [], checked: AC3_CHECKED, elsewhere: [{ ac: 'AC-2', repo: 'notes-fork' }, { ac: 'AC-2', repo: '' }] } }))
  assert.match(firstReason.result.spec.status, /refused AC-2 elsewhere: notes-fork is the repo under review\)$/, 'the first refusal is the one reported')

  const twoRepos = await run({ issue: 7 }, reviewers({ scope: SPLIT_SCOPE, spec: { findings: [], checked: SPEC_CHECKED, elsewhere: [ELSEWHERE, { ac: 'AC-3', repo: 'notes-web' }] } }))
  assert.match(twoRepos.result.spec.status, /not verifiable here: AC-2 \(agent-plugins\); AC-3 \(notes-web\)$/)
  const oneRepo = { ...SPLIT_SCOPE, spec: { ...SPLIT_SCOPE.spec, text: '## In agent-plugins\n#### AC-1: one\n#### AC-2: two' } }
  const grouped = await run({ issue: 7 }, reviewers({ scope: oneRepo, spec: { findings: [], checked: [], elsewhere: [{ ac: 'AC-1', repo: 'agent-plugins' }, { ac: 'AC-2', repo: 'Agent-Plugins' }] } }))
  assert.equal(grouped.result.spec.status, 'failed: the reviewer returned no findings and no record of what it checked; not verifiable here: AC-1, AC-2 (agent-plugins)', 'elsewhere is no record of what was checked, and a failed axis still says what lives elsewhere')
  const groupedChecked = await run({ issue: 7 }, reviewers({ scope: oneRepo, spec: { findings: [], checked: [{ item: 'spec read', at: 'docs/spec.md:1' }], elsewhere: [{ ac: 'AC-1', repo: 'agent-plugins' }, { ac: 'AC-2', repo: 'Agent-Plugins' }] } }))
  assert.match(groupedChecked.result.spec.status, /not verifiable here: AC-1, AC-2 \(agent-plugins\)$/, 'one repo spelled two ways is one group')
})

test('meta is a pure literal naming every phase the script uses', () => {
  const literal = source.match(/export const meta = (\{[\s\S]*?\n\})/)[1]
  const meta = Function(`return ${literal}`)()
  assert.equal(meta.name, 'review-changes')
  assert.deepEqual(meta.phases.map(phase => phase.title), ['Scope', 'Standards', 'Spec'])
})
