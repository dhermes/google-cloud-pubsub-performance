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
