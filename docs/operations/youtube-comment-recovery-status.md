# Recovery status meanings

- `pending`: the wave has not finished all planned attempts.
- `partial_failure`: at least one planned write failed.
- `verification_pending`: all expected write responses were recorded, but complete live confirmation is still missing.
- `completed`: every planned operation has been confirmed without requiring a repeated write.

A `completed` journal alone proves the signed wave, not full current channel coverage. Full coverage additionally requires a fresh successful audit and a coverage certificate.
