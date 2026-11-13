// ABOUTME: The Jev questions and thresholds the skill-drift mod asks; `step` is asked once per numbered step, `turn.deviated` only for a skill with none.
// ABOUTME: Everything after `export default` must stay plain JSON, because the Python eval parses it.
export default {
  "thresholds": {
    "deviated": 0.75,
    "missing_guidance": 0.5,
    "corrected": 0.55
  },
  "turn": {
    "deviated": "The agent loaded the skill in `skill.text` during the turn in `turn`. Did the agent skip, reorder, or contradict a step or rule that the skill states, in a way that matters for this turn?",
    "missing_guidance": "During `turn`, did something the skill in `skill.text` relies on fail to fit this case (a command it gives returned an outcome the skill does not say how to handle, or it prefers a method its own tools cannot check and does not say what to do instead), so the agent had to find its own way? Answer no if the agent only did what the skill or the repo's docs told it, or if its trouble came from a tool permission, a typo, or its own mistake."
  },
  "next_message": {
    "corrected": "The user's message in `next_user_message` follows the agent's turn in `turn`, where the agent used the skill in `skill.text`. Is the user correcting or pushing back on how the agent handled something that skill covers?"
  },
  "step": "The agent loaded the skill in `skill.text` during the turn in `turn`. Consider only step {n} of that skill, \"{title}\", which begins: {body} Does the turn show the agent skipping that step, or doing it against what it says, although it applied here? Answer no if the step did not apply (for example, a file it reads does not exist), if the turn shows it done, or if it is a step of judgment that leaves no tool call and nothing in the turn contradicts it."
}
