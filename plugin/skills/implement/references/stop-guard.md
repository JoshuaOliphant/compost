# The stop guard

Step 9's list of allowed stops is the whole list. This is how compost's Stop hook enforces it.

compost's Stop hook holds you to that list during an implement run: when your last message waits
on the user for anything else, Jev flags it and the hook sends you back to post a ruling and
continue. The run ends when `compost:finish` loads, or `compost:pause` once the user has sent a
message during the run; a pause you start on your own leaves the guard on, so stop only for the
list (resuming loads implement again, which starts a new run). A turn answering a message the
user typed may wait on them. When `compost:finish` loads mid-run (the user asked for the PR
early), load `compost:implement` again before you go on, or the rest of the run is unguarded. The
hook sends a stop back once and lets the next one through, so it is a nudge, not a gate: keeping
to the list is still on you.
