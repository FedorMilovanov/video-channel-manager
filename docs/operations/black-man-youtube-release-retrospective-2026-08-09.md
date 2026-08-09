# «Чёрный человек» YouTube release retrospective — 2026-08-09

Status: immutable operational retrospective and defect evidence. This document does **not** authorize any provider mutation or re-execution. It records what happened during the one-off release of the existing Black Man album target and turns the observed failures into reusable repository requirements.

## 1. Scope and evidence level

Project identity:

- `project_key`: `legendary-poet`
- YouTube OAuth alias: `legendary-poet`
- channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- released video ID: `x-puy27S2qs`
- uploaded media SHA-256: `sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0`

Evidence used for this retrospective:

1. merged repository history through `main@69682b09f3ee1613f83c552278fa85350babab12`;
2. Issue #154 checkpoints and durable repository contracts;
3. operator console output from the exact local YouTube reads/writes performed during the release session;
4. YouTube Studio screenshots supplied by the operator for fields that the Data API did not round-trip reliably;
5. exact local result paths printed by the successful guarded steps.

Provider writes described below are historical facts from this release. They are **not** standing authorization for another write.

## 2. Final observed provider state

The release session ended with the following verified remote state:

- video ID: `x-puy27S2qs`;
- title: `Сергей Есенин ⚡ Аудиоальбом «ЧЁРНЫЙ ЧЕЛОВЕК» ⚡ 7 Версий Стихотворения`;
- visibility: `public`;
- processing: `succeeded`;
- custom thumbnail: present;
- `selfDeclaredMadeForKids=false`;
- YouTube Studio `AI use`: `Yes`;
- playlist `Сергей Есенин` (`PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q`): membership present;
- playlist `Поющие Поэты` (`PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8`): membership inserted and verified;
- created top-level comment thread: `UgwqMEOx27WrGwhO7Bt4AaABAg`;
- pin state: not API-verifiable and not claimed here.

Final thumbnail input:

- operator artifact: `black-man-youtube-thumbnail-1920x1080.jpg`;
- exact SHA-256: `sha256:1d10f48a6a3eb38e9e155e4771b4d58f504c41d8e3d5edad6283af44202ccdf8`;
- requested dimensions: `1920×1080`, 16:9.

Final successful local evidence path printed by the operator:

```text
C:\Users\Fedor\Projects\video-channel-manager\operator-output\black-man-youtube-release-result.json
```

The successful release output explicitly reported:

```text
BLACK MAN YOUTUBE RELEASE VERIFIED.
VIDEO ID: x-puy27S2qs
PLAYLIST: Сергей Есенин => already_present
PLAYLIST: Поющие Поэты => inserted_and_verified
PRIVACY: public
CUSTOM THUMBNAIL: True
MADE FOR KIDS: False
COMMENT: created
COMMENT THREAD ID: UgwqMEOx27WrGwhO7Bt4AaABAg
```

## 3. Important completion split

This release proves a **provider rollout** of the historical album media. It does not prove the current artifact-level contract of Issue #154.

The uploaded MP4 SHA `e5450342...` predates the quality-master provenance fix merged in #213. Current `main` correctly treats that MP4 as historical evidence rather than current-policy artifact completion. Therefore the exact states are:

- repository implementation: current local pipeline hardening exists on `main`;
- provider rollout for historical media `e5450342...`: **verified public**;
- Issue #154 current-policy artifact completion: **not proven / remains open** until the exact accepted seven-master bytes are available to the executing environment and the current pipeline regenerates timing → render → verify → package → description evidence.

Future agents must not “solve” this discrepancy by reuploading the video. The live target is now an existing verified remote object and must be reconciled explicitly.

## 4. Chronology of the release and what failed

### 4.1 Historical uploader executed from a superseded branch

The initial private upload was dispatched from the historical PR #171 implementation in a detached worktree rather than from current `main`.

Observed worktree/head during the release:

```text
C:\Users\Fedor\Projects\video-channel-manager-black-man-upload
head d9a3a5a839b0c5266f486da51c817e62b1d4655b
```

This later became explicitly superseded by #215. Current branch-lifecycle policy now forbids executing closed, unmerged, superseded or retired branches.

**Lesson:** useful semantics discovered in a historical branch must be reimplemented on current `main`; the historical executable itself must never become the operational path again.

### 4.2 Tag readback was compared in the wrong semantic domain

The upload completed and returned video ID `x-puy27S2qs`, but the old verifier stopped with:

```text
Uploaded video readback mismatch: snippet.tags
```

Read-only diagnosis showed:

```text
ORDER EXACT: False
SAME SET: True
MISSING: []
EXTRA: []
```

YouTube returned the exact same tag values in another order. The verifier incorrectly treated tags as an ordered list.

**Required invariant:** tags are semantically unordered for this postcondition. Compare multiplicity-preserving counters, not list order. Reordering by the provider is not a content mismatch.

### 4.3 Correct response to ambiguous post-upload state

Because the verifier failed **after** remote upload, the durable state correctly represented a possible provider effect rather than inviting a second upload. Re-running `videos.insert` could have created a duplicate.

The safe recovery was:

1. stop all write retries;
2. read the journal and known video ID;
3. perform read-only `videos.list` reconciliation;
4. verify the existing private target instead of creating another upload.

This was a successful application of the repository’s no-blind-replay rule and must be preserved in any future executor.

### 4.4 `containsSyntheticMedia` did not round-trip through `videos.list`

The upload intent required:

```text
status.containsSyntheticMedia = true
```

Readback returned the other expected status fields but omitted this property (`actual=None`). A separate `videos.update(part=status)` reasserted `containsSyntheticMedia=true` and returned HTTP 200, but the subsequent `videos.list` still omitted the property.

The operator then inspected YouTube Studio and supplied screenshots showing:

- `AI use`: `Yes`;
- audience: `No, it's not made for kids`.

**Required invariant:** distinguish `false` from `unobserved`. A missing provider field is not automatically a semantic mismatch. For fields with known incomplete API observability, define a field-specific proof policy and preserve UI evidence when API readback cannot establish the value.

Do not weaken all status verification because one field is omitted. `privacyStatus`, `license`, `embeddable`, audience and other observable fields retain exact checks.

### 4.5 Description handoff failed because chat examples looked executable

Several operator failures were not PowerShell defects. The assistant placed a real command next to a second fenced block containing illustrative output such as:

```text
YOUTUBE DESCRIPTION PLAN READY — NO PROVIDER WRITE.
Channel: ...
Video: ...
Before SHA: ...
```

The operator used normal `Ctrl+C → Ctrl+V` and PowerShell attempted to execute those example lines as commands.

A second rendering defect inserted literal chat escapes such as `\_` and `\:` into executable text. Raw description copy was also pasted into the shell in one failed attempt, causing labels/URLs/content to be parsed as commands.

The process became reliable only after:

- one executable block per handoff;
- no adjacent pseudo-output block;
- description text stored in a repository file;
- PowerShell passing only exact paths/IDs;
- immutable plan + exact before/after SHA;
- post-write readback.

Final description plan evidence from that session:

```text
Before SHA: sha256:8889104d5273006b5f26aea28c9e1e8943d09a1c7a93d11deea5a93e6d7e7551
After SHA:  sha256:6290100db4a6c00c62287260758ffc050690807d06259818ad4a6ba18f0da308
Plan SHA:   sha256:bb9a6e4147d5dadcce9b9bbfe2c1c2cab75d92eaf523eb1b0be53580ad0a49a4
```

The execution reported that only `snippet.description` changed and that the result was verified.

**Important drift note:** that live description was applied through the now-superseded #197-era workflow. Current `main` later rebuilt the canonical source-first description flow in #214. The live description must therefore not be assumed to equal a future current-policy rendered description merely because both were called final at different times.

### 4.6 Image-generation boundary was repeatedly violated during artwork iteration

During thumbnail development the operator repeatedly requested deterministic/non-generative composition so that the original face/mirror pixels would not be redrawn. Image generation was nevertheless invoked multiple times before the request later changed to explicitly request generated right-side typography variants.

The final desired workflow became clear:

- generation may be used only when explicitly requested for the generated design component;
- the original portrait/mirror source is preserved as source pixels when the user requests “без генерации”;
- final assembly is deterministic compositing/cropping/resampling only where declared;
- generated typography and original photography are separate assets until final composition.

This is a tool-selection/handoff defect worth preserving as operator guidance even though it is not a YouTube API defect.

### 4.7 Thumbnail/playlist wrapper became a second provider client

The first finalization helper embedded direct `googleapis.com` HTTP calls in a generated PowerShell/Python file. This violated the current repository rule that PowerShell must orchestrate one repository-owned implementation rather than become a second provider client.

Functionally, the helper:

1. set the custom thumbnail successfully;
2. inserted the video into playlist `Сергей Есенин` successfully;
3. immediately queried playlist membership;
4. received an empty readback and stopped.

The operator did **not** rerun the mutation blindly. A read-only reconciliation then proved:

```text
CUSTOM THUMBNAIL: present
PLAYLIST Сергей Есенин: PRESENT True
PLAYLIST Поющие Поэты: PRESENT False
```

Thus the POST had succeeded and the immediate list result had not yet converged.

**Required invariant:** an accepted `playlistItems.insert` plus an empty immediate readback is `may_exist`, never `confirmed_absent`. Preserve the returned playlist-item ID as durable effect evidence, poll with bounded convergence, and if still unresolved stop for later read-only reconciliation.

A stronger verification path scans the complete target playlist with pagination and matches `contentDetails.videoId` / `snippet.resourceId.videoId`, rather than treating one immediate filtered read as authoritative absence.

### 4.8 Final release was functionally successful but architecturally ad hoc

A second generated release helper then:

- full-scanned both playlists;
- preserved already-present `Сергей Есенин` membership;
- inserted and verified missing `Поющие Поэты` membership;
- changed visibility from private to public;
- reasserted `containsSyntheticMedia=true` while preserving other editable status fields;
- created one top-level comment;
- verified final public/custom-thumbnail/audience state.

The operation succeeded, but the helper again contained its own direct YouTube HTTP implementation. This must not become the reusable standard.

**Required architectural correction:** future provider execution belongs in reviewed current-main repository modules with durable child-operation state, idempotent/resumable semantics and provider-free regression tests. Operator PowerShell should only invoke those entrypoints.

## 5. What worked well and should be retained

The release also demonstrated several controls that prevented larger failures:

- exact video/channel identity was carried throughout the flow;
- media SHA-256 was frozen before upload;
- upload started private;
- no blind second upload was created after the tag-verifier failure;
- description mutation used exact before/after state and readback;
- custom thumbnail was checked separately from video upload;
- playlist membership was treated as a separate child operation;
- an ambiguous playlist postcondition was reconciled read-only before another insert;
- visibility was changed only after thumbnail/playlist state was ready;
- final public state, custom thumbnail and audience were read back;
- a machine-readable final result path was produced;
- the final provider rollout did not falsely close the newer artifact-provenance gate.

## 6. Repository gaps exposed by the release

### P0 — live remote target is not represented in current stable upload state

Current main’s upload planner is intentionally provider-inert and uses a stable project/channel/media key. It must not later allow the known public target `x-puy27S2qs` / media `e5450342...` to be forgotten simply because the historical provider write happened outside the v2 journal namespace.

Before any future `videos.insert` implementation is considered safe, it needs a supported **adopt/reconcile-existing-target** path that binds a known remote video ID to the stable upload identity and makes that identity permanently collision-blocking unless a separately reviewed replacement policy proves otherwise.

### P0 — no supported current-main release executor

Current `main` intentionally has no YouTube upload/release execute command. The one-off release proved useful child-operation semantics, but those semantics currently live only in operator history and generated scripts.

A future reusable executor must be a separately reviewed current-main feature. It should not revive #171 or #197.

### P0 — provider semantics need explicit normalization

Reusable pure semantics should cover at minimum:

- tags: multiplicity-preserving order-insensitive equality;
- optional provider field readback: `expected / false / unobserved` must be distinct states;
- accepted mutation with missing immediate readback: `may_exist`;
- playlist verification: full pagination / exact video-ID match;
- no parent replay after a child failure.

### P1 — Windows/chat handoff contract is still underspecified

The repository already requires self-contained PowerShell, but the exact observed failure class should be explicit:

- assume the operator copies the entire shown command block with ordinary Ctrl+C/Ctrl+V;
- one executable block only;
- do not place example console output in a second adjacent code block;
- do not paste long content bodies into shells; pass exact files;
- literal `\_` or `\:` introduced by chat formatting is a handoff defect, not something the operator should repair manually;
- if chat rendering cannot preserve a command, deliver a `.ps1` artifact instead.

### P1 — retired YouTube branches should be explicit in retirement state

The retirement registry should explicitly name:

- PR #171 / historical Black Man provider uploader;
- PR #197 / historical YouTube description apply branch;

Both contain useful evidence but are non-authoritative after #215/#214 and branch-lifecycle hardening.

### P1 — live description/current canonical description drift is unresolved

The provider-visible description was successfully changed during this session, but current `main` later made media-derived chapters and current provenance stricter. A future metadata refinement should first perform read-only compare against a current-policy rendered description for the **same exact media bytes**. Do not silently overwrite the public description just to make repository text look current.

### P2 — comment pin remains a UI-only residual

The final top-level comment exists. No provider API postcondition for pinning was established. Do not write “pinned” into durable state until an operator explicitly verifies that UI state.

## 7. Required design for the next reusable YouTube executor

A new implementation should model each child operation independently:

```text
existing-target reconciliation
→ upload only if exact stable identity proves absent
→ processing/private readback
→ description/metadata child operations
→ thumbnail
→ playlist memberships
→ visibility/publication
→ top-level comment
→ optional manual-only pin evidence
```

Each child needs:

- exact identity and immutable payload digest;
- durable intent before dispatch;
- `not_dispatched / may_exist / verified / confirmed_absent` effect state;
- provider-returned object ID where available;
- bounded readback/convergence policy;
- zero blind retries after `may_exist`;
- a result that survives process failure;
- exact resume from the first unverified child.

PowerShell may select paths and call the repository entrypoint. It must not reimplement OAuth, HTTP endpoints, pagination, retry semantics or provider verification.

## 8. What future agents must never do

- Do not upload another copy of the album because current `main` has no v2 provider journal for the historical release.
- Do not run PR #171 or PR #197 branches/worktrees.
- Do not call the old MP4 current-policy artifact proof.
- Do not treat tag order as semantic order.
- Do not convert missing `containsSyntheticMedia` readback to `false`.
- Do not infer failed playlist insertion from one empty immediate read.
- Do not replay thumbnail/playlist/publication parent operations after a later child fails.
- Do not embed a new direct YouTube client in a one-off `.ps1`/temporary Python helper.
- Do not put raw YouTube description text or pseudo-console output into an executable PowerShell handoff.
- Do not claim the comment is pinned without separate UI evidence.

## 9. Durable next actions

1. Record the verified live target in current operational state without converting this historical provider success into standing authorization.
2. Add explicit retirement entries for #171 and #197.
3. Harden the Windows/chat handoff contract against the exact Ctrl+C/Ctrl+V failures observed here.
4. Add provider-semantic regression helpers/tests for unordered tags, unobserved status fields and accepted-but-not-yet-readable child effects.
5. Open a new focused implementation issue for a current-main guarded YouTube release executor / existing-target adoption path.
6. Comment on Issue #154 that provider rollout is verified public while current-policy artifact completion remains open.
7. After the active GitHub-governance writer is finished, update `docs/operations/current-state.md` with the live public target and retain the artifact/provider completion split.

No item above authorizes a new YouTube mutation.