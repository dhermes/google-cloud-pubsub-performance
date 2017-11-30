This indicates an inherent problem:

```
timeLevel=00003115:DEBUG
logger=google.cloud.pubsub_v1.subscriber._consumer
threadName=Thread-gRPC-ConsumeRequestIterator
Sending initial request:
subscription: "projects/precise-truck-742/subscriptions/s-repro-1512072427168"
stream_ack_deadline_seconds: 10

----------------------------------------
timeLevel=00115947:DEBUG
logger=google.cloud.pubsub_v1.subscriber._consumer
threadName=Thread-gRPC-ConsumeRequestIterator+
Sending initial request:
subscription: "projects/precise-truck-742/subscriptions/s-repro-1512072427168"
stream_ack_deadline_seconds: 10

----------------------------------------
timeLevel=00123195:INFO
logger=message-after-recover-repro
threadName=Thread-ReproPublish
Published: After the policy recovered from failure.
----------------------------------------
timeLevel=00123646:DEBUG
logger=google.cloud.pubsub_v1.subscriber._consumer
threadName=Thread-ConsumerHelper-ConsumeBidirectionalStream
Received response:
received_messages {
  ack_id: "fjUwRUFeQBJMPgVESVMrQwsqWBFOBCEhPjA-RVNEUAYWLF1GSFE3GQhoUQ5PXiM_NSAoRREDIG8TJEJZGWJoXFx1B1ALGXIoaSZrXUBQCEVZfndrOTJpW1p8A1cLG3t4ZnVsXBYpjaCV5MNgZh89WxJLLD4"
  message {
    data: "After the policy recovered from failure."
    message_id: "176946629570665"
    publish_time {
      seconds: 1512072550
      nanos: 359000000
    }
  }
}

----------------------------------------
timeLevel=00123648:DEBUG
logger=google.cloud.pubsub_v1.subscriber.policy.thread
threadName=Thread-ConsumerHelper-ConsumeBidirectionalStream
New message received from Pub/Sub:
ack_id: "fjUwRUFeQBJMPgVESVMrQwsqWBFOBCEhPjA-RVNEUAYWLF1GSFE3GQhoUQ5PXiM_NSAoRREDIG8TJEJZGWJoXFx1B1ALGXIoaSZrXUBQCEVZfndrOTJpW1p8A1cLG3t4ZnVsXBYpjaCV5MNgZh89WxJLLD4"
message {
  data: "After the policy recovered from failure."
  message_id: "176946629570665"
  publish_time {
    seconds: 1512072550
    nanos: 359000000
  }
}

----------------------------------------
timeLevel=00123649:INFO
logger=message-after-recover-repro
threadName=ThreadPoolExecutor-SubscriberPolicy_0
 Received: After the policy recovered from failure.
----------------------------------------
timeLevel=00123651:DEBUG
logger=google.cloud.pubsub_v1.subscriber._consumer
threadName=Thread-gRPC-ConsumeRequestIterator
Sending request:
ack_ids: "fjUwRUFeQBJMPgVESVMrQwsqWBFOBCEhPjA-RVNEUAYWLF1GSFE3GQhoUQ5PXiM_NSAoRREDIG8TJEJZGWJoXFx1B1ALGXIoaSZrXUBQCEVZfndrOTJpW1p8A1cLG3t4ZnVsXBYpjaCV5MNgZh89WxJLLD4"

----------------------------------------
timeLevel=00143209:DEBUG
logger=google.cloud.pubsub_v1.subscriber._consumer
threadName=Thread-gRPC-ConsumeRequestIterator+
Request generator signaled to stop.
----------------------------------------
```

This is because both `Thread-gRPC-ConsumeRequestIterator` and
`Thread-gRPC-ConsumeRequestIterator+` are calling

```python
request = self._request_queue.get()
```

so when the `Message.ack()` adds to the request queue, it goes to
the "dead" thread `Thread-gRPC-ConsumeRequestIterator` because
that thread called the blocking `get()` **FIRST**. Then after we call
`policy.close()`, the `STOP` request goes to the second thread
`Thread-gRPC-ConsumeRequestIterator+` because it's `get()` call is
the oldest remaining. Hence, the **second** thread gets shut down, but
the first remains a zombie.
