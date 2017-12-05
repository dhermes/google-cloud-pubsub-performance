## Status: Identified as broken but not yet fixed

1. Creates a new topic
1. Creates a subscription to the created topic
1. Opens a subscriber to the new subscription
1. Spawns a publisher worker (in the background) that publishes 6 messages
   and then sleeps a random number of seconds in ``[0, 1]`` and continues
   to do this for 70 seconds
1. Uses a custom `Policy` that logs information about the load on the
   subscription every time `Policy._load >= 1.0` is checked
