# VK reviewed correction P1 — «Шёпот, робкое дыханье…»

## Scope

Correction-only dry-run for exactly two VK videos:

```text
-235216998_456239127
-235216998_456239143
```

Titles, the other 109 descriptions, 17 collection titles, 294 membership identity pairs, the 111-video inventory, links, hashtags, poem text, and music framing are frozen.

## Editorial findings

### Confirmed

- «Шёпот, робкое дыханье…» is dated 1850 in the academic complete edition.
- The poem contains no verbs.
- Chernyshevsky's letter specifically mentions the piece without verbs and uses the horse comparison.
- Fet knew Maria Lazich during his military service in the Kherson province.
- The separation was followed by Lazich's death from burns; B. Ya. Bukhstab presents disguised suicide only as a possibility.
- A retrospective group of poems is connected with Lazich's memory.
- Fet's secretary E. V. Kudryavtseva recorded the steel letter knife, the attempt to reach other knives, her intervention, and Fet's death shortly afterwards.

### Unsupported or overstated in the current VK descriptions

- a documented authorial dedication of «Шёпот…» to Maria Lazich;
- the claim that Fet wrote all lifelong love poetry only to Lazich;
- the claim that an ultimate Lazich dedication is securely dated 1892;
- the claim that Lazich was the only heroine of all Fet's love lyrics;
- an omniscient reconstruction of Lazich's last hours and exact last words without attribution;
- a medically established heart attack as the proven cause after Fet's suicide attempt;
- the caricature «днём — жёсткий помещик, ночью — гений нежности» as biography.

Bukhstab distinguishes a principal retrospective Lazich cycle from another late love cycle of 1882–1892 addressed to a living beloved or beloveds whose identity is not established.

## Reviewed replacements

The decision set is:

```text
content/policies/vk-reviewed-corrections-p1-fet-whisper-20260727.json
```

It contains five exact replacements:

1. rebuild the short description's first three paragraphs;
2. qualify the 1850/Lazich context as possible biographical background rather than a documented dedication;
3. attribute the Lazich death account and label disguised suicide as a hypothesis;
4. correct the late love-cycle and Fet-death claims using Bukhstab and Kudryavtseva;
5. remove the accidental truncated footer line `🎧 The Leg`.

Every replacement must occur exactly once. The two current descriptions are guarded by exact canonical VK text hashes.

## Sources

- Russian Virtual Library, B. Ya. Bukhstab, *A. A. Fet*.
- Russian Virtual Library, *Fet. Complete Collection of Poems*, 1959.
- *Voprosy Literatury*, O. Panchenko, *Movement of the Poetic Word*.
- Fundamental Electronic Library, *On the Death of A. A. Fet*, including E. V. Kudryavtseva's eyewitness memoir.
- Fundamental Electronic Library, *Concise Literary Encyclopedia: Fet*.
- The Legendary Poet project charter and editorial judgment policy.
- The owner's Research knowledge base.

## Source chain

The source snapshot must come from the independently verified final snapshot of the preceding Esenin correction apply wave. The wrapper first runs:

```powershell
py -3.11 -X utf8 .\scripts\verify_vk_reviewed_correction_apply_bundle.py <apply-zip>
```

Only after `status=verified_completed` does it extract `04-final-vk-snapshot.json` and build the Fet plan.

## Canonical guard-hash incident

The first dry-run attempt stopped with:

```text
Description guard mismatch for -235216998_456239127
```

The description text in the independently verified final snapshot was correct and unchanged. The policy had stored ordinary SHA-256 of UTF-8 text bytes, while the writer contract uses `text_sha256`:

```text
canonical_vk_text(text)
→ compact JSON string with ensure_ascii=false
→ SHA-256
```

Correct guards:

```text
-235216998_456239127
raw SHA-256: sha256:1b9c99ad52dc29f2df7645ae4c3dbedce20ff0c9da942e8e468709e9e35845e3
text_sha256: sha256:eb10b7f1e529c26c240dada4116d2a9666b33bb4e0e167839ad3f9762e959203

-235216998_456239143
raw SHA-256: sha256:971c88b8e2aed7273cfcf0115dd957717a0d176c8b4461dcd8259c0346b51a9b
text_sha256: sha256:76c74c96f9aaa93d952531094d42c4b7a168f901566688bd349febd8b7b0c6b9
```

All reviewed decision sets now declare:

```json
"description_guard_hash_algorithm": "video-manager.text-sha256-v1"
```

The correction builder rejects missing or unknown guard algorithms. On mismatch it reports expected canonical hash, actual canonical hash, and raw text SHA-256 so a calculation-method bug is distinguishable from real text drift.

## Honest failed-diagnostic handoff

The initial wrapper incorrectly printed a green ready message after plan construction failed and then attempted to open a missing `plan-review.html`.

The wrapper now distinguishes:

- `artifact_kind=verified dry-run` only when plan construction and live read-only preflight complete;
- `artifact_kind=failed diagnostic` on every failure.

A failed diagnostic ZIP contains source snapshot, source apply verification, decisions, source review bundle, and `00-build.txt`. It is never eligible for execute. Missing HTML is not opened, and automatic shell opening cannot replace the original error.

## Dry-run command

```powershell
pwsh -File .\scripts\Invoke-VkReviewedCorrectionFetWave.ps1
```

Expected preflight:

```text
ready: 2
already applied: 0
conflicts: 0
remote writes: 0
```

One-file handoff:

```text
data\handoffs\vk-reviewed-correction-p1-fet-dry-run-YYYYMMDD-HHMMSS.zip
```

The dry-run wrapper contains no `--execute` and cannot call VK mutation methods.
