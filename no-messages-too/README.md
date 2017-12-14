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

The issue occurs in the [`channel_spin`][3] thread. The cause seems to
be a [spinlock bug][5] (which may have a [fix][6]).

In the captured logs (`0.29.4.txt`), the main process is `25626`, and during
the period of 100% CPU usage we can pin down the exact `pthread` using all
the CPU:

```
$ ps auxw -L
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}  25626 25626  0.3    9  0.3 816352 58944 pts/2    Sl+  20:30   0:12 .../bin/python no-messages-too/script.py
${USER}  25626 25631  0.1    9  0.3 816352 58944 pts/2    Sl+  20:30   0:06 .../bin/python no-messages-too/script.py
${USER}  25626 25632  0.0    9  0.3 816352 58944 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626 25639  0.1    9  0.3 816352 58944 pts/2    Sl+  20:30   0:05 .../bin/python no-messages-too/script.py
${USER}  25626 25657  0.0    9  0.3 816352 58944 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626 25658  0.0    9  0.3 816352 58944 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626 25659  0.0    9  0.3 816352 58944 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626  3610 97.6    9  0.3 816352 58944 pts/2    Rl+  21:34   0:58 .../bin/python no-messages-too/script.py
${USER}  25626  3611  0.0    9  0.3 816352 58944 pts/2    Sl+  21:34   0:00 .../bin/python no-messages-too/script.py
...
$
$
$
$ ps auxw -L
USER       PID   LWP %CPU NLWP %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...
${USER}  25626 25626  0.2    9  0.3 816352 53276 pts/2    Sl+  20:30   0:13 .../bin/python no-messages-too/script.py
${USER}  25626 25631  0.1    9  0.3 816352 53276 pts/2    Sl+  20:30   0:06 .../bin/python no-messages-too/script.py
${USER}  25626 25632  0.0    9  0.3 816352 53276 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626 25639  0.1    9  0.3 816352 53276 pts/2    Sl+  20:30   0:05 .../bin/python no-messages-too/script.py
${USER}  25626 25657  0.0    9  0.3 816352 53276 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626 25658  0.0    9  0.3 816352 53276 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626 25659  0.0    9  0.3 816352 53276 pts/2    Sl+  20:30   0:00 .../bin/python no-messages-too/script.py
${USER}  25626  5033 99.1    9  0.3 816352 53276 pts/2    Rl+  21:46   0:35 .../bin/python no-messages-too/script.py
${USER}  25626  5034  0.0    9  0.3 816352 53276 pts/2    Sl+  21:46   0:00 .../bin/python no-messages-too/script.py
...
```

Checking the logs, each of these corresponds to one of the threads we have
named `Thread-gRPC-StopChannelSpin` (see `thread_names.py` for how we intercept
calls to `threading.Thread` to give custom names):

```
----------------------------------------
timeLevel=03852345:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin+43
Created TID: 3610
----------------------------------------
timeLevel=04576010:DEBUG
logger=root
threadName=Thread-gRPC-StopChannelSpin+51
Created TID: 5033
----------------------------------------
```

Attaching `strace` to these threads we see:

```
$ [sudo] strace -p 3610
...
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 182) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513229731, 320975350}) = 0
write(2, "D1213 21:35:31.320975350    3610"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513229731, 321022943}) = 0
write(2, "D1213 21:35:31.321022943    3610"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {595607, 440475523}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 182) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513229731, 321105382}) = 0
write(2, "D1213 21:35:31.321105382    3610"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513229731, 321137959}) = 0
write(2, "D1213 21:35:31.321137959    3610"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {595607, 440590009}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 182) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513229731, 321219667}) = 0
write(2, "D1213 21:35:31.321219667    3610"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513229731, 321264922}) = 0
write(2, "D1213 21:35:31.321264922    3610"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {595607, 440743565}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 182) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513229731, 321359132}) = 0
write(2, "D1213 21:35:31.321359132    3610"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513229731, 321391637}) = 0
write(2, "D1213 21:35:31.321391637    3610"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {595607, 440846074}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 182) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513229731, 321475654}) = 0
write(2, "D1213 21:35:31.321475654    3610"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513229731, 321509018}) = 0
write(2, "D1213 21:35:31.321509018    3610"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {595607, 440962645}) = 0
...
$
$
$
$ [sudo] strace -p 5033
...
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 190) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513230431, 254451018}) = 0
write(2, "D1213 21:47:11.254451018    5033"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513230431, 254488163}) = 0
write(2, "D1213 21:47:11.254488163    5033"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {596307, 373944159}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 190) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513230431, 254563047}) = 0
write(2, "D1213 21:47:11.254563047    5033"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513230431, 254597548}) = 0
write(2, "D1213 21:47:11.254597548    5033"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {596307, 374077123}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 190) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513230431, 254708226}) = 0
write(2, "D1213 21:47:11.254708226    5033"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513230431, 254742499}) = 0
write(2, "D1213 21:47:11.254742499    5033"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {596307, 374197185}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=0}, {fd=9, events=POLLIN}], 3, 190) = 1 ([{fd=7, revents=POLLHUP}])
clock_gettime(CLOCK_REALTIME, {1513230431, 254828449}) = 0
write(2, "D1213 21:47:11.254828449    5033"..., 78) = 78
clock_gettime(CLOCK_REALTIME, {1513230431, 254868180}) = 0
write(2, "D1213 21:47:11.254868180    5033"..., 96) = 96
clock_gettime(CLOCK_MONOTONIC, {596307, 374335746}) = 0
...
```

By comparison, attached `strace` to a "spin worker" **before** CPU
thrashing begins is much different and much less frequent:

```
$ [sudo] strace -p 659
...
poll([{fd=6, events=POLLIN}, {fd=7, events=POLLIN}], 2, 200) = 0 (Timeout)
clock_gettime(CLOCK_REALTIME, {1513228764, 700198592}) = 0
write(2, "D1213 21:19:24.700198592    1058"..., 78) = 78
clock_gettime(CLOCK_MONOTONIC, {594640, 819839551}) = 0
clock_gettime(CLOCK_REALTIME, {1513228764, 700493169}) = 0
write(2, "I1213 21:19:24.700493169    1058"..., 100) = 100
clock_gettime(CLOCK_REALTIME, {1513228764, 700656910}) = 0
clock_gettime(CLOCK_REALTIME, {1513228764, 700721928}) = 0
write(2, "I1213 21:19:24.700721928    1058"..., 199) = 199
clock_gettime(CLOCK_REALTIME, {1513228764, 700846757}) = 0
clock_gettime(CLOCK_MONOTONIC, {594640, 820321137}) = 0
clock_gettime(CLOCK_MONOTONIC, {594640, 820375072}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=POLLIN}], 2, 200) = 0 (Timeout)
clock_gettime(CLOCK_REALTIME, {1513228764, 901367968}) = 0
write(2, "D1213 21:19:24.901367968    1058"..., 78) = 78
clock_gettime(CLOCK_MONOTONIC, {594641, 21010129}) = 0
clock_gettime(CLOCK_REALTIME, {1513228764, 901659978}) = 0
write(2, "I1213 21:19:24.901659978    1058"..., 100) = 100
futex(0x8f7824, FUTEX_WAIT_BITSET_PRIVATE|FUTEX_CLOCK_REALTIME, 3707, {1513228764, 906769000}, ffffffff) = -1 EAGAIN (Resource temporarily unavailable)
futex(0x8f77e0, FUTEX_WAKE_PRIVATE, 1)  = 0
futex(0x8f7824, FUTEX_WAKE_OP_PRIVATE, 1, 1, 0x8f7820, {FUTEX_OP_SET, 0, FUTEX_OP_CMP_GT, 1}) = 1
clock_gettime(CLOCK_REALTIME, {1513228764, 901972843}) = 0
clock_gettime(CLOCK_REALTIME, {1513228764, 902035229}) = 0
write(2, "I1213 21:19:24.902035229    1058"..., 199) = 199
clock_gettime(CLOCK_REALTIME, {1513228764, 902155033}) = 0
clock_gettime(CLOCK_MONOTONIC, {594641, 21626288}) = 0
clock_gettime(CLOCK_MONOTONIC, {594641, 21678834}) = 0
poll([{fd=6, events=POLLIN}, {fd=7, events=POLLIN}], 2, 200) = 0 (Timeout)
clock_gettime(CLOCK_REALTIME, {1513228765, 102717770}) = 0
write(2, "D1213 21:19:25.102717770    1058"..., 78) = 78
futex(0x7f7fba9b9770, FUTEX_WAKE_PRIVATE, 1) = 1
clock_gettime(CLOCK_MONOTONIC, {594641, 222389240}) = 0
clock_gettime(CLOCK_REALTIME, {1513228765, 103026105}) = 0
write(2, "I1213 21:19:25.103026105    1058"..., 100) = 100
clock_gettime(CLOCK_REALTIME, {1513228765, 103148225}) = 0
clock_gettime(CLOCK_REALTIME, {1513228765, 103206113}) = 0
write(2, "I1213 21:19:25.103206113    1058"..., 199) = 199
clock_gettime(CLOCK_REALTIME, {1513228765, 103316735}) = 0
clock_gettime(CLOCK_MONOTONIC, {594641, 222783434}) = 0
clock_gettime(CLOCK_MONOTONIC, {594641, 222831870}) = 0
...
```

In the healthy `pthread` (`659`), the three poll operations timeout at

- `1513228764.700198592`
- `1513228764.901367968` (+201.2ms)
- `1513228765.102717770` (+201.3ms)

i.e. they obey the `200ms` timeout that is set. In one of the unhealthy
`pthread`-s (`5033`), the four poll operations timeout at

- `1513230431.254451018`
- `1513230431.254563047` (+112.0&#956;s)
- `1513230431.254708226` (+145.2&#956;s)
- `1513230431.254828449` (+120.2&#956;s)

i.e. they come nowhere near the `190ms` timeout that is set. In the other
unhealthy `pthread` (`3610`), the five operations timeout in a similar
fashion:

- `1513229731.320975350`
- `1513229731.321105382` (+130.0&#956;s)
- `1513229731.321219667` (+114.3&#956;s)
- `1513229731.321359132` (+139.5&#956;s)
- `1513229731.321475654` (+116.5&#956;s)

which is nowhere near the `182ms` timeout that is set.

### Miscellaneous Notes

There are still three unknown `pthread`-s that are alive throughout
the process (likely created by [`gpr_thd_new`][4]). There are also
two unknown `pthread`-s that only show up during cleanup (i.e. after all
of the Pub / Sub code has shut down).

The `channel_spin() ...` messages when the CPU usage spikes to 100% don't
seem to be different than those messages before.

CPU Usage spikes to 100%:
- `1h 1m 16.808s` (0.4%, `Thread-gRPC-StopChannelSpin+40`)
- `1h 1m 21.820s` (45.5%, `Thread-gRPC-StopChannelSpin+41`)
- `1h 1m 26.831s` (100.2%, `Thread-gRPC-StopChannelSpin+41`)
- ...
- `1h 3m 17.074s` (100.0%, `Thread-gRPC-StopChannelSpin+42`)

Every single `Thread-gRPC-StopChannelSpin` goes through four iterations
before exiting except for the very last one (there are 54 such threads).
Each of them also takes somewhere between 60 and 120 seconds, which
matches the expected amount of time before gRPC throws an `UNAVAILABLE`
due to inactivity.

Every single `Event(...)` instance logged has `type=2` which is the
`GRPC_OP_COMPLETE` enum.

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

### Debunked Hypothesis 2

It was previously believed that the CPU thrashing was brought on by a
"bad" refresh (i.e. by `google-auth` rather than by `grpcio`). This is
because this cause **almost always** begins to start thrashing after
approximately 65 minutes, which corresponds to the 60 minute refresh
window for an access token.

This has been "debunked" by reports from users of thrashing occurring after
10 minutes as well as a reproducible case (recently checked in) where after
`44m 54.613s`, the `Thread-gRPC-StopChannelSpin+31` thread ran a credentials
check via `Thread-gRPC-PluginGetMetadata+33` and then started thrashing.

However, it is still true that **exactly** one of the spin workers actually
checks the credentials metadata

```
$ cat 0.29.4.txt | grep 'Spin.* -> .*Plugin'
Thread-gRPC-StopChannelSpin+41 -> Thread-gRPC-PluginGetMetadata+43
```

and that this is always the spin worker
that kicks off the thrashing (i.e. where CPU usage goes to 100%).

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4563
[2]: https://rafalcieslak.wordpress.com/2013/04/02/dynamic-linker-tricks-using-ld_preload-to-cheat-inject-features-and-investigate-programs/
[3]: https://github.com/grpc/grpc/blob/v1.8.0/src/python/grpcio/grpc/_channel.py#L710-L711
[4]: https://github.com/grpc/grpc/blob/v1.8.0/src/core/lib/support/thd_posix.cc#L58
[5]: https://github.com/grpc/grpc/issues/9688
[6]: https://github.com/grpc/grpc/pull/13665
