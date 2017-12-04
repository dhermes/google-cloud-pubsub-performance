**Status**: Fixed in `0.29.1` ([#4444][1])

1. Creates a new topic
1. Creates a subscription to the created topic
1. Opens a subscriber to the new subscription

This intentionally has no messages. It was used as the original
test case to show that `0.29.0` was not correctly handling
`UNAVAILABLE` exceptions. It was both setting an exception and
**not** exiting after the exception, resulting in a `RuntimeError`
the second time the exception occurred.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/pull/4444
