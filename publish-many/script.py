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

import thread_names
import utils


CURR_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_PUBLISH = 2000
ONLY_DATA = b'Issue 4575'
HEARTBEAT_ADDENDUM = """
Heartbeats=%d
Publish Futures Done=%s"""


def publish_sync(publisher, topic_path, logger):
    futures = []
    for index in six.moves.xrange(NUM_PUBLISH):
        index_str = '{:d}'.format(index)
        future = publisher.publish(
            topic_path,
            ONLY_DATA,
            index=index_str,
        )
        futures.append(future)

    logger.info('Finished %d', NUM_PUBLISH)

    return futures


class HeartbeatHelper(utils.HeartbeatHelper):

    def __init__(self, futures):
        # List[.publisher.futures.Future]: futures
        self.futures = futures
        self.num_heartbeats = 0
        self.template = HEARTBEAT_ADDENDUM

    @property
    def done_status(self):
        done_count = sum(future.done() for future in self.futures)
        return '{} / {}'.format(done_count, len(self.futures))

    def increment_done(self, future, done_count):
        self.num_heartbeats += 1
        return done_count

    @property
    def extra_args(self):
        return self.num_heartbeats, self.done_status


class NotFuture(object):

    def done(self):
        return None

    def running(self):
        return None


def main():
    # Do set-up.
    logger = utils.setup_logging(CURR_DIR)
    thread_names.monkey_patch()

    # Get clients and resource paths.
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    client_info = utils.get_client_info(topic_name, 's-unused')
    publisher, topic_path, _, _ = client_info

    # Create a topic.
    publisher.create_topic(topic_path)

    # Set off sync job to publish some messages.
    futures = publish_sync(publisher, topic_path, logger)

    # The publisher is non-blocking, so we watch it from the main thread.
    helper = HeartbeatHelper(futures)
    sub_future = NotFuture()
    utils.heartbeats_block(logger, sub_future, max_time=20, helper=helper)

    # Do clean-up.
    publisher.delete_topic(topic_path)
    thread_names.save_tree(CURR_DIR, logger)
    thread_names.restore()
    utils.restore()


if __name__ == '__main__':
    main()
