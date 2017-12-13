## Status: Broken in `0.29.4` (confirmed in Ubuntu 16.04)

This example does the following:

1. Creates a new topic
1. Creates a subscription to the created topic
1. Opens a subscriber to the new subscription
1. Runs for 80 minutes

This intentionally has no messages. As [reported][1], after `~65`
minutes, the process starts to consume 100% of CPU and doesn't
stop doing this until exiting at 80 minutes.

Adds a "thread creation interceptor" that wraps the `target` in a given
thread. Before running the target, the interceptor tracks a map of the
`pthread` ID to the thread name (i.e. the name given by Python). During each
"heartbeat", this mapping is used to verify that the active `pthreads`
according to the operating system are the same as the active threads
according to Python.

When running this, there are three `pthread`-s unknown to Python, and
these currently seem to be the most likely culprit (though it will have
to wait for the current run to finish before the hypothesis can be
checked). It seems these threads are created by the gRPC C-core and are
not known to Python.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4563
