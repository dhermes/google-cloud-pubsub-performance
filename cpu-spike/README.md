## Status: Still not able to reproduce

This example does the following:

1.  Creates a new topic
1.  Creates a subscription to the created topic
1.  Opens a subscriber to the new subscription
1.  Spawns a publisher worker that does the following in order
    in the background:
    - pushes 18 messages
    - sleeps 3 seconds
    - pushes 5 messages
    - sleeps 10 seconds
    - pushes 1 messages
    - sleeps 5 seconds
    - pushes 7 messages
    - sleeps 3 seconds

The goal of this example is to reproduce [reported][4] increases
in CPU usage.

----

Note here that the once all 10 executor threads are
active, they never become inactive:

```
timeLevel=00303498:INFO
logger=cpu-spike-repro
threadName=MainThread
Heartbeat:
running=True
done=False
active threads (18) =
  - MainThread
  - Thread-ConsumerHelper-CallbackRequestsWorker
  - Thread-ConsumerHelper-ConsumeBidirectionalStream
  - Thread-gRPC-ConsumeRequestIterator
  - Thread-LeaseMaintenance
  - ThreadPoolExecutor-SubscriberPolicy_0
  - ThreadPoolExecutor-SubscriberPolicy_1
  - ThreadPoolExecutor-SubscriberPolicy_2
  - ThreadPoolExecutor-SubscriberPolicy_3
  - ThreadPoolExecutor-SubscriberPolicy_4
  - ThreadPoolExecutor-SubscriberPolicy_5
  - ThreadPoolExecutor-SubscriberPolicy_6
  - ThreadPoolExecutor-SubscriberPolicy_7
  - ThreadPoolExecutor-SubscriberPolicy_8
  - ThreadPoolExecutor-SubscriberPolicy_9
  - Thread-gRPC-ConsumeRequestIterator+
  - Thread-gRPC-StopChannelSpin++
  - Thread-gRPC-ConsumeRequestIterator++
```

This is a feature of `ThreadPoolExecutor` and we should
almost certainly call `executor.shutdown()` **somewhere**.
We don't keep references to futures, but this has been
widely [reported][1] by users ([e.g.][2], [e.g.][3]).

[1]: https://bugs.python.org/issue27144
[2]: https://stackoverflow.com/q/37445540/1068170
[3]: https://stackoverflow.com/q/34770169/1068170
[4]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4234#issuecomment-339400158
