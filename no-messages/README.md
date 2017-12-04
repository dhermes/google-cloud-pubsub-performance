1. Creates a new topic
1. Creates a subscription to the created topic
1. Opens a subscriber to the new subscription

This intentionally has no messages. It was used as the original
test case to show that `0.29.0` was not correctly handling
UNAVAILABLE exceptions.
