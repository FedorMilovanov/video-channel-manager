# Review notes — Milovi Cake Telegram onboarding

- Scope is provider-inert.
- Exact numeric `chat_id` is intentionally absent until read-only provider proof.
- Editorial drafts are not runtime queues.
- Five unsupported review placeholders found during audit were removed and regression-blocked.
- Shared bot architecture is preserved; no duplicate bot is introduced.
- Workflow is Milovi-only; generic Python discovery logic remains reusable/tested.
- Canary proposal is one text-only message and still requires explicit later authorization.
