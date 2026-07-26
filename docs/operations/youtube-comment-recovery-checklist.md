# YouTube comment recovery checklist

Use the one-command recovery wrapper with the original signed plan and original apply journal. Do not rebuild the plan and do not rerun create mode.

A successful recovery must produce all of these results:

- verify-only confirms every planned operation with zero writes;
- the original journal is marked completed;
- a fresh YouTube scan succeeds;
- the fresh audit is internally consistent;
- every public video has exactly one channel-authored top-level comment;
- the coverage certificate is written.

Keep the plan, journal, audit, and certificate together as the evidence bundle for the completed wave.
