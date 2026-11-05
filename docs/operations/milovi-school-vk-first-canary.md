# MILOVI CAKE — one-shot postponed School wall canary (#792)

## Exact target and authority

- Project: `milovi-cake`; VK community `68859909`, wall owner `-68859909`
- Source: `tech-mirror-glaze`, `https://french.milovicake.ru/articles/tech-mirror-glaze/`
- Frozen editorial preview: `content/editorial/milovi-cake/vk-school-first-canary-preview-20261105.json` from merged PR #808
- Reviewed message SHA-256: `9cc8b4a2c18f062da24533efe8a6b8da97ce3e840ccf924f71d05bb9463147b0`
- One proposed postponed slot: **2026-11-07 12:00 Moscow** (`1794042000`)
- Exact VK idempotency GUID: `vcm-milovi-school-b0ab367a74ae756f99be`
- No video, photo, attachment or unrelated account may be added
- This writer never touches the 12 protected native clips from #323

## Evidence and platform constraints

The owner's official app service key can scan all 162 public wall posts and found **zero**
of the ten exact School URLs twice on 2026-11-05. The Milovi public Articles page
showed **no articles** when viewed through the authorized browser. The owner
personally stated that no postponed posts were queued; this is a **human
administrative observation, not a machine-verified queue snapshot**.

VK `wall.get` with the separately validated community token actually returns
provider error **27**, and `wall.get(filter=postponed)` with the service key
returns provider error **15**. Do not bypass either error, query the quarantined
user aliases `default` and `legendary-poet`, or claim the API read verified
postponed-slot vacancy. A **fresh authenticated admin UI check** is the
remaining authority for scheduled wall occupancy and the final postflight.

## Dry-run (safe; absolutely no provider writes)

The CLI is repository-owned under the existing `video_channel_manager vk`
command family. Invoke from a fresh clean checkout of the exact released main,
while pointing `--data-dir` to the **persistent** token store, not the
temporary worktree's ephemeral `data` directory.

```powershell
python -m video_channel_manager vk milovi-school-postponed-canary `
  --preview-path content/editorial/milovi-cake/vk-school-first-canary-preview-20261105.json `
  --editorial-path content/editorial/milovi-cake/vk-school-wave-20261105.md `
  --journal-path C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-school-vk-postponed-canary-20261105.json `
  --data-dir C:\Users\Fedor\Projects\video-channel-manager\data
```

Do not add `--apply` solely because a dry-run passed. A second, explicitly
reviewed approval must bind the exact text, time, project, community and
source. Verify latest public wall by official service API, and verify the
administrative queue and native Article state through the authorized admin UI
before running the one-time write.

## Single authorized execution (never bulk)

Only after exact user/operator approval and rechecking that the 7 November
12:00 Moscow slot is unoccupied, call the same command with `--apply`,
the exact confirmation `MILOVI-CAKE-68859909-TECH-MIRROR-GLAZE-20261107-1200MSK`,
and reviewed `--admin-queue-witness OWNER_REPORTED_EMPTY_2026-11-05`.
The latter is *a declaration of the owner's existing witness*, not proof of
a new provider readback. **It must not be used to waive the preceding fresh
admin UI check**. Keep the canonical output journal on the persistent root.

The handler acquires the canonical per-community mutex, performs a fresh
complete public wall re-read through the service key, requires live community
key permissions and exact community binding, fsyncs its unique journal in
`intent_prepared` state, then fsyncs a `dispatch_started` marker **before
exactly one `wall.post`**. It supplies `guid` and `publish_date` and
deliberately never retries an ambiguous request.

A valid positive provider `post_id` is recorded as
`vk_accepted_pending_admin_postflight`, **not** as `canary_verified`.
The operator must then open the real VK admin **Отложенные** surface and verify
the matching text, date, wall identity and exact post ID. The community
credential cannot perform that privileged read itself. If the attempt
fails, times out or produces a non-positive post ID, leave the durable journal
in place, stop and reconcile remotely; never re-run the same `guid` blindly.

No other School post can be scheduled until the exact first canary's provider
postcondition has been independently verified. This is one target and one
write, not a generic VK wall-publishing backend.
