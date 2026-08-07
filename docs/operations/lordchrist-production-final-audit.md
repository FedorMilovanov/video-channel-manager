# Lordchrist production final audit — 2026-08-07

This audit hardens the already enabled autonomous publisher before its first eligible scheduled send on 2026-08-08.

Key conclusions implemented in the companion branch/PR:

- scheduled production remains independent from the manual posting toggle;
- production config is release-bound to exact channel ID, bot ID, bot username, queue digest and presentation policy digest;
- presentation policy v2 selects the longest direct quote for bold emphasis instead of blindly bolding the first quoted fragment;
- all other direct quotes remain italic;
- source queue and durable publication ledger remain unchanged;
- no Telegram provider write is performed by this audit/PR;
- next strict item remains `lordchrist-bunyan-fire-grace` until a verified scheduled send occurs.

The 2026-08-07 21:17 window is intentionally before `not_before_moscow_date=2026-08-08` and therefore cannot authorize a provider mutation.
