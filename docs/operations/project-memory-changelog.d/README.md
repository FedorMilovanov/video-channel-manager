# Project-memory changelog fragments

This directory extends `../project-memory-changelog.md` with append-only, source-bound entries when rewriting the large historical file would create unnecessary loss or merge risk.

Fragments are part of durable operational memory only when they:

- name the exact wave/issue/PR/merge/CI evidence;
- preserve project identities and operational ownership;
- record provider query/write/plan counts;
- avoid upgrading retained counts or transcript claims to fresh live truth;
- remain referenced by current state, machine state, tests, or the exact owning issue.

Current fragments:

- [`2026-08-05-wave-12a.md`](2026-08-05-wave-12a.md) — project-bound live issue ownership correction.
