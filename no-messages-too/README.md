## Status: Broken in `0.29.4` (confirmed in Ubuntu 16.04)

This example does the following:

1. Creates a new topic
1. Creates a subscription to the created topic
1. Opens a subscriber to the new subscription
1. Runs for 80 minutes

This intentionally has no messages. As [reported][1], after `~65`
minutes, the process starts to consume 100% of CPU and doesn't
stop doing this until exiting at 80 minutes.

Adds a "thread creation interceptor" that wraps the `target` in a given
thread. Before running the target, the interceptor tracks a map of the
`pthread` ID to the thread name (i.e. the name given by Python). During each
"heartbeat", this mapping is used to verify that the active `pthread`-s
according to the operating system are the same as the active threads
according to Python.


### Current Hypothesis

The issue occurs in the [`channel_spin`][3] thread. In the
captured logs, the process was `2324`, and during the period of
100% CPU usage `ps auxw -L | grep 2324` was run.

```
$ ps auxw -L | grep 2324
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}   2324  2324  0.2    9  0.3 889264 55332 pts/2    Sl+  16:26   0:11 .../bin/python no-messages-too/script.py
${USER}   2324  2329  0.0    9  0.3 889264 55332 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2330  0.0    9  0.3 889264 55332 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2339  0.0    9  0.3 889264 55332 pts/2    Sl+  16:26   0:01 .../bin/python no-messages-too/script.py
${USER}   2324  2341  0.0    9  0.3 889264 55332 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2342  0.0    9  0.3 889264 55332 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2346  0.0    9  0.3 889264 55332 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  8599  100    9  0.3 889264 55332 pts/2    Rl+  17:33   0:45 .../bin/python no-messages-too/script.py
${USER}   2324  8601  0.0    9  0.3 889264 55332 pts/2    Sl+  17:33   0:00 .../bin/python no-messages-too/script.py
$
$
$
$ ps auxw -L | grep 2324
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}   2324  2324  0.2    9  0.3 889264 55336 pts/2    Sl+  16:26   0:12 .../bin/python no-messages-too/script.py
${USER}   2324  2329  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2330  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2339  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:01 .../bin/python no-messages-too/script.py
${USER}   2324  2341  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2342  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2346  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  9508  100    9  0.3 889264 55336 pts/2    Rl+  17:37   1:00 .../bin/python no-messages-too/script.py
${USER}   2324  9509  0.0    9  0.3 889264 55336 pts/2    Sl+  17:37   0:00 .../bin/python no-messages-too/script.py
$
$
$
$ ps auxw -L | grep 2324
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}   2324  2324  0.2    9  0.3 889264 55336 pts/2    Sl+  16:26   0:12 .../bin/python no-messages-too/script.py
${USER}   2324  2329  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2330  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2339  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:01 .../bin/python no-messages-too/script.py
${USER}   2324  2341  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2342  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324  2346  0.0    9  0.3 889264 55336 pts/2    Sl+  16:26   0:00 .../bin/python no-messages-too/script.py
${USER}   2324 10532 95.3    9  0.3 889264 55336 pts/2    Rl+  17:38   0:05 .../bin/python no-messages-too/script.py
${USER}   2324 10533  0.0    9  0.3 889264 55336 pts/2    Sl+  17:38   0:00 .../bin/python no-messages-too/script.py
```

and each of these corresponds to one of the threads we have named
`Thread-gRPC-StopChannelSpin` (see `thread_names.py` for how we intercept
calls to `threading.Thread` to give custom names):

```
----------------------------------------
timeLevel=03971109:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin++++++++++++++++++++++++++++++++++++++++++++
Created TID: 8599
----------------------------------------
timeLevel=04214416:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin+++++++++++++++++++++++++++++++++++++++++++++++
Created TID: 9508
----------------------------------------
timeLevel=04295317:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin++++++++++++++++++++++++++++++++++++++++++++++++
Created TID: 10532
----------------------------------------
```

Note there are still three unknown `pthread`-s that are alive throughout
the process (likely created by [`gpr_thd_new`][4]). There are also
two unknown `pthread`-s that only show up during cleanup (i.e. after all
of the Pub / Sub code has shut down).

### Debunked Hypothesis 1

When running this, there are three `pthread`-s unknown to Python, and
these currently seem to be the most likely culprit (though it will have
to wait for the current run to finish before the hypothesis can be
checked). It seems these threads are created by the gRPC C-core and are
not known to Python.

It's likely we can hook into this by [using `LD_PRELOAD`][2] to replace
`gpr_thd_new` at the ABI level:

```
$ strings .../grpc/_cython/cygrpc.cpython-36m-x86_64-linux-gnu.so \
> | grep gpr_thd_new
gpr_thd_new(&t_id, &run_poll, pargs, &opt)
gpr_thd_new
gpr_thd_new
```

or just build gRPC from source with extra logging.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4563
[2]: https://rafalcieslak.wordpress.com/2013/04/02/dynamic-linker-tricks-using-ld_preload-to-cheat-inject-features-and-investigate-programs/
[3]: https://github.com/grpc/grpc/blob/v1.8.0/src/python/grpcio/grpc/_channel.py#L710-L711
[4]: https://github.com/grpc/grpc/blob/v1.8.0/src/core/lib/support/thd_posix.cc#L58
