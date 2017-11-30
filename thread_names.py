# Copyright 2017 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collections
import os
import threading

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber import policy
import grpc._channel
import grpc._common
import networkx
import networkx.drawing.nx_pydot

import utils


ORIGINAL_THREAD = threading.Thread
ORIGINAL_CLEANUP_THREAD_CONSTRUCTOR = grpc._common.CleanupThread.__init__
PLUGIN_GET_METADATA_REPR = (
    '<cyfunction plugin_get_metadata.<locals>.async_callback at 0x')
CHANNEL_SPIN_REPR = (
    '<function _run_channel_spin_thread.<locals>.channel_spin at 0x')
CONSUME_REQUEST_REPR = (
    '<function _consume_request_iterator.<locals>.'
    'consume_request_iterator at 0x')
THREAD_PARENTS = []
THREAD_NAMES = []


def update_thread_kwargs(args, kwargs):
    if 'name' in kwargs:
        return

    if 'target' not in kwargs:
        raise KeyError(
            'Thread has no name or target', args, kwargs)

    target = kwargs['target']

    # Expected case 1: Spawned in ``grpc._channel._spawn_delivery()``.
    if target is grpc._channel._deliver:
        kwargs['name'] = 'Thread-gRPC-SpawnDelivery'
        return

    # Expected case 2: Spawned in ``grpc._channel._subscribe()``.
    if target is grpc._channel._poll_connectivity:
        kwargs['name'] = 'Thread-gRPC-SubscribeMoot'
        return

    # Expected case 3: Spawned in ``plugin_get_metadata()`` in the Cython
    # file ``grpc/_cython/_cygrpc/credentials.pyx.pxi``.
    target_repr = repr(target)
    if target_repr.startswith(PLUGIN_GET_METADATA_REPR):
        kwargs['name'] = 'Thread-gRPC-PluginGetMetadata'
        return

    # Expected case 4: Spawned in ``grpc._channel._run_channel_spin_thread()``.
    if target_repr.startswith(CHANNEL_SPIN_REPR):
        kwargs['name'] = 'Thread-gRPC-StopChannelSpin'
        return

    # Expected case 5: Spawned in
    # ``grpc._channel._consume_request_iterator()``.
    if target_repr.startswith(CONSUME_REQUEST_REPR):
        kwargs['name'] = 'Thread-gRPC-ConsumeRequestIterator'
        return

    if utils.PUBSUB_VERSION == '0.29.1':
        func = getattr(target, '__func__', None)
        # Expected case 6: Spawned in ``policy.thread.Policy.open()``, though
        # takes into account our override.
        if func is utils.Policy.maintain_leases:
            kwargs['name'] = 'Thread-LeaseMaintenance'
            return

        # Expected case 7: Spawned in ``batch.thread.Batch`` constructor.
        if func is pubsub_v1.publisher.batch.thread.Batch.monitor:
            kwargs['name'] = 'Thread-MonitorBatchPublisher'
            return

    raise TypeError(
        'Unexpected target', args, kwargs)


def check_thread_name(kwargs):
    name = kwargs['name']
    with threading.Lock():
        while name in THREAD_NAMES:
            name += '+'
        THREAD_NAMES.append(name)
        THREAD_PARENTS.append(threading.current_thread().name)
        kwargs['name'] = name


def named_thread(*args, **kwargs):
    update_thread_kwargs(args, kwargs)
    check_thread_name(kwargs)
    return ORIGINAL_THREAD(*args, **kwargs)


def named_cleanup_thread_constructor(self, behavior, *args, **kwargs):
    update_thread_kwargs(args, kwargs)
    check_thread_name(kwargs)
    ORIGINAL_THREAD.__init__(self, *args, **kwargs)
    self._behavior = behavior


def monkey_patch():
    threading.Thread = named_thread
    grpc._common.CleanupThread.__init__ = named_cleanup_thread_constructor


def restore():
    threading.Thread = ORIGINAL_THREAD
    grpc._common.CleanupThread.__init__ = ORIGINAL_CLEANUP_THREAD_CONSTRUCTOR


def get_names_remap(thread_names):
    """Do a remapping, where e.g. 'foobar+++' becomes 'foobar3'

    .. note::

        This assumes ``THREAD_NAMES`` is "final" so we don't need to
        lock before access.
    """
    prefixes = collections.Counter()
    for name in thread_names:
        stripped = name.rstrip('+')
        prefixes[stripped] += 1

    names_map = {'MainThread': 'MainThread'}
    for name in thread_names:
        stripped = name.rstrip('+')
        if prefixes[stripped] > 1:
            count = len(name) - len(stripped)
            to_add = '{}{}'.format(stripped, count)
        else:
            assert stripped == name
            to_add = name

        if to_add.startswith('Thread-'):
            to_add = to_add[len('Thread-'):]
        names_map[name] = to_add

    return names_map


def save_tree(directory):
    filename = os.path.join(
        directory,
        '{}.svg'.format(utils.PUBSUB_VERSION),
    )
    assert len(THREAD_NAMES) == len(THREAD_PARENTS)

    # Pass copy of thread names to avoid edit-during-read.
    names_map = get_names_remap(THREAD_NAMES[::])

    graph = networkx.DiGraph()
    for parent, name in zip(THREAD_PARENTS, THREAD_NAMES):
        graph.add_edge(names_map[parent], names_map[name])

    dot = networkx.drawing.nx_pydot.to_pydot(graph)
    with open(filename, 'wb') as file_obj:
        file_obj.write(dot.create_svg())
