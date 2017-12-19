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

import os
import time

import six

from google.cloud.pubsub_v1.publisher.batch import thread

import thread_names
import utils


CURR_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_PUBLISH_SUCCEED = 500
NUM_PUBLISH_FAIL = 2000
ONLY_DATA = b'Issue 4575'
HEARTBEAT_ADDENDUM = """
Heartbeats=%d
Publish Futures Done=%d, Failed=%d, Total=%d"""
BATCH_COMMIT = """\
_commit(%r):
caller = %s
topic = %s
status = %s
len(messages) = %d
len(futures) = %d"""


class CustomBatch(thread.Batch):

    LOGGER = None

    def _commit(self, caller='commit'):
        self.LOGGER.debug(
            BATCH_COMMIT, self, caller, self._topic, self._status,
            len(self._messages), len(self._futures))
        return super(CustomBatch, self)._commit()

    def monitor(self):
        # NOTE: This is **mostly** copied from the `0.30.0` source,
        #       but is done so that the logging statement can be
        #       added for `0.29.4` and so that we can pass a custom
        #       caller to ``_commit``.
        time.sleep(self._settings.max_latency)
        self.LOGGER.debug('Monitor is waking up')
        return self._commit(caller='monitor')


def publish_sync(publisher, topic_path, num_publish, logger):
    futures = []
    for index in six.moves.xrange(num_publish):
        index_str = '{:d}'.format(index)
        future = publisher.publish(
            topic_path,
            ONLY_DATA,
            index=index_str,
        )
        futures.append(future)

    logger.info('Finished creating %d publish futures', num_publish)

    return futures


class HeartbeatHelper(utils.HeartbeatHelper):

    def __init__(self, futures):
        # List[.publisher.futures.Future]: futures
        self.futures = futures
        self.num_heartbeats = 0
        self.template = HEARTBEAT_ADDENDUM

    @property
    def done_info(self):
        done_count = 0
        fail_count = 0
        for future in self.futures:
            if future._exception is not future._SENTINEL:
                fail_count += 1
            elif future._result is not future._SENTINEL:
                done_count += 1

        return done_count, fail_count, len(self.futures)

    def increment_done(self, future, done_count):
        self.num_heartbeats += 1
        return done_count

    @property
    def extra_args(self):
        return (self.num_heartbeats,) + self.done_info


class NotFuture(object):

    def done(self):
        return None

    def running(self):
        return None


def main():
    # Do set-up.
    logger = utils.setup_logging(CURR_DIR)
    CustomBatch.LOGGER = logger
    thread_names.monkey_patch()

    # Get clients and resource paths.
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    client_info = utils.get_client_info(
        topic_name, 's-unused', batch_class=CustomBatch)
    publisher, topic_path, _, _ = client_info

    # Create a topic.
    publisher.create_topic(topic_path)

    # Set off sync job to publish some messages (won't fail).
    futures_succeed = publish_sync(
        publisher, topic_path, NUM_PUBLISH_SUCCEED, logger)

    # The publisher is non-blocking, so we watch it from the main thread.
    helper_succeed = HeartbeatHelper(futures_succeed)
    sub_future = NotFuture()
    utils.heartbeats_block(
        logger, sub_future, max_time=10, helper=helper_succeed)

    # Set off sync job to publish some messages (will fail, at least
    # in `0.29.4`).
    futures_fail = publish_sync(
        publisher, topic_path, NUM_PUBLISH_FAIL, logger)

    # The publisher is non-blocking, so we watch it from the main thread.
    helper_fail = HeartbeatHelper(futures_fail)
    utils.heartbeats_block(
        logger, sub_future, max_time=20, helper=helper_fail)

    # Do clean-up.
    publisher.delete_topic(topic_path)
    thread_names.save_tree(CURR_DIR, logger)
    thread_names.restore()
    utils.restore()


if __name__ == '__main__':
    main()
