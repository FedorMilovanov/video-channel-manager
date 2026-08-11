# Milovi Cake VK Clips browser UI read

This runbook covers the next read-only evidence step for Issue #257 after both API enumeration paths proved incomplete or unavailable.

## Outcome

Collect a bounded inventory from the **public VK Video Clips UI** for exact Milovi Cake identity:

- `project_key=milovi-cake`
- VK community `68859909`
- VK owner `-68859909`
- public Clips route `https://vkvideo.ru/@milovi_cake/clips`

The resulting JSON is browser evidence only. It never claims a complete provider surface and never authorizes upload, edit, hide, delete, wall publication, or scheduling.

## Transport and safety

Transport: `browser_ui_read`.

The repository-owned reader uses only:

- one navigation to the exact canonical Milovi Clips route;
- DOM reads;
- provider response reads already caused by that page;
- programmatic scrolling to the current document end.

The implementation contains no click, double-click, form fill, selection, file input, keyboard-submit, or provider mutation primitive. It persists no cookies, headers, authorization data, request bodies, response bodies, or URL query strings.

A dedicated browser profile may be supplied explicitly, but the default is an ephemeral anonymous browser context. The credential/profile never selects the target; exact project/community/owner plus exact-owner Clip IDs do.

## Native Clip identity

A target record is admitted only when at least one browser observation proves one of:

1. a `clip<owner>_<id>` UI route for exact owner `-68859909`; or
2. a page response object explicitly contains `type=short_video`, `owner_id=-68859909`, and a positive exact video ID.

Foreign Clips rendered as recommendations are counted only as noise and never enter the Milovi target set.

The known Shrek Clip `-68859909_456239130` should be supplied as a coverage probe. Its presence strengthens route/target evidence; its absence is a coverage warning, not proof of provider absence.

## Bounded end condition

The reader scrolls until both the exact-owner Clip count and document height remain unchanged while the page is at the bottom for five consecutive rounds, or until the configured maximum scroll count is reached.

`bounded_ui_end_observed=true` means this scrolling condition was observed. It does **not** mean hidden, private, draft, deleted, moderation-limited, or otherwise non-rendered provider objects were enumerated. Therefore `surface_complete_claim` is always `false`.

## Local dependency

Playwright is an optional dependency because current CI does not need a browser binary:

```text
pip install -e ".[browser-read]"
```

The runtime uses an already installed Chromium-family browser. On Windows it searches Yandex Browser, Google Chrome, and Microsoft Edge in common locations. An exact executable can be supplied with `--browser-executable` if discovery fails.

## Operator output

Use the canonical operator outbox and one deterministic file:

```text
C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-cake-vk-clips-ui-inventory.json
```

After the operator returns that JSON, reconcile its exact Clip IDs against the previously captured immutable wall evidence. UI-only IDs prove public Clips not observed on that wall snapshot. Wall-only IDs prove only a UI coverage gap. Neither class by itself authorizes provider mutation.
