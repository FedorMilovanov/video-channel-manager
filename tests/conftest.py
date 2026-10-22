from __future__ import annotations

# The shared fixtures that used to live here were two workarounds and are gone:
#
# 1. An `xfail(strict=False)` that hid an assertion the parsed-link v3 contract had
#    inverted. The test now asserts the current contract instead of being excused from it.
# 2. An autouse fixture that monkeypatched `Path.write_text` globally so a legacy isolated
#    plan fixture would also receive the source contract. That test now copies the contract
#    explicitly, which is what it always depended on.
#
# Neither belonged in a global hook: both made a dependency invisible at the call site.
