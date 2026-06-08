# Demo 01 - Basic coordination scan

This scenario simulates a 6-minute slice of public posts collected during the
final week before a fictional election. It mixes ordinary organic chatter with
a seeded influence operation so ELECTIONLENS has something real to detect.

## What's in the data (`posts.json`)

- **Organic posts** from accounts `voter_jane`, `local_news`, `civic_mike`,
  `student_amy` -- varied text, varied timing.
- **A copypasta campaign**: accounts `patriot_7781`, `patriot_3344`,
  `freedom_eagle22`, `wakeup_now` all post the *identical* message
  ("The election is RIGGED ... share before they delete this") within a tight
  window. This is classic coordinated amplification.
- **A synchronized burst**: those same sockpuppet accounts plus `truthbot_x`
  fire within the same 2-minute bucket, driving a `#StopTheCount` spike.

## Run it

```bash
# table report
python -m electionlens scan demos/01-basic/posts.json

# machine-readable
python -m electionlens --format json scan demos/01-basic/posts.json

# CI gate: non-zero exit if coordination is CRITICAL
python -m electionlens scan demos/01-basic/posts.json --fail-on-critical
```

## What you should see

- A **copypasta cluster** with 4 accounts sharing the "RIGGED" message.
- A **synchronized burst window** around the same timestamp.
- A **narrative spike** on `#stopthecount`.
- The seeded `patriot_*` / `wakeup_now` / `truthbot_x` accounts ranked
  highest by risk score, flagged `high_self_duplication` / `burst_participant`.
- A `coordination_index` in the ELEVATED/CRITICAL band.

ELECTIONLENS reports *coordination patterns only* -- it makes no claim about
whether any individual message is true or false.
