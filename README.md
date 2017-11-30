# Performance Tests for `google-cloud-pubsub`

This is an assemblage of scripts that exercise long(ish)-lived states
for the Google Cloud Pub / Sub Python client.

In particular, it tracks the threads created (including the parent
thread creating them) and makes sure threads don't get turned
into "zombies".

Some issues worth exploring:

- Reports of lease management causing [CPU spikes][1] (seems like
  zombie threads)

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4288
