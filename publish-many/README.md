## Status: Fixed in `0.30.0` ([#4612][1], [#4613][2], [#4614][3] and [#4616][4])

This example does the following:

1. Creates a new topic
1. (Attempts to) publish 2000 messages to that topic all at once

This issue was first encountered when writing the `issue-4238/` case
and was [reported][1] shortly after.

This issue had two components, most explained in the
[`0.30.0` release notes][5]:

> There were two related bugs. The first: if a batch exceeds the
> `max_messages` from the batch settings, then the `commit()` will fail.
> The second: when a "monitor" worker calls `commit()` after `max_latency`
> seconds, a failure can occur if a new message is added to the batch
> **during** the commit.

In `0.29.4.txt`:

```
$ cat 0.29.4.txt | grep -n 'Done='
32:Publish Futures Done=0, Failed=0, Total=500
49:Publish Futures Done=500, Failed=0, Total=500
61:Publish Futures Done=500, Failed=0, Total=500
79:Publish Futures Done=0, Failed=0, Total=2000
91:Publish Futures Done=0, Failed=0, Total=2000
103:Publish Futures Done=0, Failed=0, Total=2000
115:Publish Futures Done=0, Failed=0, Total=2000
127:Publish Futures Done=0, Failed=0, Total=2000
```

we see that **none** of the batches of `2000` messages get published. This
is because a [bug in `commit()`][6] made it so that `_commit()` was
[always a no-op][7] when called from `commit()`.

However, in `0.30.0.txt` all messages are published:

```
$ cat 0.30.0.txt | grep -n 'Done='
32:Publish Futures Done=0, Failed=0, Total=500
54:Publish Futures Done=500, Failed=0, Total=500
66:Publish Futures Done=500, Failed=0, Total=500
105:Publish Futures Done=1000, Failed=0, Total=2000
127:Publish Futures Done=2000, Failed=0, Total=2000
139:Publish Futures Done=2000, Failed=0, Total=2000
151:Publish Futures Done=2000, Failed=0, Total=2000
163:Publish Futures Done=2000, Failed=0, Total=2000
``

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4612
[2]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4613
[3]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4614
[4]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4616
[5]: https://github.com/GoogleCloudPlatform/google-cloud-python/releases/tag/pubsub-0.30.0
[6]: https://github.com/GoogleCloudPlatform/google-cloud-python/blob/pubsub-0.29.4/pubsub/google/cloud/pubsub_v1/publisher/batch/thread.py#L143
[7]: https://github.com/GoogleCloudPlatform/google-cloud-python/blob/pubsub-0.29.4/pubsub/google/cloud/pubsub_v1/publisher/batch/thread.py#L167-L168
