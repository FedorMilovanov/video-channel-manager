# Milovi Cake Telegram canary preparation

Date: 2026-08-15
Owning issue: #353
Status: **proposal only — no provider-write authorization**

## Purpose

Define the smallest first live operation so target onboarding does not drift into a batch release.

## Candidate content

Use `MC-TG-001` from `content/telegram/milovi-cake/launch-pack-2026-08.md` as the first canary candidate, but render it as a **single text message only** for the first provider mutation.

Why text-only:

- proves the exact channel/bot/binding path with the smallest provider surface;
- avoids mixing media-upload behavior into target identity verification;
- avoids a separate pin operation;
- is easy to verify byte-for-byte against the reviewed payload.

## Not part of the first canary

- no media upload;
- no poll;
- no pin;
- no edit after send;
- no second post;
- no schedule/batch;
- no Dzen sync;
- no invite-link creation;
- no admin-right mutation.

## Preconditions

The canary remains blocked until all are true:

1. provider-inert onboarding PR is merged and CI is green;
2. Milovi-only read-only discovery is run from current `main`;
3. exact negative numeric `chat_id` is reviewed;
4. bot id/username match `8716602202` / `preaching_mp3_bot`;
5. immutable target binding is separately committed;
6. cross-project fail-closed tests are green;
7. `MC-TG-001` is re-reviewed for current wording and links;
8. an exact rendered provider payload digest is recorded in #353;
9. #353 is amended with explicit authorization for **that one payload only**.

## Outcome verification

After the single send, record:

- provider response/message id;
- exact channel id/username observed;
- expected plain text vs provider result;
- timestamp;
- release/payload digest;
- whether the outcome is confirmed success, confirmed failure-before-dispatch, or ambiguous.

If the outcome is ambiguous, **do not retry blindly**. Stop and reconcile provider state first.

A successful canary does not authorize the second post. Subsequent scheduling/release scope must be reviewed separately.
