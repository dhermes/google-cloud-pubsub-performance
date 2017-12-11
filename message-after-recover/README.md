## Status: Fixed in `0.29.3/0.29.4` ([#4503][1])

1. Creates a new topic
1. Creates a subscription to the created topic
1. Opens a subscriber to the new subscription
1. Spawns a publisher worker (in the background) that waits until the
   subscriber has recovered from an UNAVAILABLE error before publishing
   a single message, then sleeping for 20 seconds and closing the
   subscriber

----

This indicates an inherent problem, present in `0.29.2`:

```
----------------------------------------           +
timeLevel=00003890:DEBUG                           |
logger=google.cloud.pubsub_v1.subscriber._consumer |
threadName=gRPC-ConsumeRequestIterator             |
Sending initial request:                           |
subscription: "${SUB}"                             |
stream_ack_deadline_seconds: 10                    |
                                                   |
----------------------------------------           +
                                                   | timeLevel=00115817:DEBUG
                                                   | logger=google.cloud.pubsub_v1.subscriber._consumer
                                                   | threadName=gRPC-ConsumeRequestIterator+
                                                   | Sending initial request:
                                                   | subscription: "${SUB}"
                                                   | stream_ack_deadline_seconds: 10
                                                   |
----------------------------------------           +
timeLevel=00123991:INFO                            |
logger=message-after-recover-repro                 |
threadName=ReproPublish                            |
Published: After the policy recovered from ...     |
----------------------------------------           +
timeLevel=00124823:DEBUG                           |
logger=google.cloud.pubsub_v1.subscriber._consumer |
threadName=ConsumerHelper-ConsumeBidirectionalStream
Received response:                                 |
received_messages {                                |
  ack_id: "${ACK_ID}"                              |
  message {                                        |
    data: "After the policy recovered from ..."    |
    message_id: "178698045084220"                  |
    publish_time {                                 |
      seconds: 1512434190                          |
      nanos: 692000000                             |
    }                                              |
  }                                                |
}                                                  |
                                                   |
----------------------------------------           +
timeLevel=00124825:DEBUG                           |
logger=google.cloud.pubsub_v1.subscriber.policy.thread
threadName=ConsumerHelper-ConsumeBidirectionalStream
New message received from Pub/Sub:                 |
ack_id: "${ACK_ID}"                                |
message {                                          |
  data: "After the policy recovered from ..."      |
  message_id: "178698045084220"                    |
  publish_time {                                   |
    seconds: 1512434190                            |
    nanos: 692000000                               |
  }                                                |
}                                                  |
                                                   |
----------------------------------------           +
timeLevel=00124826:INFO                            |
logger=message-after-recover-repro                 |
threadName=ThreadPoolExecutor-SubscriberPolicy_0   |
 Received: After the policy recovered from ...     |
----------------------------------------           +
timeLevel=00124827:DEBUG                           |
logger=google.cloud.pubsub_v1.subscriber.policy.thread
threadName=ConsumerHelper-ConsumeBidirectionalStream
Result: Message {                                  |
    data: b'After the policy recovered from ...'   |
    attributes: ...                                |
}                                                  |
----------------------------------------           +
timeLevel=00124828:DEBUG                           |
logger=google.cloud.pubsub_v1.subscriber._consumer |
threadName=gRPC-ConsumeRequestIterator             |
Sending request:                                   |
ack_ids: "${ACK_ID}"                               |
                                                   |
----------------------------------------           +
                                                   | timeLevel=00144011:DEBUG
                                                   | logger=google.cloud.pubsub_v1.subscriber._consumer
                                                   | threadName=gRPC-ConsumeRequestIterator+
                                                   | Request generator signaled to stop.
----------------------------------------           +
```

This is because both `gRPC-ConsumeRequestIterator` and
`gRPC-ConsumeRequestIterator+` are calling

```python
request = self._request_queue.get()
```

so when the `Message.ack()` adds to the request queue, it goes to
the "dead" thread `gRPC-ConsumeRequestIterator` because
that thread called the blocking `get()` **FIRST**. Then after we call
`policy.close()`, the `STOP` request goes to the second thread
`gRPC-ConsumeRequestIterator+` because it's `get()` call is
the oldest remaining. Hence, the **second** thread gets shut down, but
the first remains a zombie.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/pull/4503
