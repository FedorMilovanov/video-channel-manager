# Exact historical source import

The chronology, failure analysis, and artifact manifest are committed in this branch. The historical source snapshots are deliberately imported through a separate byte-preserving local package rather than copied manually through chat or the GitHub contents API.

## Package identity

- File: `legendary-poet-operational-history-source-import.zip`
- SHA-256: `f44c7dea055d84b2df45490b739e57b09cb2f8215460a19bb44a21c6247e747c`
- Source snapshot files: 6 Markdown containers
- Historical Python/PowerShell artifacts represented: 17
- Provider-write authority: none

## Target

```text
docs/history/operational-attempts/legendary-poet-vk-clips-2026-08-03-04/sources/
```

## Required safety properties

The installer:

- requires branch `agent/operational-attempt-history`;
- validates every package file against `SHA256SUMS.txt`;
- copies Markdown containers only;
- never executes code inside them;
- never contacts VK or YouTube;
- never stages, commits, pushes, resets, or checks out Git state;
- refuses to overwrite a different existing file.

After local import, the repository agent must inspect the exact diff, verify the artifact manifest, and commit only the intended historical evidence.
