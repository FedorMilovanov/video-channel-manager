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

Every replacement must occur exactly once. The two current descriptions are guarded by exact SHA-256 values.

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
