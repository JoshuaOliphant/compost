---
name: reframe
description: Gives the user the expert words for what they are building when they can't name it yet, ranked by how much each changes what gets built, each tied to their description and to a real source checked by opening it, plus words from neighboring fields that solved the same problem; then rewrites their description with them. Use when the user types /compost:reframe.
disable-model-invocation: true
---

# Reframe

An agent can only build what the request names. A user who can't name the problem ("some fields
save right away and others only on submit, and people lose edits") gets an answer to the words they
used, not to the problem. Reframe hands them the field's vocabulary first, so the request, and the
spec after it, says what they mean. `compost:deeper-ask` deepens a request that is already aimed;
reframe aims it.

Start from the user's own description and their files and code, not from a summary of them.

## Steps

1. **Name the problem.** When the description could be more than one problem, list the two or
   three it could be, each with the one term that names it and the sign that tells it apart from
   the others ("if edits are lost only across tabs, it's a concurrency problem, not a form-state
   one"). Pick the likeliest and say why, then teach the words for that one.

2. **Give 8 to 12 terms,** ranked by how much each would change what gets built. For each:
   - the word, and its meaning in one plain sentence;
   - the part of the user's description it names;
   - one real project, paper, or system that uses it that way, with a link;
   - what it lets them ask an agent for.

   When the repo has a `CONTEXT.md` glossary (follow `CONTEXT-MAP.md` when there are several) and
   it already names a concept, use the glossary's word and give the expert term beside it.

3. **Borrow from two or three neighboring fields** that solved the same shape of problem under
   other names. For each: what carries over, where the analogy breaks, and which of its terms come
   back to this problem.

4. **Name what they didn't mention** but should care about, given the terms above.

5. **Rewrite their description** with the new words. Keep their goal; change only the words that
   were vague.

Open every link and confirm it uses the term the way you say. Cut any citation you can't confirm.
No padding: a term that would not change what gets built does not make the list.

Reframe writes nothing to the repo. A term the user adopts as their domain's own reaches
`CONTEXT.md` through `compost:spec`, which owns the glossary.

## Next moves

- `compost:deeper-ask` on the rewritten description, to make it deeper before work starts.
- `compost:spec` when the rewritten description is a feature to build.
