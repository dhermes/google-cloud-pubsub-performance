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

### Failure Case (`0.29.4`):

From our heartbeats:

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

To see this:

```
----------------------------------------
timeLevel=00001541:DEBUG
logger=publish-many-repro
threadName=Thread-MonitorBatchPublisher
_commit(<__main__.CustomBatch object at 0x7fa55344a978>):
caller = monitor
topic = projects/precise-truck-742/topics/t-repro-1513705130612
status = accepting messages
len(messages) = 500
len(futures) = 500
----------------------------------------
timeLevel=00011581:DEBUG
logger=publish-many-repro
threadName=Thread-CommitBatchPublisher
_commit(<__main__.CustomBatch object at 0x7fa55344aa20>):
caller = commit
topic = projects/precise-truck-742/topics/t-repro-1513705130612
status = in-flight
len(messages) = 1000
len(futures) = 999
----------------------------------------
timeLevel=00011588:DEBUG
logger=publish-many-repro
threadName=Thread-MonitorBatchPublisher+
_commit(<__main__.CustomBatch object at 0x7fa55344aa20>):
caller = monitor
topic = projects/precise-truck-742/topics/t-repro-1513705130612
status = in-flight
len(messages) = 1000
len(futures) = 1000
----------------------------------------
timeLevel=00011609:DEBUG
logger=publish-many-repro
threadName=Thread-CommitBatchPublisher+
_commit(<__main__.CustomBatch object at 0x7fa5511be908>):
caller = commit
topic = projects/precise-truck-742/topics/t-repro-1513705130612
status = in-flight
len(messages) = 1000
len(futures) = 999
----------------------------------------
timeLevel=00011631:DEBUG
logger=publish-many-repro
threadName=Thread-MonitorBatchPublisher++
_commit(<__main__.CustomBatch object at 0x7fa5511be908>):
caller = monitor
topic = projects/precise-truck-742/topics/t-repro-1513705130612
status = in-flight
len(messages) = 1000
len(futures) = 1000
----------------------------------------
```

We see that `status` is already set to "in-flight" when `_commit`
is called (but `_commit` is a no-op unless `status` is "accepting messages").

We **also** see that in one of the cases, `len(messages)` is not equal
to `len(futures)`, which is **another** sort of concurrency problem.

### Success Case (`0.30.0`):

All messages are published:

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
```

To see the actual batches that get published:

```
----------------------------------------
timeLevel=00001342:DEBUG
logger=publish-many-repro
threadName=Thread-MonitorBatchPublisher
_commit(<__main__.CustomBatch object at 0x7f4f00c6a9b0>):
caller = monitor
topic = projects/precise-truck-742/topics/t-repro-1513705091078
status = accepting messages
len(messages) = 500
len(futures) = 500
----------------------------------------
timeLevel=00011394:DEBUG
logger=publish-many-repro
threadName=Thread-CommitBatchPublisher
_commit(<__main__.CustomBatch object at 0x7f4f00c6aa58>):
caller = commit
topic = projects/precise-truck-742/topics/t-repro-1513705091078
status = starting
len(messages) = 1000
len(futures) = 1000
----------------------------------------
timeLevel=00011398:DEBUG
logger=publish-many-repro
threadName=Thread-MonitorBatchPublisher+
_commit(<__main__.CustomBatch object at 0x7f4f00c6aa58>):
caller = monitor
topic = projects/precise-truck-742/topics/t-repro-1513705091078
status = in progress
len(messages) = 1000
len(futures) = 1000
----------------------------------------
timeLevel=00011657:DEBUG
logger=publish-many-repro
threadName=Thread-MonitorBatchPublisher++
_commit(<__main__.CustomBatch object at 0x7f4ef29b9a20>):
caller = monitor
topic = projects/precise-truck-742/topics/t-repro-1513705091078
status = accepting messages
len(messages) = 991
len(futures) = 991
----------------------------------------
timeLevel=00011890:DEBUG
logger=publish-many-repro
threadName=Thread-MonitorBatchPublisher+++
_commit(<__main__.CustomBatch object at 0x7f4ef29b9a58>):
caller = monitor
topic = projects/precise-truck-742/topics/t-repro-1513705091078
status = accepting messages
len(messages) = 9
len(futures) = 9
----------------------------------------
```

**NOTE**: The **size** of each batch be dependent on how much the system
can accomplish in `0.05s`, hence is not deterministic.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4612
[2]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4613
[3]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4614
[4]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4616
[5]: https://github.com/GoogleCloudPlatform/google-cloud-python/releases/tag/pubsub-0.30.0
[6]: https://github.com/GoogleCloudPlatform/google-cloud-python/blob/pubsub-0.29.4/pubsub/google/cloud/pubsub_v1/publisher/batch/thread.py#L143
[7]: https://github.com/GoogleCloudPlatform/google-cloud-python/blob/pubsub-0.29.4/pubsub/google/cloud/pubsub_v1/publisher/batch/thread.py#L167-L168
