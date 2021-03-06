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

import logging
import time

import grpc
import grpc._channel
import grpc._common
from grpc._cython import cygrpc
import pkg_resources


LOGGER = logging.getLogger('grpc._channel')
DONT_EXIT = 'channel_spin() has managed_calls remaining (iteration=%d)\n%r'
DO_EXIT = 'channel_spin() exiting (iteration=%d, duration=%g)'
EVENT_REPR_TEMPLATE = """\
Event(
  type={event.type}
  success={event.success}
  tag={event.tag}
  operation_call={event.operation_call}
  request_call_details={event.request_call_details}
  request_metadata={event.request_metadata}
  batch_operations={event.batch_operations}
  is_new_request={event.is_new_request}
)"""


def _consume_request_iterator(
        request_iterator, state, call, request_serializer):
    """Consume a request iterator.

    This is borrowed from ``grpcio==1.8.2``.
    """
    event_handler = grpc._channel._event_handler(state, call, None)

    def consume_request_iterator():
        while True:
            try:
                request = next(request_iterator)
            except StopIteration:
                LOGGER.debug(
                    'consume_request_iterator() encountered StopIteration')
                break
            except Exception:
                LOGGER.exception('Exception iterating requests!')
                call.cancel()
                grpc._channel._abort(
                    state, grpc.StatusCode.UNKNOWN,
                    'Exception iterating requests!')
                return
            serialized_request = grpc._common.serialize(
                request, request_serializer)
            with state.condition:
                if state.code is None and not state.cancelled:
                    if serialized_request is None:
                        call.cancel()
                        details = 'Exception serializing request!'
                        grpc._channel._abort(
                            state, grpc.StatusCode.INTERNAL, details)
                        return
                    else:
                        operations = (
                            cygrpc.operation_send_message(
                                serialized_request,
                                grpc._channel._EMPTY_FLAGS,
                            ),
                        )
                        call.start_client_batch(
                            make_ops(operations),
                            event_handler,
                        )
                        state.due.add(cygrpc.OperationType.send_message)
                        while True:
                            state.condition.wait()
                            if state.code is None:
                                if cygrpc.OperationType.send_message not in state.due:
                                    LOGGER.debug(
                                        'consume_request_iterator() sent:\n%r',
                                        request)
                                    break
                            else:
                                LOGGER.debug(
                                    'consume_request_iterator() exiting in '
                                    'error (%r) after waiting for '
                                    'send_message()', state.code)
                                return
                else:
                    LOGGER.debug(
                        'consume_request_iterator() exiting in error before '
                        'sending newly consumed request:\n%r', request)
                    return
        with state.condition:
            if state.code is None:
                operations = (
                    cygrpc.operation_send_close_from_client(
                        grpc._channel._EMPTY_FLAGS,
                    ),
                )
                call.start_client_batch(
                    make_ops(operations), event_handler)
                state.due.add(cygrpc.OperationType.send_close_from_client)
            else:
                LOGGER.debug(
                    'consume_request_iterator() exiting in error (%r) after a '
                    'request iterator is exhausted', state.code)

    def stop_consumption_thread(timeout):
        with state.condition:
            if state.code is None:
                call.cancel()
                state.cancelled = True
                grpc._channel._abort(
                    state, grpc.StatusCode.CANCELLED, 'Cancelled!')
                state.condition.notify_all()

    consumption_thread = grpc._common.CleanupThread(
        stop_consumption_thread, target=consume_request_iterator)
    consumption_thread.start()


def event_repr(event):
    # event: grpc._cython.cygrpc.Event
    try:
        return EVENT_REPR_TEMPLATE.format(event=event)
    except:
        return repr(event)


def _run_channel_spin_thread(state):
    """Spin a channel until all managed calls are resolved.

    Used by ``_channel_managed_call_management`` in cases where
    a ``state`` has no ``managed_calls`` attached.

    This is borrowed from ``grpcio==1.8.2``.
    """

    def channel_spin():
        count = 0
        start = time.time()
        while True:
            count += 1
            LOGGER.debug('Polling in channel_spin() (iteration=%d)', count)
            event = state.completion_queue.poll()
            completed_call = event.tag(event)
            LOGGER.debug(
                'channel_spin():\niteration=%d\nevent=%s\ncompleted_call=%r',
                count, event_repr(event), completed_call)
            if completed_call is not None:
                with state.lock:
                    state.managed_calls.remove(completed_call)
                    if not state.managed_calls:
                        state.managed_calls = None
                        duration = time.time() - start
                        LOGGER.debug(DO_EXIT, count, duration)
                        return
                    else:
                        LOGGER.debug(DONT_EXIT, count, state.managed_calls)

    def stop_channel_spin(timeout):
        with state.lock:
            if state.managed_calls is not None:
                LOGGER.debug(
                    'stop_channel_spin() has managed_calls\n%r',
                    state.managed_calls)
                for call in state.managed_calls:
                    call.cancel()
            else:
                LOGGER.debug('stop_channel_spin() has no managed_calls')

    channel_spin_thread = grpc._common.CleanupThread(
        stop_channel_spin, target=channel_spin)
    channel_spin_thread.start()


def patch(spin_also):
    grpc._channel._consume_request_iterator = _consume_request_iterator
    if spin_also:
        grpc._channel._run_channel_spin_thread = _run_channel_spin_thread


try:
    pkg_resources.require('grpcio >= 1.8.2')
    make_ops = lambda operations: operations
except pkg_resources.ResolutionError:
    make_ops = cygrpc.Operations
