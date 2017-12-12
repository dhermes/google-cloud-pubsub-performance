## Status: Fixed in `0.29.4` ([#4558][3] and [#4564][4])

This example does the following:

1. Creates a new topic
1. Creates a subscription to the created topic
1. Publishes 4000 messages to the new topic (must be done after
   creating the subscription)
1. Sleeps 10s, and then opens a subscription to the topic, attempting
   to ack all 4000 messages while using flow control to make sure at
   most 100 messages are active

This is a flow control issue [reported][1] by [@kir-titievsky] (the
Product Manager for Pub / Sub):

> When ran as it is against a subscription with a large backlog, it
> shows that the client thinks it's processing ~700 messages/second,
> while there is no outgoing traffic from the machine and the
> monitoring metrics show no `ack` / `modAckDeadline` traffic

This was caused by the "incorrect" way flow control was used to pause and
resume the consumer thread.

### `0.29.2`: Broken

The main thread exits with all workers stopped, but work pending:

```
timeLevel=00121837:INFO
logger=issue-4238-repro
threadName=MainThread
Consumer Request Queue Size=0
  Policy Request Queue Size=2402
  Policy Num. Ack On Resume=0
Policy Num. Managed Ack IDs=101
```

The actual gRPC logging added in `grpc_hacks` shows that no actual
messages are ever acked in the bidirectional streaming pull:

```
$ python issue-4238/parse_requests.py --filename 0.29.2.txt --show-all
----------------------------------------
timeLevel=00015294:DEBUG
logger=grpc._channel
threadName=Thread-gRPC-ConsumeRequestIterator
consume_request_iterator() sent:
subscription: "projects/precise-truck-742/subscriptions/s-repro-1513057993506"
stream_ack_deadline_seconds: 10

----------------------------------------
timeLevel=00017471:DEBUG
logger=grpc._channel
threadName=Thread-gRPC-ConsumeRequestIterator
consume_request_iterator() encountered StopIteration
----------------------------------------
```

What's more, the workers don't even **see** all 4000 messages
because the subscription policy gets closed before received
them all:

```
timeLevel=00115394:INFO
logger=issue-4238-repro
threadName=MainThread
Heartbeat:
running=False
done=True
active threads (11) =
  - MainThread
  - ThreadPoolExecutor-SubscriberPolicy
  - ThreadPoolExecutor-SubscriberPolicy+
  - ThreadPoolExecutor-SubscriberPolicy++
  - ThreadPoolExecutor-SubscriberPolicy+++
  - ThreadPoolExecutor-SubscriberPolicy++++
  - ThreadPoolExecutor-SubscriberPolicy+++++
  - ThreadPoolExecutor-SubscriberPolicy++++++
  - ThreadPoolExecutor-SubscriberPolicy+++++++
  - ThreadPoolExecutor-SubscriberPolicy++++++++
  - ThreadPoolExecutor-SubscriberPolicy+++++++++
exception=None
    Fut. is Policy's fut?=False
 Message ack rate (msg/s)=12.75846
 Total messages processed=1250
Unique messages processed=1250
```

### `0.29.4`: Fixed

(We skip the `0.29.3` release because it had a bug in lease maintenance.) The
main thread ends with no pending work:

```
timeLevel=00250461:INFO
logger=issue-4238-repro
threadName=MainThread
Consumer Request Queue Size=0
  Policy Request Queue Size=0
  Policy Num. Ack On Resume=0
Policy Num. Managed Ack IDs=0
```

The actual gRPC logging added in `grpc_hacks` shows that we all 4000
messages were acked:

```
$ python issue-4238/parse_requests.py --filename 0.29.4.txt
Non-ack messages:
========================================
timeLevel=00016109:DEBUG
logger=grpc._channel
threadName=Thread-gRPC-ConsumeRequestIterator
consume_request_iterator() sent:
subscription: "projects/precise-truck-742/subscriptions/s-repro-1513058171879"
stream_ack_deadline_seconds: 10

----------------------------------------
timeLevel=00241342:DEBUG
logger=grpc._channel
threadName=Thread-gRPC-ConsumeRequestIterator
consume_request_iterator() encountered StopIteration
========================================
Total consume_request_iterator() messages: 4021
Acks sent: 4000
```


[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4238
[2]: https://github.com/kir-titievsky
[3]: https://github.com/GoogleCloudPlatform/google-cloud-python/pull/4558
[4]: https://github.com/GoogleCloudPlatform/google-cloud-python/pull/4564

consume_request_iterator()
