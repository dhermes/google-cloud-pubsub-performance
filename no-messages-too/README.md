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
"heartbeat", this mapping is used to verify that the active `pthreads`
according to the operating system are the same as the active threads
according to Python.

When running this, there are three `pthread`-s unknown to Python, and
these currently seem to be the most likely culprit (though it will have
to wait for the current run to finish before the hypothesis can be
checked). It seems these threads are created by the gRPC C-core and are
not known to Python.

It's likely we can hook into this by [using `LD_PRELOAD`][2] to replace
`gpr_thd_new` at the ABI level:

```
$ git clone https://github.com/grpc/grpc/ --depth=1
$ cd grpc/
$ git log -1 --pretty=%H
69e8ab400dadb2843e9a1927cf579bdec94d729b
$ git grep -n gpr_thd_new -- include/ src/
include/grpc/support/thd.h:49:GPRAPI int gpr_thd_new(gpr_thd_id* t, const char* thd_name,
src/core/lib/iomgr/ev_poll_posix.cc:1362:  GPR_ASSERT(gpr_thd_new(&t_id, "grpc_poller", &run_poll, pargs, &opt));
src/core/lib/iomgr/executor.cc:107:    gpr_thd_new(&g_thread_state[0].id, "grpc_executor", executor_thread,
src/core/lib/iomgr/executor.cc:264:        gpr_thd_new(&g_thread_state[cur_thread_count].id, "gpr_executor",
src/core/lib/iomgr/timer_manager.cc:90:  // The call to gpr_thd_new() has to be under the same lock used by
src/core/lib/iomgr/timer_manager.cc:92:  // (internally by gpr_thd_new) and read there. Otherwise it's possible for ct
src/core/lib/iomgr/timer_manager.cc:96:  gpr_thd_new(&ct->t, "grpc_global_timer", timer_thread, ct, &opt);
src/core/lib/profiling/basic_timers.cc:206:  GPR_ASSERT(gpr_thd_new(&g_writing_thread, "timer_output_thread",
src/core/lib/support/thd_posix.cc:50:/* Body of every thread started via gpr_thd_new. */
src/core/lib/support/thd_posix.cc:72:int gpr_thd_new(gpr_thd_id* t, const char* thd_name,
src/core/lib/support/thd_windows.cc:55:/* Body of every thread started via gpr_thd_new. */
src/core/lib/support/thd_windows.cc:68:int gpr_thd_new(gpr_thd_id* t, const char* thd_name,
src/ruby/ext/grpc/rb_grpc_imports.generated.c:266:gpr_thd_new_type gpr_thd_new_import;
src/ruby/ext/grpc/rb_grpc_imports.generated.c:538:  gpr_thd_new_import = (gpr_thd_new_type) GetProcAddress(library, "gpr_thd_new");
src/ruby/ext/grpc/rb_grpc_imports.generated.h:771:typedef int(*gpr_thd_new_type)(gpr_thd_id* t, const char* thd_name, void (*thd_body)(void* arg), void* arg, const gpr_thd_options* options);
src/ruby/ext/grpc/rb_grpc_imports.generated.h:772:extern gpr_thd_new_type gpr_thd_new_import;
src/ruby/ext/grpc/rb_grpc_imports.generated.h:773:#define gpr_thd_new gpr_thd_new_import
$
$
$ strings .../grpc/_cython/cygrpc.cpython-36m-x86_64-linux-gnu.so \
> | grep gpr_thd_new
gpr_thd_new(&t_id, &run_poll, pargs, &opt)
gpr_thd_new
gpr_thd_new
```

or just build gRPC from source with extra logging.

[1]: https://github.com/GoogleCloudPlatform/google-cloud-python/issues/4563
[2]: https://rafalcieslak.wordpress.com/2013/04/02/dynamic-linker-tricks-using-ld_preload-to-cheat-inject-features-and-investigate-programs/
