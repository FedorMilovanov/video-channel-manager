# Neural-dubbed YouTube media: one practical audio acceptance gate

Scope: guarded YouTube releases with AI-translated or AI-generated speech. This is one additional prepublication check, **not** a new TTS service or a requirement for the channel owner to listen to every word. The actual agent workflow is already in MP3Bot `docs/agent_direct_dubbing/README.md`.

1. **Review the final exported MP4 audio.** For Shorts (up to three minutes), review the full audio once. For long recordings, review known repaired passages, all Scripture/name/stress-risk occurrences, joins and distributed samples. The operator or AI agent must have genuine audio-listening capability; otherwise mark `NOT_REVIEWED`. Do not convert Whisper/SRT/ffprobe PASS into a listening verdict.
2. Keep a **small pronunciation watchlist**, not a per-word bureaucracy: Russian `Ева́нгелие` (stress on the *va*), biblical book and person names, recurring theological words. Text or ASR similarity does not prove phonetic stress. On a confirmed defect, patch only the affected acoustic window, review the joins and the final exported audio again.
3. On a new YouTube v2 upload spec for an AI-dubbed release, set `audio_review_required: true`. The existing intent and release-plan digest will carry the requirement. This is **not inferred from** `containsSyntheticMedia`, which may refer solely to images. Legacy non-dubbed plans retain existing behavior.
4. After actual final-MP4 playback, add one compact record to the **existing signed execution approval**; its top-level `reviewed_by` / `reviewed_at` still identify the release approver, while the record below identifies the agent who actually listened:

```json
"final_audio_review": {
  "verdict": "PASS",
  "media_sha256": "sha256:<exact digest of final MP4>",
  "listened_from_final_mp4": true,
  "reviewer": "agent-who-actually-listened",
  "reviewed_at": "2026-11-15T05:00:00+00:00"
}
```

The guard requires a positive result bound to the exact MP4 SHA, and rejects an explicit `human_audio_listening_certified: false` even for older approvals. Never invent playback or set `true` merely to pass CI. YouTube authorization, copyright permission and the duplicate-upload journal remain separate gates.

**Confirmed incident:** APJ #1159 Short `cs3LJ7XBIB0`, around 00:04–00:11. Written transcript/ASS showed the word correctly, while the user reported defective pronunciation. The final Short retained the preexisting audio stream byte-for-byte; its historical execution approval declared `human_audio_listening_certified: false`. This is a *missing acceptance* defect, not evidence that ASR can diagnose Russian stress. The published video cannot have its audio replaced in-place; a corrected replacement requires a distinct editorial/publication decision and existing-target reconciliation.

The gate proves presence of a media-bound attestation, not that an agent truly listened or correctly perceived every syllable. Honor `AGENTS.md`, MP3Bot editorial rules, and actual audio evidence.