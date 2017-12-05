## Status: Fixed in `0.29.2` ([#4472][1] and [#4498][2])

This example does the following:

1. Creates a new topic
1. Opens a subscription for a subscription path that doesn't exist
1. Spawns a publisher worker that pushes 1 message to the topic (5 total)
   every 3 seconds in the background

When it fails, we expect the exception to be handled correctly and we
expect the exception to show up in logs. Before being fixed, the
`Policy` managing the subscription consumer was setting the exception
but not stopping the consumer, resuling in a `RuntimeError` after
trying to set an already-set exception.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/pull/4472
[2]: https://github.com/GoogleCloudPlatform/google-cloud-python/pull/4498
