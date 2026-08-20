# Legendary Poet — full channel video intake

Status: **provider-inert**  
Project: `legendary-poet`  
YouTube channel: `UC-78ys2S3cQ3lpqgXfo-SvQ`  
Built: 2026-08-20

This is the mandatory Instagram intake surface for the existing Legendary Poet video estate. It is not a publication plan and it does not authorize Instagram/Meta writes.

## Evidence boundary

The frozen cross-platform mapping `content/mappings/youtube-vk-reviewed-20260727.json` proves **111 exact YouTube video IDs** already associated with exact VK video IDs. That is a strong identity floor, but it is not a fresh current-channel snapshot and it does not contain enough information to label a record as a YouTube Short or long-form video.

The current repository already has the correct read-only YouTube acquisition path:

```powershell
video-manager youtube scan --account legendary-poet
```

`YouTubeApiClient.list_videos()` enumerates the exact uploads playlist and reads `snippet,contentDetails,status`, producing exact title, duration, publication time, privacy, tags, thumbnail and revision for each video. A fresh scan is therefore the authoritative way to close the current-channel delta; scraping titles or guessing from IDs is forbidden.

### Short classification rule

`duration_seconds` alone is **not** accepted as proof that a video is/was a YouTube Short. A confirmed Short requires provider/source evidence sufficient to distinguish the Shorts surface and/or exact source-media geometry. Until then the format state is `unknown`.

Unknown format does **not** remove a video from Instagram intake. It only changes the production route:

- confirmed native vertical/Short + clean project-owned master → `direct_remaster`;
- long-form + clean master → `editorial_extract`;
- no clean video master but source-owned audio/stills/evidence → `editorial_rebuild`;
- unresolved rights/provenance → `hold`.

Never download a YouTube/VK delivery encoding and silently treat it as the Instagram source master.

## Coverage

| Layer | Exact count | State |
| --- | ---: | --- |
| frozen YouTube↔VK identities | 111 | exact IDs proven |
| reviewed YouTube editorial records | 15 | title + source-led editorial record |
| remaining mapped videos | 96 | exact identity, metadata/content triage required |
| currently confirmed Shorts from frozen evidence | 0 | intentionally unclaimed |
| currently confirmed long-form from frozen evidence | 0 | intentionally unclaimed |
| format-unknown intake records | 111 | must be enriched by fresh read-only scan |

The zeroes above mean **“not proved by this frozen evidence”**, not “there are no Shorts/long videos”.

## Reviewed editorial subset

These 15 exact IDs already have reviewed source-led records under `content/youtube-comments/` and therefore enter content triage ahead of the metadata-only tail:

- `2GQ-T6dYH3E` — Ахматова, «Я научилась просто, мудро жить…»;
- `3ZFf2PBEYrM` — Есенин, «Что это такое?»;
- `48WeOZPMaOA` — historical/political rap reconstruction; rights/context hold;
- `5CzAVKhsscA` — «Перемен!» adaptation; rights hold;
- `BSJZ3BogD94` — English Esenin adaptation; translation/adaptation review;
- `GVMafWIYPpI` — Блок, «Россия», second creative;
- `K-x6neQiyfs` — Пушкин, «Песнь о Вещем Олеге»;
- `RQIlUvFf1KQ` — Тютчев, «Как хорошо ты, о море ночное…»;
- `U4D40EQg10U` — Блок, «На поле Куликовом»;
- `jkaayeq7q8g` — Фет, «Шёпот, робкое дыханье…»;
- `lXwlZt1v97U` — Блок, «О, я хочу безумно жить…»;
- `m8sCb7VV0Y4` — Кино, «Транквилизатор» adaptation; rights hold;
- `mFsty3NOEMs` — Есенин, «Отговорила роща золотая…»;
- `mw-dYETmPIE` — Есенин, «Чёрный человек»;
- `yaJNLxSSqZg` — Веня Д’ркин, `Anno Domini` adaptation; rights hold.

## Full exact-ID intake floor (111)

Every ID below must survive future scan reconciliation. A fresh channel scan may add newer uploads, but it must never silently lose one of these historical exact identities without an explicit provider-state explanation.

```text
-3GkI8wip-w
11u1wlWFT2Y
156l_su1P48
2GQ-T6dYH3E
2IyjbK4kdPs
3ZFf2PBEYrM
48WeOZPMaOA
4B3OTlPttFM
55IPY5t7AOo
5CzAVKhsscA
6XkCbkEnXI4
6caLdFvuvds
7IP9_wxDTAc
8S_JgM5u6QE
8ULM0GD_HdU
8g_4EVWFb1g
9Cvbz3QocUc
9nD37a7hKQ8
A5VfFPv1uSg
Ac7Fz_9HS3I
BSJZ3BogD94
BXZeRiEOHmQ
BqXU9uRCJa4
BrD1lJQhghk
C5gFOn8SS0M
CS0soMka39A
CX7VRsIlKDw
CfpwtD7lWK0
DoPW2_Q1sM4
DrfeOZmkwBY
E4gJWCKD50s
EOaXd3EKNxA
F5kgP197YUE
FHytR5WwyeM
GVMafWIYPpI
GmKQXseJH04
I1OsM65y-Lo
ItewE1lCUJ8
IvAnQnO2CtQ
JefLdqrWmUM
K-x6neQiyfs
KUDVfsn_atc
Kn0D5laf5hs
L5R0QgwMsgY
LekwmjWVP10
LjNpRbJ57Sc
LrLPe5TgJpA
LwJSzH9CBBE
MBdv5JvWuhw
NFLJP84QQo4
RQIlUvFf1KQ
RdLTSe_n71s
S_3XdEGW4cU
Sdv8puPeJYw
T6WIgGaZm74
TDbW__q3hYk
U14Mh3TNwac
U4D40EQg10U
UiEX0HOJTsw
V9XRuxOHl5E
VZAhM-mfgQw
Wsbkvfzq5x0
YrDKZGQNvpA
Yy__6RGVpNE
ZArgxRj7Vro
ZjfSTrLCKK4
_G_raWj44iU
_JhTcxchSn8
b0VHXLc6rnc
bStyYN4dvEs
cMuGYGlaof8
c__ZdqdiSJ0
dafBBWweSWs
eD0fngOI4Qo
fBceuJz15Fc
g9bW6upeQCg
gQwDrtkCBpo
gavdyL0QWJU
ib2ehg2__sg
ivADfDPt7Ww
jIiluJTjf0A
jJ3kVn43QB8
jkaayeq7q8g
jnxnK-CYQ7Q
kGav2FpMaZc
kSpmh5OKCtg
l-nzhGTw0V0
lMnZR1SeVdE
lXwlZt1v97U
laxWRb47N4M
m8sCb7VV0Y4
mFj0U1Sj_Ik
mFsty3NOEMs
mLkldhGvUZ0
mw-dYETmPIE
nR5xNFlk3z4
nZ8T74rjROc
oS6fpnaKhBs
pE5Im38_jN0
r1YIF5scHgU
sPbdDHtMlsA
ux2T7UVjUpM
vCYylNPkP6c
vjydzctHIeI
vk_9nWPYwwA
wFHa8VOom3U
x-TPtQ9E2mc
xqRJU9DS2cc
y-iTEdO52_c
yGr0cSKW-Og
yaJNLxSSqZg
```

## Reconciliation contract for the fresh scan

The next read-only inventory snapshot must produce, per video:

```text
youtube_video_id
channel_id
title
duration_seconds
published_at
privacy_status
tags
thumbnail_url
revision
present_in_20260727_mapping
exact_vk_video_id (when mapped)
reviewed_editorial_record (when present)
source_master_binding
source_width
source_height
source_duration
source_sha256
youtube_format_status = confirmed_short | confirmed_longform | unknown
instagram_route = direct_remaster | editorial_extract | editorial_rebuild | hold
rights_status
priority
```

No Reel timing may be frozen before the exact source master is bound. No “best 20 seconds” may be invented from a title or remembered version.

## Intake priority

1. **P0:** reviewed public-domain poetry records with strong source-led facts and no obvious modern-work rights dependency.
2. **P1:** project-owned site music/audio and second creatives that can expand the identity without duplicating the same Reel.
3. **P2:** the remaining 96 mapped exact IDs after fresh title/duration/source reconciliation.
4. **P3:** modern song adaptations, translation-heavy adaptations and political/historical reconstructions until rights/context review is complete.

This file deliberately turns the entire known video estate into work. `unknown` means “needs exact evidence”, never “ignore it”.