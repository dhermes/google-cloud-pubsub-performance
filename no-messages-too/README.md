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

Adds a `_run_channel_spin_thread` patch that logs all the possible states
of the worker in the thread with `channel_spin() ...` messages.

### Current Hypothesis

The issue occurs in the [`channel_spin`][3] thread. In the
captured logs, the process was `28627`, and during the period of
100% CPU usage `ps auxw -L | grep 28627` was run.

```
$ ps auxw -L | grep 28627
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}  28627 28627  0.3    9  0.3 889424 59072 pts/2    Sl+  20:45   0:16 .../bin/python no-messages-too/script.py
${USER}  28627 28631  0.0    9  0.3 889424 59072 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28632  0.0    9  0.3 889424 59072 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28638  0.0    9  0.3 889424 59072 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28641  0.0    9  0.3 889424 59072 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28642  0.0    9  0.3 889424 59072 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28646  0.0    9  0.3 889424 59072 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627  3586 96.4    9  0.3 889424 59072 pts/2    Rl+  21:59   0:04 .../bin/python no-messages-too/script.py
${USER}  28627  3587  0.0    9  0.3 889424 59072 pts/2    Sl+  21:59   0:00 .../bin/python no-messages-too/script.py
$
$
$
$ ps auxw -L | grep 28627
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}  28627 28627  0.3    9  0.3 889424 59332 pts/2    Sl+  20:45   0:16 .../bin/python no-messages-too/script.py
${USER}  28627 28631  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28632  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28638  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28641  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28642  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28646  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627  7134 95.0    9  0.3 889424 59332 pts/2    Rl+  22:01   0:15 .../bin/python no-messages-too/script.py
${USER}  28627  7135  0.0    9  0.3 889424 59332 pts/2    Sl+  22:01   0:00 .../bin/python no-messages-too/script.py
$
$
$
$ ps auxw -L | grep 28627
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}  28627 28627  0.3    9  0.3 889424 59332 pts/2    Sl+  20:45   0:16 .../bin/python no-messages-too/script.py
${USER}  28627 28631  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28632  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28638  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28641  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28642  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627 28646  0.0    9  0.3 889424 59332 pts/2    Sl+  20:45   0:00 .../bin/python no-messages-too/script.py
${USER}  28627  7214 99.7    9  0.3 889424 59332 pts/2    Rl+  22:02   1:18 .../bin/python no-messages-too/script.py
${USER}  28627  7215  0.0    9  0.3 889424 59332 pts/2    Sl+  22:02   0:00 .../bin/python no-messages-too/script.py
```

and each of these corresponds to one of the threads we have named
`Thread-gRPC-StopChannelSpin` (see `thread_names.py` for how we intercept
calls to `threading.Thread` to give custom names):

```
----------------------------------------
timeLevel=04486419:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin++++++++++++++++++++++++++++++++++++++++++++++++++
Created TID: 3586
----------------------------------------
timeLevel=04564349:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin+++++++++++++++++++++++++++++++++++++++++++++++++++
Created TID: 7134
----------------------------------------
timeLevel=04643095:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin++++++++++++++++++++++++++++++++++++++++++++++++++++
Created TID: 7214
----------------------------------------
```

Note there are still three unknown `pthread`-s that are alive throughout
the process (likely created by [`gpr_thd_new`][4]). There are also
two unknown `pthread`-s that only show up during cleanup (i.e. after all
of the Pub / Sub code has shut down).

The `channel_spin() ...` messages when the CPU usage spikes to 100% don't
seem to be significantly different than those messages before.

CPU Usage spikes to 100%:
- `1h 1m 16.808s` (0.4%, `Thread-gRPC-StopChannelSpin+40`)
- `1h 1m 21.820s` (45.5%, `Thread-gRPC-StopChannelSpin+41`)
- `1h 1m 26.831s` (100.2%, `Thread-gRPC-StopChannelSpin+41`)
- ...
- `1h 3m 17.074s` (100.0%, `Thread-gRPC-StopChannelSpin+42`)

Every single `Thread-gRPC-StopChannelSpin` goes through four iterations
before exiting except for the very last one (there are 55 such threads).
Each of them also takes somewhere between 60 and 120 seconds, which
matches the expected amount of time before gRPC throws an `UNAVAILABLE`
due to inactivity.

**Exactly** one of the spin workers (`Thread-gRPC-StopChannelSpin+41`)
actually checks the credentials metadata (`Thread-gRPC-PluginGetMetadata+43`).
This corresponds **exactly** with the spin worker where CPU usage goes to
100%. It also perfectly explains why the problem manifests after an hour
(with some potential wiggle room).

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
