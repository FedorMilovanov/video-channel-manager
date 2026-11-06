# @lordchrist Shorts: fresh owner-media recovery ? 2026-11-06

Owner: #810. Read-only and provider-inert evidence; NO publication authorization.

## Current source state

- Current owner channel: YouTube UCeSJsC6go2c9pdJCuUI1BYA, exact snapshot 53c8499f-7daf-4b84-a16d-308ba9b5668e on 2026-11-05 17:43:11Z.
- Snapshot 1843 videos, 283 durations <=180s, 282 historical-surface candidates with incomplete owner geometry; 0 automatically proven Shorts.
- File search on the owner's Windows machine found 22 unique video IDs with local files whose names AND exact byte sizes match the YouTube owner fileDetails. 17 had matching duration <=2 seconds and real vertical frames, demonstrated via ffprobe.
- Another three local matches have video-duration mismatch >2 seconds and are held, despite size/name match. The two hymn videos in the matched set are landscape and must NOT be auto-classified as Shorts.
- The channel public Telegram audit read 119 recent visible messages; among these two native videos #1468 and #1493, no established repeat of the candidate Shorts series. Public HTML alone is not complete historical duplicate evidence.

## Eight exact native-transport media prepared locally

The canonical repository-owned prepare-media command accepted the following 8 intact copies without transcoding, strictly hashing both source and transport and checking codec, dimensions and duration. This is MEDIA readiness only, not editorial/rights/provider clearance.

| YouTube source ID | Ready bytes | Accepted media SHA256 |
|---|---:|---|
| _aDIR0D7rSk | 4,966,959 | sha256:e57d3cfe26f9c88b21b60f45919294e432383987ed9c58e92cced3eb792c93b7 |
| tELrnM71TQA | 16,558,893 | sha256:052e9d6a4f6c4d92ed8a750ad65f5ca4ab68f5efdc1641f512ea2e0887d42e8f |
| 2sapXv78y9Q | 26,284,322 | sha256:bdd3155e714f84da7c9acb01a6d09ca7182ebbea1f15e200c1da89baefffb4fe |
| PUlNpw83DFI | 8,884,076 | sha256:219f1f3d94e2447a28554886e7442fe97fa5eddac8d01f865b095c75e92754e1 |
| ba4ZahiY-U0 | 19,849,330 | sha256:7e8101677e8dc9514d01c864beddea3b6c96e8dd0c083f1274175d3bf789c64c |
| y9a7_3DutWk | 5,992,419 | sha256:88569eeec694082fac254888ff281add75758309d78973f61c4ffe2ff76e8e29 |
| EozlBy39F1c | 8,767,713 | sha256:af5cd3b5d20418127ef283781fca19eae4f35a12c4557e64a3ab82d0d609ee30 |
| VeY1tpoLUJU | 45,099,071 | sha256:b021cbec8e6495e7fec49107492a39781323060618cbdc31d05a63b297aa93e3 |

- Local source bindings: operator-output/lordchrist-shorts-eight-owned-local-master-bindings-20261106.json, exact file SHA256 ce78523b1139dc8c72363135af4894bdae6e0b19f60246b0d9a5e3921a93b126.
- Media acceptance: operator-output/lordchrist-shorts-eight-media-acceptance-20261106.json.
- Frozen current-snapshot wave: operator-output/lordchrist-shorts-wave-20261106-eight-media-review-hold/. It correctly records candidate_unconfirmed=282, accepted=0 under the strict editorial surface/rights gate. This is not a contradiction: eight physical MP4 transports exist, but none of the 282 candidates has exact human surface/release approval yet.
- All these artifact paths are LOCAL operator output and are deliberately not committed. They can expire under freshness policy and are not reusable evergreen release authority.

## Exact UTF-8 Windows defect and repair

The existing LordChrist ffprobe_media subprocess invoked ffprobe in Python text mode without explicit output encoding. On Windows with a non-UTF-8 default code page, output metadata with Russian names could trigger UnicodeDecodeError in subprocess reader threads and then json.loads(None) TypeError. This reproduced for the actual on-disk filenames of two more owned sources: lTRm2NbnIas and eyWl7bIV_Bk.

The fix explicitly decodes ffprobe JSON as UTF-8 with replacement for malformed metadata bytes. On Windows, exact real ffprobe of both Cyrillic filenames now succeeds; dimensions/duration are 1080x1920/144s and 1080x1918/70.767s. This does NOT imply these third-party preacher clips may be redistributed.

## Remaining hard holds

1. Exact editorial confirmation of vertical Shorts surface per source, current media bytes and source attribution; title, upload date and duration alone do not prove Shorts publication.
2. Copyright/license permissions for video and audio, especially John Piper, MacArthur, Sproul, Washer, Beeke and other third-party sermon content. File presence on a user-controlled YouTube channel is not rights clearance.
3. Read-only exact native-video duplicate reconciliation and the complete durable LordChrist state namespace before any new publisher/slot.
4. The current generic LordChrist profile and Shorts policy deliberately disable provider writes; Charnock, Jude 1:5 and quote lanes have separate ownership. A new release requires full explicit owner authorization, lock, exact target, one durable intent/attempt, and provider-verified message receipt.
5. No recurring timer, release or Telegram upload was activated. Daily 16:00 Moscow remains only a provider-inert editorial cadence.

This work does not modify YouTube #795, LordChrist existing quote/Charnock/Jude ledgers, other branches or protected state refs.


## Owner-requested four-video deferred review, 6 November 2026

A separate, provider-inert editorial preview now records exactly four
owned-channel accepted MP4s: three John MacArthur videos proposed
8, 9 and 10 November, and one John Piper video proposed 11 November,
one per day at 16:00 Moscow. All source media, caption text and
provenance SHA256s are pinned in
content/telegram/lordchrist/shorts-piper-macarthur-deferred-review-20261106.json.

This is NOT an active Telegram schedule and does not grant copyright
clearance. The channel owner requested reuploads and deferred slots,
but Desiring God expressly requires written permission for online
audio/video re-uploads and for public translations; a specific request
was sent 6 November and no affirmative answer is known. GTY's
historical 2019 limited grant and 2026 pending management review
cannot automatically be extended to unverified third-party footage
or these exact native Telegram videos. Do not put private email
correspondence or confidential identifiers in this public repository.

No LordChrist provider writer, state ref or scheduled workflow is
modified. Charnock/Jude/quote lanes have separate ownership.
The Shorts policy still has telegram_provider_mutation_allowed=false.
Publishing requires source-specific rightsholder evidence, latest
public duplicate check, exact approved release, full durable state,
serialization across existing writers and one verified Telegram receipt.

### Frozen UTF-8 caption repair (provider-inert)

A Windows PowerShell codepage damaged *only* the Russian source-label
and hashtags in the first four-copy preview, saving literal question
marks. New provider-inert captions regenerate the exact source label
and Russian tags as Unicode; SHA256 is recomputed per exact caption.
The source title, video ID, media bytes, 16:00 editorial date and
rights/license holds are byte-identical. The new regression test
fails closed on any run of four question marks, so a valid checksum
of corrupted text cannot be accepted.
