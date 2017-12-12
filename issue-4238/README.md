## Status: Investigating

This is a flow control issue [reported][1] by [@kir-titievsky] (the
Product Manager for Pub / Sub):

> When ran as it is against a subscription with a large backlog, it
> shows that the client thinks it's processing ~700 messages/second,
> while there is no outgoing traffic from the machine and the
> monitoring metrics show no `ack` / `modAckDeadline` traffic

It seems likely that this was caused by the "incorrect" way flow control
was used to pause and resume the consumer thread. This hypothesis will be
tested with the example here against `0.29.2` (before the flow control
fix) and `0.29.4` after (the `0.29.3` release had a bug in lease maintenance).

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4238
[2]: https://github.com/kir-titievsky
