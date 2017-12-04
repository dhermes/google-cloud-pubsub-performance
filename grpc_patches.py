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

import grpc
import grpc._channel
import grpc._common
from grpc._cython import cygrpc


LOGGER = logging.getLogger('grpc._channel')
EMPTY_FLAGS = grpc._channel._EMPTY_FLAGS


def _consume_request_iterator(
        request_iterator, state, call, request_serializer):
    """Consume a request iterator.

    This is borrowed from ``grpcio==1.7.0``.
    """
    event_handler = grpc._channel._event_handler(state, call, None)

    def consume_request_iterator():
        while True:
            try:
                request = next(request_iterator)
            except StopIteration:
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
                                EMPTY_FLAGS,
                            ),
                        )
                        call.start_client_batch(
                            cygrpc.Operations(operations),
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
                                return
                else:
                    return
        with state.condition:
            if state.code is None:
                operations = (
                    cygrpc.operation_send_close_from_client(EMPTY_FLAGS),
                )
                call.start_client_batch(
                    cygrpc.Operations(operations), event_handler)
                state.due.add(cygrpc.OperationType.send_close_from_client)

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


def patch():
    grpc._channel._consume_request_iterator = _consume_request_iterator