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
    Fut. is Policy's fut?=%s
 Message ack rate (msg/s)=%.5f
 Total messages processed=%d
Unique messages processed=%d"""
TEARDOWN_SUMMARY_TEMPLATE = """\
Consumer Request Queue Size=%d
  Policy Request Queue Size=%d
  Policy Num. Ack On Resume=%d
Policy Num. Managed Ack IDs=%d"""


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


class HeartbeatHelper(utils.HeartbeatHelper):

    def __init__(self, callback, policy):
        self.callback = callback
        self.policy = policy
        self.template = HEARTBEAT_ADDENDUM
        self.last_four = (None, None, None, None)

    @property
    def extra_args(self):
        active_future = future is self.policy._future
        rate, messages_processed, uniques = self.callback.info
        return active_future, rate, messages_processed, uniques

    @property
    def done(self):
        uniques = self.callback.uniques
        prev_last_four = self.last_four
        self.last_four = prev_last_four[1:] + (uniques,)

        return (
            uniques == NUM_PUBLISH_BATCHES * BATCH_SIZE or
            prev_last_four == (uniques, uniques, uniques, uniques)
        )

    def _base_inc(self, unused_future, done_count):
        # **ONLY** increment the done count if ``self.done`` is true.
        if self.done:
            done_count += 1
        return done_count


def teardown_summary(policy, logger):
    consumer = policy._consumer
    logger.info(
        TEARDOWN_SUMMARY_TEMPLATE, consumer._request_queue.qsize(),
        policy._request_queue.qsize(), len(policy._ack_on_resume),
        len(policy._managed_ack_ids))


def main():
    # Do set-up.
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
    helper = HeartbeatHelper(callback, subscription)
    utils.heartbeats_block(logger, sub_future, max_time=500, helper=helper)

    # Do clean-up.
    subscription.close()
    subscription._executor.shutdown()  # Idempotent, but needed for 0.29.2.
    publisher.delete_topic(topic_path)
    subscriber.delete_subscription(subscription_path)
    teardown_summary(subscription, logger)
    thread_names.save_tree(CURR_DIR, logger)
    thread_names.restore()
    utils.restore()


if __name__ == '__main__':
    main()
