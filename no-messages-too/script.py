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

import datetime
import os
import time

import google.auth
import google.auth.transport.grpc as auth_grpc
import grpc
import psutil

import thread_names
import utils


ORIGINAL_PLUGIN = auth_grpc.AuthMetadataPlugin
ORIGINAL_UPDATE_THREAD_KWARGS = thread_names.update_thread_kwargs
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
UNKNOWN = '<name-unknown>'
HEARTBEAT_ADDENDUM = """
psutil info=
%s"""


class AuthMetadataPlugin(ORIGINAL_PLUGIN):

    LOGGER = None
    CLOCK_SKEW = datetime.timedelta(seconds=300)
    TEMPLATE = (
        '_get_authorization_headers()\n'
        '  now          =%s\n'
        '  skewed_expiry=%s\n'
        '  expiry       =%s\n'
        '  valid=%s\n'
        '  stack=\n\n%s')

    def __init__(self, credentials, request):
        # NOTE: We have to hack around the original constructor since
        #       it refers to the ``AuthMetadataPlugin`` name at runtime.
        grpc.AuthMetadataPlugin.__init__(self)
        self._credentials = credentials
        self._request = request

    def _get_authorization_headers(self, context):
        stack_info = utils.get_stack(15)

        expiry = self._credentials.expiry
        if expiry is None:
            now = None
            skewed_expiry = None
            valid = False
        else:
            now = datetime.datetime.utcnow()
            skewed_expiry = expiry - self.CLOCK_SKEW
            valid = now >= skewed_expiry

        self.LOGGER.debug(
            self.TEMPLATE, now, skewed_expiry, expiry, valid, stack_info)

        return ORIGINAL_PLUGIN._get_authorization_headers(self, context)


class HeartbeatHelper(utils.HeartbeatHelper):

    def __init__(self):
        self.num_heartbeats = 0
        self.process = psutil.Process()
        self.template = HEARTBEAT_ADDENDUM

    def increment_done(self, future, done_count):
        self.num_heartbeats += 1
        return super(HeartbeatHelper, self).increment_done(
            future, done_count)

    @property
    def psutil_info(self):
        pid = self.process.pid
        cpu_usage = self.process.cpu_percent()
        children = self.process.children()
        threads = self.process.threads()

        parts = [
            '  Heartbeats={}'.format(self.num_heartbeats),
            '  CPU usage={}%'.format(cpu_usage),
            '  pid={}'.format(pid),
        ]

        parts.append('  child processes ({})'.format(len(children)))
        for child in children:
            parts.append('    pid={}'.format(child.pid))

        parts.append('  owned pthreads ({})'.format(len(threads)))
        with thread_names.TID_LOCK:
            for pthread in threads:
                tid = pthread.id
                name = thread_names.TID_MAP.get(tid, UNKNOWN)
                parts.append('    tid={} ({})'.format(tid, name))

        return '\n'.join(parts)

    @property
    def extra_args(self):
        return self.psutil_info,


class UpdateThreadKwargs(object):

    def __init__(self, logger):
        self.logger = logger

    def __call__(self, args, kwargs):
        result = ORIGINAL_UPDATE_THREAD_KWARGS(args, kwargs)

        if kwargs['name'] == thread_names.PLUGIN_THREAD_NAME:
            stack_info = utils.get_stack(15)
            self.logger.debug(
                'When spawning %s, stack:\n\n%s',
                thread_names.PLUGIN_THREAD_NAME, stack_info)

        return result


def patch_stage1():
    # We can patch this since the **name** is used at **runtime** by
    # ``auth_grpc.secure_authorized_channel``, which is used by:
    # - ``google.cloud._helpers.make_secure_channel``
    # - ``google.api_core.grpc_helpers.create_channel``
    auth_grpc.AuthMetadataPlugin = AuthMetadataPlugin
    thread_names.LogCreationTarget.ADD_LOGGING = True
    thread_names.LogCreationTarget._log_current()


def patch_stage2(logger):
    thread_names.update_thread_kwargs = UpdateThreadKwargs(logger)
    AuthMetadataPlugin.LOGGER = logger


def main():
    # Do set-up.
    patch_stage1()
    logger = utils.setup_logging(CURR_DIR, spin_also=True)
    patch_stage2(logger)
    thread_names.monkey_patch()

    # Get clients and resource paths.
    credentials, _ = google.auth.default(scopes=utils.SCOPES)
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    subscription_name = 's-repro-{}'.format(int(1000 * time.time()))
    client_info = utils.get_client_info(
        topic_name, subscription_name, credentials=credentials)
    publisher, topic_path, subscriber, subscription_path = client_info

    # Create a topic, though we won't push messages to it.
    publisher.create_topic(topic_path)

    # Subscribe to the topic, even though it won't publish any messages.
    subscriber.create_subscription(subscription_path, topic_path)
    logger.info('Listening for messages on %s', subscription_path)
    subscription = subscriber.subscribe(subscription_path)
    sub_future = subscription.open(utils.AckCallback(logger))

    # The subscriber is non-blocking, so we must keep the main thread from
    # exiting to allow it to process messages in the background.
    helper = HeartbeatHelper()
    # Make sure it runs 1h20m.
    utils.heartbeats_block(logger, sub_future, max_time=4800, helper=helper)

    # Do clean-up.
    subscription.close()
    publisher.delete_topic(topic_path)
    subscriber.delete_subscription(subscription_path)
    thread_names.save_tree(CURR_DIR, logger)
    thread_names.restore()
    utils.restore()

    # Do four more heartbeats to see if all the threads are gone.
    for _ in (1, 2, 3, 4):
        utils.heartbeat(logger, sub_future, 0, helper)
        time.sleep(5)


if __name__ == '__main__':
    main()
