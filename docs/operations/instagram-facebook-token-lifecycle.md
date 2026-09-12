# Instagram Facebook Login credential lifecycle

Updated: 2026-09-10
Owner: issue #581

This runbook covers safe credential replacement and read-only validation for the registered `legendary-poet` Instagram Facebook Login compatibility route. It does not authorize any Instagram provider mutation.

## Exact registered target

Credentials authenticate requests; they do not select the project or provider target.

- project key: `legendary-poet`
- Instagram Professional account ID: `17841435926122104`
- Instagram username assertion: `the.legendary.poet`
- linked Facebook Page ID: `1299632476567433`
- linked Facebook Page name: `The Legendary Poet`
- login mode: `facebook`
- Graph host: `https://graph.facebook.com`

Any mismatch in the numeric Facebook Page or Instagram account identity is a stop condition. Never change the target merely to match whichever object a credential resolves.

## Secret handling

Access tokens, application secrets, authorization codes and Authorization headers are secret material.

- Never commit them to Git or paste them into issues, pull requests, artifacts, screenshots, test fixtures or logs.
- Keep credential issuance and replacement in Meta's official tooling and approved local secret storage.
- Store the active runtime credential only in ignored local `.env` or another approved secret store.
- Never put a credential value in a publish manifest or durable provider-evidence JSON.
- Keep `VCM_INSTAGRAM_WRITES_ENABLED=false` throughout credential replacement and read-only verification.

## Replacement procedure

Meta can change credential issuance and lifetime rules, so use Meta's current official Facebook Login tooling/documentation to issue or replace the operator credential. The repository deliberately does not freeze a promised token lifetime or a permanent Graph API version.

After Meta-side replacement:

1. Bind the credential to the exact registered Facebook Page `1299632476567433`; reject any other Page identity.
2. Store the resulting runtime credential only in ignored local secret storage as `VCM_INSTAGRAM_ACCESS_TOKEN`.
3. Configure the non-secret provider assertions independently:

   ```text
   VCM_INSTAGRAM_LOGIN_MODE=facebook
   VCM_INSTAGRAM_GRAPH_HOST=https://graph.facebook.com
   VCM_INSTAGRAM_GRAPH_API_VERSION=<currently reviewed version>
   VCM_INSTAGRAM_ACCOUNT_ID=17841435926122104
   VCM_INSTAGRAM_ACCOUNT_USERNAME=the.legendary.poet
   VCM_INSTAGRAM_WRITES_ENABLED=false
   ```

4. From current `main`, run only the read-only provider check:

   ```text
   video-manager instagram production preflight
   ```

5. Accept the credential for further planning only if preflight proves the exact Instagram account ID and username and can read the publishing-limit endpoint.
6. Leave `VCM_INSTAGRAM_WRITES_ENABLED=false`. A successful preflight is readiness evidence, not live execution authority.

## Error classification

Meta OAuth error code `190` is treated by the CLI as the invalid-or-expired credential class. On the Facebook Login route the operator is instructed to replace the Facebook-side credential through approved Meta tooling, bind it again to the exact registered Page, and rerun read-only preflight.

For this class the CLI intentionally does not echo the raw provider error message. This avoids turning provider diagnostic text into an accidental secret-bearing log surface.

On error code `190`:

- do not retry publishing;
- do not enable provider writes;
- do not alter the configured Page or Instagram identity;
- replace the credential outside Git;
- rerun read-only preflight from current `main`.

Other provider error codes remain ordinary provider diagnostics and are not mislabeled as credential expiry.

## Longer-lived credentials

A longer-lived credential can reduce operator churn, but it is never standing execution authority and its lifetime must not be hard-coded as a repository invariant. A credential can expire or be invalidated independently of the repository state.

Credential rotation must never create a new publication identity, reset a durable publication ledger, reopen an ambiguous provider mutation, or bypass the existing no-blind-retry state machine.

## Completion boundary

Repository-side credential lifecycle work is complete, and Issue #581 is closed as completed after the first successful Legendary Poet production Reel canary. The reviewed URL-transport publication `legendary-poet-yesenin-chto-eto-takoe-url-canary-20260912-01` reached durable `published` / provider `PUBLISHED`; exact media `18135337036649890` is independently visible as a `REELS`/`VIDEO` object at `https://www.instagram.com/reel/DdMgCixE8Gl/`. The write kill switch was restored to false after the single authorized invocation. This success is evidence only, not standing authority: every future Instagram release requires a new immutable publication identity, fresh point-in-time target/quota/duplicate/media proof and fresh operation-specific execution authority.
