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
import threading
import time

from google.cloud.pubsub_v1 import types
import six

import thread_names
import utils


CURR_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_PUBLISH_BATCHES = 16
# NOTE: This is a workaround for some (currently unknown) issue in
#       the publisher. Observed when batches reach ~1k messages.
BATCH_SIZE = 250
ONLY_DATA = b'Kir Issue 4238'
SLEEP_TIME = 0.5  # 500ms
MAX_MESSAGES = 100
HEARTBEAT_ADDENDUM = """
 Message ack rate (msg/s)=%.5f
 Total messages processed=%d
Unique messages processed=%d"""


def publish_sync(publisher, topic_path, logger):
    index = 0
    for _ in six.moves.xrange(NUM_PUBLISH_BATCHES):
        futures = []
        for _ in six.moves.range(BATCH_SIZE):
            index_str = '{:d}'.format(index)
            future = publisher.publish(
                topic_path,
                ONLY_DATA,
                index=index_str,
            )
            futures.append(future)
            index += 1

        for future in futures:
            future.result()

        logger.info('Finished %d', index)


class TrackingCallback(object):

    def __init__(self, sleep_time, logger):
        self.sleep_time = sleep_time
        self.logger = logger
        self.lock = threading.Lock()
        self.start_time = None
        self.seen = []

    @property
    def messages_processed(self):
        return len(self.seen)

    @property
    def uniques(self):
        return len(set(self.seen))

    def __call__(self, message):
        with self.lock:
            if self.start_time is None:
                self.start_time = time.time()

        time.sleep(self.sleep_time)
        message.ack()
        with self.lock:
            assert message.data == ONLY_DATA
            index = int(message.attributes['index'])
            self.logger.info('Received: %d', index)
            self.seen.append(index)

    @property
    def info(self):
        with self.lock:
            if self.start_time is None:
                rate = 0.0
            else:
                duration = time.time() - self.start_time
                rate = self.messages_processed / duration

            return rate, self.messages_processed, self.uniques


class NotRandom(object):

    def __init__(self, fraction):
        self.fraction = fraction

    def uniform(self, a, b):
        return a + (b - a) * self.fraction


class Heartbeat(object):

    def __init__(self, callback, template):
        self.callback = callback
        self.template = template

    @property
    def done(self):
        return self.callback.uniques == NUM_PUBLISH_BATCHES * BATCH_SIZE

    def __call__(self, logger, future, done_count):
        is_running = future.running()
        is_done = future.done()
        if is_done:
            done_count += 1
            exception = future.exception()
        else:
            if self.done:
                done_count += 1
            exception = None

        thread_count = threading.active_count()
        parts = ['  - ' + thread.name for thread in threading.enumerate()]
        assert thread_count == len(parts)
        pretty_names = '\n'.join(parts)

        rate, messages_processed, uniques = self.callback.info
        logger.info(
            self.template, is_running, is_done,
            thread_count, pretty_names, exception,
            rate, messages_processed, uniques)

        return done_count


def main():
    # Do set-up.
    utils.MAX_TIME = 500  # Make sure it runs until finishing.
    logger = utils.setup_logging(CURR_DIR)
    thread_names.monkey_patch()
    random_mod = NotRandom(0.75)
    utils.make_lease_deterministic(random_mod)

    # Get clients and resource paths.
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    subscription_name = 's-repro-{}'.format(int(1000 * time.time()))
    client_info = utils.get_client_info(
        topic_name, subscription_name, policy_class=utils.FlowControlPolicy)
    publisher, topic_path, subscriber, subscription_path = client_info

    # Create a topic and subscription (subscription must exist when
    # messages are published to topic).
    publisher.create_topic(topic_path)
    subscriber.create_subscription(subscription_path, topic_path)

    # Set off sync job to publish some messages.
    publish_sync(publisher, topic_path, logger)

    # Sleep to let the backend have some time with its thoughts.
    logger.info('Sleeping for 10s after publishing.')
    time.sleep(10.0)

    # Subscribe to the topic. We do this before the messages are
    # published so that we'll receive them as they come in.
    logger.info('Listening for messages on %s', subscription_path)
    subscription = subscriber.subscribe(
        subscription_path,
        flow_control=types.FlowControl(
            max_messages=MAX_MESSAGES,
        )
    )
    callback = TrackingCallback(SLEEP_TIME, logger)
    sub_future = subscription.open(callback)

    # The subscriber is non-blocking, so we must keep the main thread from
    # exiting to allow it to process messages in the background.
    template = utils.HEARTBEAT_TEMPLATE + HEARTBEAT_ADDENDUM
    heartbeat = Heartbeat(callback, template)
    utils.heartbeats_block(logger, sub_future, heartbeat_func=heartbeat)

    # Do clean-up.
    subscription.close()
    publisher.delete_topic(topic_path)
    subscriber.delete_subscription(subscription_path)
    thread_names.save_tree(CURR_DIR, logger)
    thread_names.restore()
    utils.restore()


if __name__ == '__main__':
    main()
