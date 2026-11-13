// ABOUTME: Engine tests for skill-drift: which turns are judged, the hits written to the session's log file, and /drift.
// ABOUTME: Jev's HTTP answers and skill_drift.py's run are stubbed at the engine boundary; the Python suite reads the hit back.
import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import writtenHit from './skill-drift-hit.ts'

type Asked = { state: Record<string, unknown>; questions: Record<string, unknown> }
type Ran = { exitCode: number; stdout: string; stderr: string } | 'refused'
type Sent = { url: string; authorization: string; model: unknown }
type World = { agents: Record<string, unknown[] | 'deny'>; asked: Asked[]; sent: Sent[]; keychain: number; files: Map<string, string>; toasts: string[]; order: string[]; ran: string[][]; drift: Ran }

// compost's folder, the root the engine loads the mod from (this file sits in its tests/).
const PLUGIN_ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '')
const LOG = '/home/me/.claude/skill-drift/1970-01-01-session-9.jsonl'

const TURN = [
  { role: 'user', text: 'run the verify gates', toolUses: [] },
  {
    role: 'assistant',
    text: 'Running the gates.',
    toolUses: [{ tool_use_id: 't1', tool: 'Bash', input: { command: 'uv run pytest' }, text: 'no such command', isError: true }],
  },
  { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 't1', text: 'no such command', isError: true }] },
  { role: 'assistant', text: 'Gates pass.', toolUses: [] },
]

function engine(
  on: On,
  answers: Record<string, number> | 'outage',
  messages: unknown[] = TURN,
  key: string | null = 'test-key',
  env: Record<string, string> = {},
): World {
  const world: World = { agents: {}, asked: [], sent: [], keychain: 0, files: new Map(), toasts: [], order: [], ran: [], drift: { exitCode: 0, stdout: '', stderr: '' } }
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('command.register', () => ({ value: { command: 'drift' } }) as never)
  on('skill.prompt', (_$, e) => ({ text: e.text }))
  on('turn.complete', (_$, e) => ({ text: e.answer }) as never)
  on('prompt.submit', (_$, e) => {
    world.order.push('prompt entered')
    return { text: e.text, context: e.context } as never
  })
  on('session.messages', (_$, e) => {
    const { agentId } = e as { agentId?: string }
    const transcript = agentId === undefined ? messages : world.agents[agentId]
    return (transcript === 'deny' ? { value: { deny: 'unknown agent' } } : { value: transcript }) as never
  })
  on('session.id', () => ({ value: 'session-9' }) as never)
  on('env.get', (_$, e) => {
    const { name } = e as { name: string }
    const values: Record<string, string | undefined> = { HOME: '/home/me', TYPESAFE_API_KEY: key ?? undefined, ...env }
    return { value: values[name] } as never
  })
  on('process.run', (_$, e) => {
    const { argv } = e as { argv: string[] }
    if (argv[0] === 'security') world.keychain += 1
    if (argv[0] !== 'uv') return { value: { exitCode: 44, stdout: '', stderr: 'not found' } } as never
    world.ran.push(argv)
    return (world.drift === 'refused' ? { deny: 'uv is not installed' } : { value: world.drift }) as never
  })
  on('clock.now', () => ({ value: 1000 }) as never)
  on('ui.toast', (_$, e) => {
    world.toasts.push(String((e as { text: string }).text))
    return { value: undefined } as never
  })
  on('fs.exists', (_$, e) => {
    const path = (e as { path: string }).path
    return { value: world.files.has(path) || [...world.files.keys()].some(file => file.startsWith(`${path}/`)) } as never
  })
  // A read that yields, as a real disk read does, so two writers that overlap both read before either writes.
  on('fs.read', async (_$, e) => {
    const text = world.files.get((e as { path: string }).path)
    await new Promise(resolve => setTimeout(resolve, 5))
    return { value: text } as never
  })
  on('fs.write', (_$, e) => {
    const { path, text } = e as { path: string; text: string }
    world.files.set(path, text)
    return { value: undefined } as never
  })
  on('fs.list', (_$, e) => {
    const dir = (e as { path: string }).path
    const names = [...world.files.keys()].filter(file => file.startsWith(`${dir}/`)).map(file => file.slice(dir.length + 1))
    return { value: names.map(name => ({ name, kind: 'file', size: 1, mtimeMs: 0, isLink: false })) } as never
  })
  on('http.fetch', (_$, e) => {
    const { url, init } = e as { url: string; init: { body: string; headers: Record<string, string> } }
    const body = JSON.parse(init.body) as Asked & { model: unknown }
    world.asked.push(body)
    world.sent.push({ url, authorization: init.headers.Authorization, model: body.model })
    world.order.push('jev asked')
    if (answers === 'outage') return { value: { status: 503, ok: false, headers: {}, text: 'unavailable' } } as never
    const out = Object.fromEntries(Object.keys(body.questions).map(id => [id, { type: 'noul', noul: answers[id] ?? 0 }]))
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ answers: out }) } } as never
  })
  return world
}

function logged(world: World): Record<string, unknown>[] {
  return (world.files.get(LOG) ?? '').split('\n').filter(Boolean).map(line => JSON.parse(line))
}

const TYPED = { kind: 'composer' }
const START = { cwd: '/tmp', surface: 'terminal', isInteractive: true } as const
const ENDED = { answer: 'Gates pass.', durationMs: 10, isAborted: false, turnId: 'turn-1', reason: 'answer' } as never

test('a turn that used a skill is judged against it and its drift is logged', async ($, on) => {
  const world = engine(on, { deviated: 0.92, missing_guidance: 0.4 })
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'Run `uv run pytest` for the gates.' })
  await $.turn.complete(ENDED)
  expect(world.asked.length).toBe(1)
  expect(Object.keys(world.asked[0].questions)).toEqual(['deviated', 'missing_guidance'])
  expect(JSON.stringify(world.asked[0].state)).toContain('ERROR no such command')
  expect(logged(world)).toEqual([writtenHit])
  expect(world.toasts).toEqual([])
})

const STEPPED = [
  '# Verify',
  '',
  '1. **Read the issue.** Find the tracker and read its acceptance criteria.',
  '',
  '2. **Run the gates.** Run `uv run pytest`',
  '   and record its output.',
].join('\n')

test('a skill with numbered steps is judged step by step, and deviates by its likeliest skipped step', async ($, on) => {
  const world = engine(on, { 'step 1': 0.81, 'step 2': 0.2, missing_guidance: 0.1 })
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: STEPPED })
  await $.turn.complete(ENDED)
  const questions = world.asked[0].questions as Record<string, { instructions: string }>
  expect(Object.keys(questions)).toEqual(['missing_guidance', 'step 1', 'step 2'])
  expect(questions['step 2'].instructions).toContain('step 2 of that skill, "Run the gates", which begins: Run `uv run pytest` and record its output.')
  expect(logged(world)).toMatchObject([{ skill: 'compost:verify', kind: 'deviated', p: 0.81 }])
  expect(String(logged(world)[0].evidence)).toStartWith('Likeliest skipped step: 1. Read the issue (p=0.81)\nUSER: run the verify gates')
})

test('a skill whose lists both number from 1 asks every step and names the one that scored', async ($, on) => {
  const twoLists = `${STEPPED}\n\n## Picking up\n\n1. **Read the trail.** Find the status comment.\n\n2. **Resume.** Carry on.`
  const world = engine(on, { 'step 1': 0.3, 'step 2': 0.4, 'step 3': 0.88, 'step 4': 0.5, missing_guidance: 0.1 })
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:pause', text: twoLists })
  await $.turn.complete(ENDED)
  const questions = world.asked[0].questions as Record<string, { instructions: string }>
  expect(Object.keys(questions)).toEqual(['missing_guidance', 'step 1', 'step 2', 'step 3', 'step 4'])
  expect(questions['step 1'].instructions).toContain('"Read the issue"')
  expect(questions['step 3'].instructions).toContain('step 1 of that skill, "Read the trail"')
  expect(String(logged(world)[0].evidence)).toStartWith('Likeliest skipped step: 1. Read the trail (p=0.88)')
})

test('a stepped skill whose every step scores under the threshold logs nothing', async ($, on) => {
  const world = engine(on, { 'step 1': 0.72, 'step 2': 0.3, missing_guidance: 0.2 })
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: STEPPED })
  await $.turn.complete(ENDED)
  expect(world.asked.length).toBe(1)
  expect(logged(world)).toEqual([])
})

test('by default the hook asks TypeSafe for jev-latest', async ($, on) => {
  const world = engine(on, {})
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  expect(world.sent).toEqual([{ url: 'https://api.typesafe.ai/v1/systemone', authorization: 'Bearer test-key', model: 'jev-latest' }])
})

test('pointed at Ollaya, the hook asks its model there without the Keychain key', async ($, on) => {
  const local = { TYPESAFE_BASE_URL: 'http://localhost:11435/', TYPESAFE_DEFAULT_MODEL: 'winnow:e4b' }
  const world = engine(on, { deviated: 0.99 }, TURN, null, local)
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  expect(world.sent).toEqual([{ url: 'http://localhost:11435/v1/systemone', authorization: 'Bearer local', model: 'winnow:e4b' }])
  expect(world.keychain).toBe(0)
  expect(logged(world).map(hit => hit.kind)).toEqual(['deviated'])
})

test('an exported key is held back from a plain-HTTP server elsewhere', async ($, on) => {
  const remote = { TYPESAFE_BASE_URL: 'http://192.168.1.20:11435', TYPESAFE_DEFAULT_MODEL: 'laya' }
  const plain = engine(on, {}, TURN, 'exported', remote)
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  expect(plain.sent.map(sent => sent.authorization)).toEqual(['Bearer local'])
  expect(plain.keychain).toBe(0)
})

test('an exported key goes to an HTTPS server', async ($, on) => {
  const secure = { TYPESAFE_BASE_URL: 'https://decisions.example.com', TYPESAFE_DEFAULT_MODEL: 'laya' }
  const world = engine(on, {}, TURN, 'exported', secure)
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  expect(world.sent).toEqual([{ url: 'https://decisions.example.com/v1/systemone', authorization: 'Bearer exported', model: 'laya' }])
})

test('a turn that loaded no skill is not judged', async ($, on) => {
  const world = engine(on, { deviated: 0.99 })
  await $.session.start(START)
  await $.turn.complete(ENDED)
  expect(world.asked.length).toBe(0)
})

// A worker's turn, as the engine hands it to session.messages({ agentId }).
const WORKER_TURN = [
  { role: 'user', text: 'You are a lane worker: build issue 14', toolUses: [] },
  { role: 'assistant', text: 'Status: DONE', toolUses: [] },
]

type Engine = Parameters<Parameters<typeof test>[1]>[0]

// Answers the model's Skill calls as the engine does: the skill's expansion (skill.prompt) happens inside the call.
// Register it before the test's first call on $; the returned function makes one such call.
function skillTool(on: On) {
  let answer: (value: unknown) => void = () => undefined
  let entered: () => void = () => undefined
  on('tool.call', { tool: 'Skill' }, () => {
    entered()
    return new Promise(resolve => (answer = resolve)) as never
  })
  return async ($: Engine, asked: string, loads: string, agentId?: string) => {
    const inside = new Promise<void>(resolve => (entered = resolve))
    const call = $.tool.call({ tool: 'Skill', tool_use_id: `use-${asked}`, skill: asked, ...(agentId ? { agentId } : {}) } as never)
    await inside
    await $.skill.prompt({ skill: loads, text: `${loads} steps` })
    answer({ result: { success: true, commandName: loads } })
    await call
  }
}

test("a skill a subagent loads is judged against that subagent's turn, never the main loop's", async ($, on) => {
  const world = engine(on, { deviated: 0.99 })
  world.agents['agent-7'] = WORKER_TURN
  const load = skillTool(on)
  await $.session.start(START)
  await load($, 'compost:build', 'compost:build', 'agent-7')
  await $.turn.complete(ENDED)
  expect(world.asked.length).toBe(0)
  await $.turn.complete({ ...(ENDED as object), turnId: 'worker-turn', agentId: 'agent-7' } as never)
  expect(world.asked.map(a => (a.state.skill as { name: string }).name)).toEqual(['compost:build'])
  expect(String(world.asked[0].state.turn)).toContain('USER: You are a lane worker')
  expect(logged(world)).toMatchObject([{ skill: 'compost:build', kind: 'deviated', turn: 'worker-turn' }])
  await $.prompt.submit({ text: 'no, that is wrong', origin: TYPED } as never)
  expect(world.asked.length).toBe(1)
})

test('a worker that asks for a skill by its short name has the load filed under its own loop', async ($, on) => {
  const world = engine(on, { deviated: 0.99 })
  world.agents['agent-7'] = WORKER_TURN
  const load = skillTool(on)
  await $.session.start(START)
  await load($, '/build', 'compost:build', 'agent-7')
  await $.turn.complete(ENDED)
  expect(world.asked.length).toBe(0)
  await $.turn.complete({ ...(ENDED as object), turnId: 'worker-turn', agentId: 'agent-7' } as never)
  expect(logged(world)).toMatchObject([{ skill: 'compost:build', kind: 'deviated', turn: 'worker-turn' }])
})

test("a skill the main loop loads through the Skill tool gets the user's next message checked for a correction", async ($, on) => {
  const world = engine(on, { corrected: 0.88 })
  const load = skillTool(on)
  await $.session.start(START)
  await load($, 'compost:build', 'compost:build')
  await $.turn.complete(ENDED)
  await $.prompt.submit({ text: 'no, you skipped the worktree', origin: TYPED } as never)
  expect(logged(world)).toMatchObject([{ skill: 'compost:build', kind: 'corrected', turn: 'turn-1' }])
})

test('a refused Skill call leaves nothing waiting, so a later typed skill still goes to the main loop', async ($, on) => {
  const world = engine(on, { deviated: 0.99 })
  on('tool.call', { tool: 'Skill' }, () => ({ deny: 'no such skill' }) as never)
  await $.session.start(START)
  await $.tool.call({ tool: 'Skill', tool_use_id: 'use-1', skill: 'compost:verify', agentId: 'agent-7' } as never)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  expect(logged(world)).toMatchObject([{ skill: 'compost:verify', turn: 'turn-1' }])
})

test("a subagent whose transcript the session can't read is skipped", async ($, on) => {
  const world = engine(on, { deviated: 0.99 })
  world.agents['agent-7'] = 'deny'
  const load = skillTool(on)
  await $.session.start(START)
  await load($, 'compost:build', 'compost:build', 'agent-7')
  await $.turn.complete({ ...(ENDED as object), agentId: 'agent-7' } as never)
  expect(world.asked.length).toBe(0)
})

test("the user's next message is checked for a correction of the skill's work", async ($, on) => {
  const world = engine(on, { corrected: 0.88 })
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  await $.prompt.submit({ text: 'no, the gates never ran, pytest is not on PATH', origin: TYPED } as never)
  expect(world.order.slice(-2)).toEqual(['prompt entered', 'jev asked'])
  expect(world.asked[1].state.next_user_message).toBe('no, the gates never ran, pytest is not on PATH')
  expect(logged(world)).toMatchObject([
    { skill: 'compost:verify', kind: 'corrected', p: 0.88, turn: 'turn-1', prompt: 'no, the gates never ran, pytest is not on PATH' },
  ])
  await $.prompt.submit({ text: 'and another thing', origin: TYPED } as never)
  expect(world.asked.length).toBe(2)
})

test("a correction check and the next turn's judgment that overlap both keep their hits", async ($, on) => {
  const world = engine(on, { corrected: 0.9, deviated: 0.9 })
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  const before = logged(world).length
  await $.skill.prompt({ skill: 'compost:build', text: 'build steps' })
  await Promise.all([
    $.prompt.submit({ text: 'no, the gates never ran', origin: TYPED } as never),
    $.turn.complete({ ...(ENDED as object), turnId: 'turn-2' } as never),
  ])
  const added = logged(world).slice(before).map(hit => `${hit.skill}:${hit.kind}`)
  expect(added.sort()).toEqual(['compost:build:deviated', 'compost:verify:corrected'])
})

test('hits append to the session file without a toast and carry the skill version', async ($, on) => {
  const world = engine(on, { deviated: 0.9 })
  await $.session.start(START)
  for (const [turnId, text] of [['turn-1', 'steps'], ['turn-2', 'steps'], ['turn-3', 'steps, revised']]) {
    await $.skill.prompt({ skill: 'compost:build', text })
    await $.turn.complete({ ...(ENDED as object), turnId } as never)
  }
  const hits = logged(world)
  expect(hits.map(hit => hit.turn)).toEqual(['turn-1', 'turn-2', 'turn-3'])
  expect(hits[0].skill_hash).toMatch(/^[0-9a-f]{8}$/)
  expect(hits[1].skill_hash).toBe(hits[0].skill_hash)
  expect(hits[2].skill_hash).not.toBe(hits[0].skill_hash)
  expect(world.toasts).toEqual([])
})

test("/drift prints skill_drift.py's summary of the log, so it shows the hits compost:skill-drift counts open", async ($, on) => {
  const world = engine(on, {})
  world.drift = { exitCode: 0, stdout: 'compost:build  deviated×2 sessions (pattern)\n', stderr: '' }
  await $.session.start(START)
  const shown = await $.command.run({ name: 'drift', args: '' } as never)
  expect((shown as { text: string }).text).toBe('compost:build  deviated×2 sessions (pattern)')
  expect(world.ran).toHaveLength(1)
  expect(world.ran[0]).toEqual([
    'uv',
    'run',
    '--quiet',
    `${PLUGIN_ROOT}/scripts/skill_drift.py`,
    '--claude-dir',
    '/home/me/.claude',
    'summary',
  ])
})

test('/drift reports a failed or refused run of skill_drift.py instead of throwing', async ($, on) => {
  const world = engine(on, {})
  world.drift = { exitCode: 1, stdout: '', stderr: '\nskill_drift: settings.json is not valid JSON\n' }
  await $.session.start(START)
  const failed = await $.command.run({ name: 'drift', args: '' } as never)
  expect((failed as { text: string }).text).toBe(
    'skill-drift: skill_drift.py summary failed (exit 1): skill_drift: settings.json is not valid JSON',
  )
  world.drift = {
    exitCode: 1,
    stdout: '',
    stderr: 'Traceback (most recent call last):\n  File "skill_drift.py", line 9, in <module>\nKeyError: \'p\'\n\n',
  }
  const crashed = await $.command.run({ name: 'drift', args: '' } as never)
  expect((crashed as { text: string }).text).toBe("skill-drift: skill_drift.py summary failed (exit 1): KeyError: 'p'")
  world.drift = 'refused'
  const refused = await $.command.run({ name: 'drift', args: '' } as never)
  expect((refused as { text: string }).text).toStartWith('skill-drift: could not run skill_drift.py: ')
})

test("a long turn is trimmed from the middle, so Jev still reads the user's request", async ($, on) => {
  const long = [
    { role: 'user', text: 'slice spec #12 into issues', toolUses: [] },
    ...Array.from({ length: 80 }, (_, i) => ({ role: 'assistant', text: `step ${i} ${'x'.repeat(300)}`, toolUses: [] })),
  ]
  const world = engine(on, {}, long)
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:slice', text: 'steps' })
  await $.turn.complete(ENDED)
  const turn = (world.asked[0].state.turn as string)
  expect(turn.startsWith('USER: slice spec #12 into issues\n…\n')).toBe(true)
  expect(turn).toContain('step 79')
  expect(turn).not.toContain('step 0 ')
})

test("an agent's message neither counts as a correction nor uses up the pending check", async ($, on) => {
  const world = engine(on, { corrected: 0.9 })
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  await $.prompt.submit({ text: 'no, that is wrong: labels say otherwise', origin: { kind: 'peer-send-message' } } as never)
  expect(world.asked.length).toBe(1)
  await $.prompt.submit({ text: 'no, the gates never ran', origin: TYPED } as never)
  expect(world.asked.length).toBe(2)
  expect(logged(world).map(hit => hit.kind)).toEqual(['corrected'])
})

test('without a TypeSafe key nothing is asked and nothing is written', async ($, on) => {
  const world = engine(on, { deviated: 0.99, corrected: 0.99 }, TURN, null)
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  await $.turn.complete(ENDED)
  await $.prompt.submit({ text: 'no, that is wrong', origin: TYPED } as never)
  expect(world.asked).toEqual([])
  expect([...world.files.keys()]).toEqual([])
  expect(world.toasts).toEqual([])
})

test('a TypeSafe outage leaves the turn and the next prompt untouched and writes nothing', async ($, on) => {
  const world = engine(on, 'outage')
  await $.session.start(START)
  await $.skill.prompt({ skill: 'compost:verify', text: 'steps' })
  const ended = await $.turn.complete(ENDED)
  const entered = await $.prompt.submit({ text: 'no, that is wrong', origin: TYPED } as never)
  expect(world.asked.length).toBe(2)
  expect(ended).toMatchObject({ text: 'Gates pass.' })
  expect(entered).toMatchObject({ text: 'no, that is wrong' })
  expect([...world.files.keys()]).toEqual([])
  expect(world.toasts).toEqual([])
})
