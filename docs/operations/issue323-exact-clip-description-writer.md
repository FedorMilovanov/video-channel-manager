# Issue #323 exact Clip description boundary

`VkVideoDescriptionWriter.replace_description_if_current()` is the exact provider primitive for a reviewed native VK Clip description transition.

The boundary is intentionally narrower than `VkVideoTextWriter`:

- exact owner/video identity is required;
- the provider object must remain `type=short_video`;
- exact title is frozen before dispatch and must be unchanged after dispatch;
- reviewed BEFORE and AFTER descriptions are compared as exact strings with no whitespace, Unicode, line-ending, or zero-width normalization;
- exactly one `video.edit` is permitted and transient mutation retry is disabled;
- provider acknowledgement is provisional; bounded safe `video.get` reads must prove exact AFTER before the primitive returns success;
- any ambiguous mutation response or non-exact postflight requires reconciliation and forbids replay.

This primitive does not own Issue #323 durable dispatch authority. The canonical promotion dispatcher must persist `EDIT_DISPATCH_STARTED` before calling it and must use fresh canonical promotion observation to mark the durable journal `VERIFIED`.
