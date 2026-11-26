# Benchmarks

Depth for performance claims in `compost:diagnose` step 6 and `compost:verify` step 7. A benchmark
produces a number; this checklist decides whether the number means what you think.

## Before you run anything

- Write the claim in one sentence: what is faster or slower, by roughly how much, on which
  workload. A claim written after the run bends to fit whatever came out.
- Name the result that would change a decision, and the noise floor you expect. Stop when the
  run-to-run spread is larger than the effect you are looking for; more runs of a noisy setup
  only measure the noise.
- Read the measurement script. Note what it times, what it counts, and what it ignores.
- Check the load with `uptime` and the core count with `nproc`. If the machine is busy, find out
  what is running. If you cannot stop it, interleave the sides so both see the same noise, and say
  so in the report.

## Seven questions

Answer each one in writing, next to the number.

1. **Why not double?** Name the limiter that stops the result from being twice as good: CPU, I/O,
   a lock, the network, a fixed cost. Show it with a profile or a measurement. A guess from reading
   the code is not a limiter.
2. **Is each side tuned?** Both sides get the same care: warm caches or cold on both, the same
   build flags, the same data, the same machine. A tuned new path against a default old one
   measures the tuning. A limiter that is a setting (a commit per row, a debug build, a missing
   index) means that side is untuned: tune it and measure again before you pick a winner, and pick
   none from a run you could not tune.
3. **Did it break limits?** Do the arithmetic: bytes per second against disk and network
   bandwidth, operations per second times the cost of one against your cores, the time saved
   against the time the changed piece took (removing a piece that takes 10% of the run makes it at
   most about 11% faster). A result past a limit measured something other than the work: a cache, a
   no-op, a bug. Then say where the result stops holding: input size, concurrency, hardware, data
   shape. A win at one size can be a loss at another.
4. **Did anything error?** Check the logs and exit codes of every run. Failed requests finish fast,
   so errors often look like a speedup.
5. **Does it reproduce?** Run each side 5 times, alternating A and B so drift hits both. Report the
   median and the range. If the ranges overlap, you have not shown a difference.
6. **Does it matter end to end?** Measure the path the user waits on, not just the piece you
   changed. A 50% win on a step that takes 1% of the request is a 0.5% win.
7. **Did it happen at all?** Prove the code you changed ran during the measurement: a counter, a
   log line, a profile frame. Skipped work, a cache hit, or a stale build all look fast.

An eval result is a number too. Ask the same of its trials: did every run do the task, and does the
gap hold across trials and models?

## Close with one verdict

End with exactly one of: faster, slower, no measurable difference, or inconclusive. Put the median,
the range, the limiter, and the answers above beside it. Call it inconclusive when you claim a
difference but cannot name the limiter, or when a side ran untuned; say what would settle it.
