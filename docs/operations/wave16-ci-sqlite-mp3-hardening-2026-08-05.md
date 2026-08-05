# Wave 16 — CI runtime, SQLite lifetime, and MP3 identity hardening

Date: 2026-08-05  
Issue: #137  
Scope: repository/local-only; no provider or browser activity

## Confirmed defects

### GitHub Actions runtime drift

The CI workflow pinned `actions/checkout` v4, `actions/setup-python` v5, and `actions/upload-artifact` v4. GitHub-hosted runners forced these Node 20-generation actions onto Node 24 and emitted deprecation warnings on every job.

Wave 16 pins immutable official Node 24 releases:

- `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd` — v6.0.2;
- `actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405` — v6.2.0;
- `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` — v7.0.1.

The immutable SHA remains authoritative; the version comment is human-readable evidence.

### SQLite context-manager misunderstanding

`sqlite3.Connection.__exit__` commits or rolls back a transaction but does not close the connection. Both Package A and its SQLite test fixtures relied on `with sqlite3.connect(...)`, producing delayed `ResourceWarning: unclosed database` messages under Python 3.13.

Wave 16:

- wraps production and fixture connections in `contextlib.closing`;
- commits fixture creation explicitly;
- adds a proxy regression proving production calls `close()`;
- promotes `unclosed database` ResourceWarnings to pytest errors.

This is a resource-lifetime fix only. Package A remains read-only and provider-free.

### MP3 canonical selection and identity ambiguity

The first path-sorted duplicate previously became canonical. That allowed an ambiguous filename-only candidate to suppress a later candidate with exact artist/title metadata.

The planner also treated two unsafe mappings as normal duplicates:

- one exact source ID with different file bytes;
- identical bytes claimed by different exact source IDs.

Wave 16 manifest schema 1.1 now:

- gives explicit exact metadata first canonical priority;
- uses declared-policy ready metadata second;
- uses path only as a stable tie-breaker;
- marks one-source/multiple-SHA as `source_id_sha256_conflict`;
- marks one-SHA/multiple-source as `sha256_multiple_source_ids`;
- keeps every conflict item in `requires_review`;
- gives every local candidate a unique deterministic operation ID including resolved path.

## Scale proof

The regression suite constructs 1,000 unique local MP3 candidates and proves:

- input-order independence;
- one deterministic manifest;
- 1,000 ready items;
- 1,000 unique operation IDs;
- zero review or duplicate states for the clean set;
- 40 deterministic chunks of 25 items.

This proves local planning scale only. It does not prove or authorize provider throughput, browser concurrency, upload capacity, or playlist mutation.

## First exact-head CI finding

CI `31022115047` on head `832cdfb8fd12eae5b34291a88d19367738f4752a` proved the intended runtime fixes:

- no `Node.js 20 is deprecated` text;
- no `ResourceWarning: unclosed database` text;
- strict mypy passed 147 source files;
- dependency audit found no known vulnerabilities;
- 844 tests passed and one expected xfail remained.

The run failed only because one new test line needed exact Ruff quote formatting and the revised contract omitted the historical sentence `Wave 15 implements only steps 1–4`. Both compatibility findings were corrected without changing runtime behavior or expanding the nine-file scope.

## Non-events

During Wave 16 implementation:

- provider queries: 0;
- provider writes: 0;
- write plans: 0;
- historical executor runs: 0;
- browser launches: 0;
- ID3 rewrites: 0;
- renames/transcodes: 0;
- VK Audio uploads or edits: 0;
- playlist or wall mutations: 0.

## Exit evidence

Final proof must come from one exact PR head and include:

- all six CI jobs green;
- Python 3.11/3.12/3.13 test counts and coverage;
- Ruff correctness and formatting;
- strict mypy;
- dependency audit;
- three PowerShell environments;
- no Node 20 deprecation text in job logs;
- no unclosed SQLite database warning in pytest logs.

A separate state-sync change may promote Wave 16 only after this code PR is merged.
