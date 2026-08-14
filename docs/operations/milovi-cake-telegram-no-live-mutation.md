# No-live-mutation boundary — Milovi Cake Telegram onboarding

Owning issue: #353.

This onboarding PR must not perform or authorize a live provider mutation. In particular, branch review/merge does not authorize Telegram publication, invite creation, pinning, editing, deletion, admin changes, Dzen sync, VK writes or advertising spend.

The next permissible provider interaction after merge is the separately documented **read-only** exact-target discovery workflow. A live canary requires a later exact payload digest and explicit one-operation authorization in #353.
