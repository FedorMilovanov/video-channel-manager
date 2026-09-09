# Instagram Legendary Poet production binding

Updated: 2026-09-09
Owning issue: #577
Provider effect at this checkpoint: `not_dispatched`

This record freezes the non-secret provider identity and read-only readiness evidence for the first production Instagram rollout of project `legendary-poet`. It is evidence only and does **not** authorize a provider mutation.

## Exact project and provider identity

- `project_key`: `legendary-poet`
- Facebook Page name: `The Legendary Poet`
- Facebook Page ID: `1299632476567433`
- Instagram Professional username: `the.legendary.poet`
- Instagram Professional account ID: `17841435926122104`
- selected compatibility transport: Facebook Login
- Graph host: `https://graph.facebook.com`
- provider version proved at this checkpoint: `v26.0`

The API version is checkpoint evidence, not a permanent constant. Every future rollout must resolve and review the current provider version again.

## Read-only evidence captured on 2026-09-09

The Facebook Page object resolved its `instagram_business_account` exactly to Instagram ID `17841435926122104` and username `the.legendary.poet`.

With the externally stored Page Access Token, the Instagram identity probe succeeded for:

```text
17841435926122104?fields=id,username
```

and resolved exactly to:

```json
{
  "id": "17841435926122104",
  "username": "the.legendary.poet"
}
```

The same Graph v26 route rejected `account_type` on this object with provider error `(#100) Tried accessing nonexisting field (account_type)`. Because production preflight uses the provider ID and optional username assertion as its identity invariants, the adapter must request only `id,username` instead of requiring an unrelated field that is unavailable on this compatibility route.

The publishing-limit endpoint was also readable:

```text
17841435926122104/content_publishing_limit?fields=quota_usage,config
```

Checkpoint response:

```json
{
  "data": [
    {
      "quota_usage": 0,
      "config": {
        "quota_total": 100,
        "quota_duration": 86400
      }
    }
  ]
}
```

Quota is time-varying evidence and must be read again immediately before an authorized canary.

Publishing-relevant granted permissions observed on the authorization used for the compatibility route include:

- `pages_show_list`
- `pages_read_engagement`
- `instagram_basic`
- `instagram_content_publish`

`business_management` was not present in the effective user-token permission readback and is not used as an invariant for this publisher path.

## Credential boundary

The working Page Access Token is secret operator material. Its value must exist only in ignored local `.env` / approved secret storage and must never be committed, pasted into an issue/PR, emitted in logs, or copied into an artifact.

Local runtime identity is expected to use:

```text
VCM_INSTAGRAM_LOGIN_MODE=facebook
VCM_INSTAGRAM_GRAPH_HOST=https://graph.facebook.com
VCM_INSTAGRAM_GRAPH_API_VERSION=<fresh-reviewed-version>
VCM_INSTAGRAM_ACCOUNT_ID=17841435926122104
VCM_INSTAGRAM_ACCOUNT_USERNAME=the.legendary.poet
VCM_INSTAGRAM_ACCESS_TOKEN=<secret-page-access-token>
VCM_INSTAGRAM_WRITES_ENABLED=false
```

The repository `.gitignore` excludes `.env` and `.env.*`; `.env.example` contains placeholders only.

## Rollout boundary

At this checkpoint:

- provider publications performed by this rollout: **0**;
- no Reel container has been created;
- no `media_publish` request has been dispatched;
- the production kill switch remains false;
- the first required live-runtime proof after the #577 adapter fix is a fresh read-only `video-manager instagram production preflight`;
- a live canary is a separate operation that requires an exact reviewed media artifact/binding, immutable public URL, manifest, caption/feed choice, durable ledger state and explicit execution authority for that exact publication.

A green repository PR, a valid credential, or this binding record alone is never execution authority.
