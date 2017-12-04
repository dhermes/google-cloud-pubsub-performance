This example does the following:

1. Creates a new topic
1. Opens a subscription for a subscription path that doesn't exist
1. Spawns a publisher worker that pushes 1 message to the topic (5 total)
   every 3 seconds in the background

When it fails, we expect the exception to be handled correctly and we
expect the exception to show up in logs.
