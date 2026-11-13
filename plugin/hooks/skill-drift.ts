// ABOUTME: Watches each skill the model loads and asks the decision model (TypeSafe Jev, or one a local Ollaya serves) whether the turn deviated from it, lacked its guidance, or drew a correction.
// ABOUTME: Hits go quietly to ~/.claude/skill-drift/<date>-<session>.jsonl; /drift prints scripts/skill_drift.py's summary of the open ones.
import type { EngineInterface, Register, SessionMessage } from 'claude-code'

import judgments from './skill-drift-judgments.ts'

// The TypeSafe SDK's variables, read the way scripts/jevtools/core.py reads them, so Ollaya's setup covers the hook too.
// tests/test_skill_drift_mod.py holds these constants equal to core.py's.
const TYPESAFE_URL = 'https://api.typesafe.ai'
const DEFAULT_MODEL = 'jev-latest'
const LOCAL_KEY = 'local'
const TYPED_BY_A_PERSON = new Set(['composer', 'bridge'])
// Room for compost's longest skill whole: Jev can't judge a step it never read. tests/test_skill_drift_mod.py holds this.
const SKILL_CHARS = 16000
const TURN_CHARS = 12000
const EVIDENCE_CHARS = 4000
const { thresholds: THRESHOLDS, turn: TURN_QUESTIONS, next_message: NEXT_MESSAGE_QUESTIONS, step: STEP_QUESTION } = judgments
const STEP_BODY_CHARS = 400

export type DriftKind = keyof typeof TURN_QUESTIONS | 'corrected'
export type Hit = {
  skill: string
  kind: DriftKind
  p: number
  at: number
  session: string
  turn: string
  skill_hash: string
  prompt: string
  evidence: string
}
type Watched = { skill: string; text: string; trace: string; prompt: string; turn: string }
type Server = { url: string; model: string; key: string }

// Mirrors carries_key in scripts/jevtools/core.py: an exported key goes only over HTTPS or to this machine.
function carriesKey(url: string): boolean {
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return false
  }
  if (parsed.protocol === 'https:') return true
  const host = parsed.hostname.replace(/^\[|\]$/g, '')
  return host === 'localhost' || host === '::1' || /^127\.\d+\.\d+\.\d+$/.test(host)
}

async function server($: EngineInterface): Promise<Server | undefined> {
  const [base, chosen, fromEnv] = await Promise.all([
    $.env.get('TYPESAFE_BASE_URL'),
    $.env.get('TYPESAFE_DEFAULT_MODEL'),
    $.env.get('TYPESAFE_API_KEY'),
  ])
  const url = (base || TYPESAFE_URL).replace(/\/+$/, '')
  const model = chosen || DEFAULT_MODEL
  // Another server never gets the Keychain's TypeSafe key, and an exported one only where carriesKey allows.
  if (url !== TYPESAFE_URL) return { url, model, key: fromEnv && carriesKey(url) ? fromEnv : LOCAL_KEY }
  if (fromEnv) return { url, model, key: fromEnv }
  const keychain = await $.process.run(['security', 'find-generic-password', '-s', 'typesafe', '-w'])
  const key = keychain.exitCode === 0 ? keychain.stdout.trim() : ''
  return key ? { url, model, key } : undefined
}

async function nouls($: EngineInterface, target: Server, state: unknown, questions: Record<string, string>) {
  const response = await $.http.fetch(`${target.url}/v1/systemone`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${target.key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: target.model,
      state,
      questions: Object.fromEntries(Object.entries(questions).map(([id, text]) => [id, { type: 'noul', instructions: text }])),
    }),
  })
  if (!response.ok) throw new Error(`Decision model ${response.status}: ${response.text.slice(0, 200)}`)
  const answers = JSON.parse(response.text).answers as Record<string, { noul: number }>
  return Object.fromEntries(Object.entries(answers).map(([id, answer]) => [id, answer.noul]))
}

export function skillHash(text: string): string {
  let hash = 0x811c9dc5
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash.toString(16).padStart(8, '0')
}

function isTypedPrompt(message: SessionMessage): boolean {
  return message.role === 'user' && message.text.trim() !== '' && !message.toolResults?.length
}

export function turnTrace(messages: SessionMessage[]): { prompt: string; trace: string } {
  let start = messages.length - 1
  while (start > 0 && !isTypedPrompt(messages[start])) start -= 1
  const lines: string[] = []
  for (const message of messages.slice(start)) {
    if (message.role === 'user' && isTypedPrompt(message)) lines.push(`USER: ${message.text}`)
    if (message.role === 'assistant') {
      if (message.text.trim()) lines.push(`AGENT: ${message.text}`)
      for (const use of message.toolUses) {
        const outcome = use.isError ? `ERROR ${use.text ?? ''}` : (use.text ?? '')
        lines.push(`TOOL ${use.tool} ${JSON.stringify(use.input).slice(0, 300)} -> ${outcome.slice(0, 400)}`)
      }
    }
  }
  const [opening = '', ...rest] = lines
  const body = rest.join('\n')
  const trace = body.length > TURN_CHARS ? `${opening}\n…\n${body.slice(-TURN_CHARS)}` : [opening, body].join('\n')
  return { prompt: messages[start]?.text ?? '', trace }
}

export type Step = { n: string; title: string; body: string }

// A skill's numbered steps (`3. **Survey the suite.** ...`), each with the start of its text.
export function skillSteps(text: string): Step[] {
  return text
    .split(/^(?=\d+\. \*\*)/m)
    .map(block => block.match(/^(\d+)\. \*\*(.+?)\*\*([\s\S]*)/))
    .filter(match => match !== null)
    .map(([, n, title, rest]) => ({ n, title: title.replace(/\.$/, ''), body: rest.split(/\s+/).join(' ').trim().slice(0, STEP_BODY_CHARS) }))
}

// One whole-skill "did it deviate" question scores 0.8+ on a long skill however well the turn followed it, so a
// skill with numbered steps gets one question per step, and the turn deviated by its likeliest skipped step.
// Questions are keyed by position, not by the step's own number: a skill with two lists (pause) numbers from 1 twice.
function turnQuestions(text: string): Record<string, string> {
  const steps = skillSteps(text)
  if (steps.length === 0) return TURN_QUESTIONS
  const asked: Record<string, string> = { missing_guidance: TURN_QUESTIONS.missing_guidance }
  steps.forEach((step, index) => {
    asked[`step ${index + 1}`] = STEP_QUESTION.replace('{n}', step.n).replace('{title}', step.title).replace('{body}', step.body)
  })
  return asked
}

// The step answers folded into one `deviated` score, named after the step that set it.
function turnScores(text: string, answers: Record<string, number>): { kind: DriftKind; p: number; why?: string }[] {
  const steps = skillSteps(text)
  if (steps.length === 0) return Object.entries(answers).map(([kind, p]) => ({ kind: kind as DriftKind, p }))
  const scored = steps.map((step, index) => ({ step, p: answers[`step ${index + 1}`] ?? 0 }))
  const { step: likeliest, p } = scored.reduce((best, next) => (next.p > best.p ? next : best))
  return [
    { kind: 'missing_guidance', p: answers.missing_guidance ?? 0 },
    { kind: 'deviated', p, why: `Likeliest skipped step: ${likeliest.n}. ${likeliest.title} (p=${p.toFixed(2)})` },
  ]
}

function evidence(trace: string): string {
  return trace.length > EVIDENCE_CHARS ? `${trace.slice(0, EVIDENCE_CHARS / 2)}\n…\n${trace.slice(-EVIDENCE_CHARS / 2)}` : trace
}

async function claudeDir($: EngineInterface): Promise<string> {
  return `${await $.env.get('HOME')}/.claude`
}

async function logDir($: EngineInterface): Promise<string> {
  return `${await claudeDir($)}/skill-drift`
}

// The engine's fs has no append, so a write is read-then-rewrite. A turn's judgment and the next prompt's
// correction check can overlap on the same session file; one queue per mod keeps either from dropping the other's hits.
let writes: Promise<void> = Promise.resolve()

function record($: EngineInterface, found: Hit[]): Promise<void> {
  if (found.length === 0) return writes
  const write = writes.then(async () => {
    const day = new Date(found[0].at).toISOString().slice(0, 10)
    const path = `${await logDir($)}/${day}-${found[0].session}.jsonl`
    const before = (await $.fs.exists(path)) ? String(await $.fs.read(path)) : ''
    await $.fs.write(path, before + found.map(hit => JSON.stringify(hit) + '\n').join(''))
  })
  writes = write.catch(() => undefined)
  return write
}

// The mod only writes hits. Which ones are open (unreviewed, on an active skill's latest version) is
// scripts/skill_drift.py's to say, for /drift as for compost:skill-drift, so /drift asks it.
async function driftSummary($: EngineInterface): Promise<string> {
  const script = `${$.plugin.root}/scripts/skill_drift.py`
  const argv = ['uv', 'run', '--quiet', script, '--claude-dir', await claudeDir($), 'summary']
  try {
    const ran = await $.process.run(argv)
    if (ran.exitCode === 0) return ran.stdout.trimEnd()
    // The last line: a Python traceback ends with the exception, and skill_drift.py's own errors are one line.
    const why = (ran.stderr || ran.stdout).split('\n').findLast(line => line.trim()) ?? 'no output'
    return `skill-drift: skill_drift.py summary failed (exit ${ran.exitCode}): ${why}`
  } catch (error) {
    return `skill-drift: could not run skill_drift.py: ${(error as Error).message}`
  }
}

export const DRIFT_COMMAND = { name: 'drift', description: 'List skill drift the mod has recorded, by skill' }

// skill.prompt names the skill but not the loop that loaded it. A model loads one through the Skill tool, whose
// call carries its loop's agentId, so each in-flight Skill call waits here for the load it causes. A load no call
// waits for (a typed /skill, or a skill an agent definition preloads) belongs to the main loop. skill.prompt carries no
// tool_use_id, so a load takes the first waiting call for its skill: two loops loading one skill at once may swap
// entries, which is harmless when both loads land, and misfiles one only if a lower hook refuses the other call.
const MAIN_LOOP = ''
type SkillCall = { asked: string; loop: string }

function callFor(calls: SkillCall[], skill: string): SkillCall | undefined {
  return calls.find(call => call.asked === skill || skill.endsWith(`:${call.asked}`))
}

export const register: Register = on => {
  const loaded = new Map<string, Map<string, string>>()
  const calls: SkillCall[] = []
  let pending: Watched[] = []

  on('tool.call', { tool: 'Skill' }, async ($, e, next) => {
    const call = { asked: String((e as { skill?: unknown }).skill ?? '').replace(/^\//, ''), loop: e.agentId ?? MAIN_LOOP }
    calls.push(call)
    try {
      return await next(e)
    } finally {
      // A call whose load never came (refused, or no such skill) leaves; one that loaded was taken by skill.prompt.
      if (calls.includes(call)) calls.splice(calls.indexOf(call), 1)
    }
  })

  on('skill.prompt', async ($, e, next) => {
    const result = await next(e)
    const call = callFor(calls, e.skill)
    if (call) calls.splice(calls.indexOf(call), 1)
    const loop = call?.loop ?? MAIN_LOOP
    if (!loaded.has(loop)) loaded.set(loop, new Map())
    loaded.get(loop)?.set(e.skill, result.text.slice(0, SKILL_CHARS))
    return result
  })

  // Each loop's turn is judged against the skills that loop loaded, so a worker's compost:build is held to the
  // worker's own turn and never to the coordinator's. Only the main loop has a person whose next message can correct it.
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const loop = e.agentId ?? MAIN_LOOP
    const skills = loaded.get(loop)
    if (e.isAborted || !skills?.size) return result
    loaded.delete(loop)
    const target = await server($)
    if (!target) return result

    const messages = e.agentId ? await $.session.messages({ agentId: e.agentId }) : await $.session.messages()
    if ('deny' in messages) return result
    const { prompt, trace } = turnTrace(messages)
    const watched = [...skills.entries()].map(([skill, text]) => ({ skill, text, trace, prompt, turn: e.turnId }))
    if (loop === MAIN_LOOP) pending = watched

    const answered = await Promise.all(
      watched.map(w => nouls($, target, { skill: { name: w.skill, text: w.text }, turn: w.trace }, turnQuestions(w.text))),
    )
    const [session, at] = await Promise.all([$.session.id(), $.clock.now()])
    await record(
      $,
      watched.flatMap((w, i) =>
        turnScores(w.text, answered[i])
          .filter(({ kind, p }) => p >= THRESHOLDS[kind as keyof typeof THRESHOLDS])
          .map(({ kind, p, why }) => hitOf(w, kind, p, session, at, w.prompt, why)),
      ),
    )
    return result
  })

  on('prompt.submit', async ($, e, next) => {
    if (!TYPED_BY_A_PERSON.has(e.origin?.kind)) return next(e)
    const watched = pending
    pending = []
    const result = await next(e)
    if (watched.length === 0 || e.text.trim().startsWith('/')) return result
    const target = await server($)
    if (!target) return result

    const answered = await Promise.all(
      watched.map(w =>
        nouls($, target, { skill: { name: w.skill, text: w.text }, turn: w.trace, next_user_message: e.text }, NEXT_MESSAGE_QUESTIONS),
      ),
    )
    const [session, at] = await Promise.all([$.session.id(), $.clock.now()])
    await record(
      $,
      watched
        .map((w, i) => hitOf(w, 'corrected', answered[i].corrected, session, at, e.text))
        .filter(hit => hit.p >= THRESHOLDS.corrected),
    )
    return result
  })

  on('command.run', { name: 'drift' }, async $ => ({ text: await driftSummary($) }))
}

function hitOf(w: Watched, kind: DriftKind, p: number, session: string, at: number, prompt: string, why?: string): Hit {
  const shown = why ? `${why}\n${evidence(w.trace)}` : evidence(w.trace)
  return { skill: w.skill, kind, p, at, session, turn: w.turn, skill_hash: skillHash(w.text), prompt, evidence: shown }
}
