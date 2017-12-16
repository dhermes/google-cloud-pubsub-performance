## Status: Broken in `0.29.4` (confirmed in Ubuntu 16.04)

This example does the following:

1. Creates a new topic
1. (Attempts to) publish 2000 messages to that topic all at once

This issue was first encountered when writing the `issue-4238/` case
and was [reported][1] shortly after.

The publisher client simply stalls without finishing.

From `0.29.4.svg`, we see that two `MonitorBatchPublisher` threads are
spawned when only one is expected.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4575
