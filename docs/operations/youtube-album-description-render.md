# YouTube album description render from verified package

Status: local-only copy assembly. No provider access or mutation.

The tracked literary body may contain exactly one marker:

`[[CHAPTERS_FROM_EXACT_VERIFIED_TIMING]]`

That body is intentionally not publishable. The marker must be replaced only from a current `video-manager.album-package` whose canonical digest is valid and whose provenance includes exact source-manifest, timing, final-media and quality-master SHA-256 values.

Use:

```text
python -m video_channel_manager.youtube_album_description_cli \
  --project legendary-poet \
  --body content/youtube/legendary-poet/black-man-album-description-body.txt \
  --package <exact-final-album-package.json> \
  --output <new-immutable-description.txt> \
  --evidence <new-immutable-description.evidence.json>
```

The renderer fails closed when:

- the package schema or canonical package digest differs;
- project/channel binding is wrong;
- the package lacks exact `source_manifest_sha256`, `timing_sha256`, `final_media_sha256` or `quality_master_sha256`;
- `provider_write_authorized` is anything other than `false`;
- chapters are missing, malformed, do not begin at `00:00`, or do not increase strictly;
- the body contains zero or multiple chapter markers;
- either output path already exists.

The evidence sidecar binds the exact source body, album package, final media, quality masters, timing and rendered description hashes. It also remains `provider_write_authorized=false`.

After rendering, the generated text is the input to the separate guarded YouTube description planning/preflight workflow. Rendering chapters does not authorize a provider write.
