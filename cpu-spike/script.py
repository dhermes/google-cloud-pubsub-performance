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

import six

import thread_names
import utils


CURR_DIR = os.path.dirname(os.path.abspath(__file__))


def publish_target(message_counts, intervals, publisher, topic_path, logger):
    index = 0
    intervals = iter(intervals)
    for message_count in message_counts:
        interval = next(intervals)
        for _ in six.moves.range(message_count):
            data = u'Wooooo! The claaaaaw! (index={})'.format(index)
            publisher.publish(
                topic_path,
                data.encode('utf-8'),
            )
            logger.info('Published: %s', data)
            index += 1
        time.sleep(interval)


def publish_async(publisher, topic_path, logger):
    message_counts = (18, 5, 1, 7)
    intervals = (3.0, 10.0, 5.0, 3.0)
    thread = threading.Thread(
        target=publish_target,
        args=(message_counts, intervals, publisher, topic_path, logger),
        name='Thread-ReproPublish',
    )
    thread.start()


def main():
    # Do set-up.
    logger = utils.setup_logging(CURR_DIR)
    thread_names.monkey_patch()
    utils.make_lease_deterministic()

    # Get clients and resource paths.
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    subscription_name = 's-repro-{}'.format(int(1000 * time.time()))
    client_info = utils.get_client_info(topic_name, subscription_name)
    publisher, topic_path, subscriber, subscription_path = client_info

    # Create a topic.
    publisher.create_topic(topic_path)

    # Subscribe to the topic. We do this before the messages are
    # published so that we'll receive them as they come in.
    subscriber.create_subscription(subscription_path, topic_path)
    logger.info('Listening for messages on %s', subscription_path)
    subscription = subscriber.subscribe(subscription_path)
    sub_future = subscription.open(utils.AckCallback(logger))

    # Set off async job to publish some messages.
    publish_async(publisher, topic_path, logger)

    # The subscriber is non-blocking, so we must keep the main thread from
    # exiting to allow it to process messages in the background.
    utils.heartbeats_block(logger, sub_future)

    # Do clean-up.
    publisher.delete_topic(topic_path)
    subscriber.delete_subscription(subscription_path)
    thread_names.save_tree(CURR_DIR, logger)
    thread_names.restore()
    utils.restore()


if __name__ == '__main__':
    main()
