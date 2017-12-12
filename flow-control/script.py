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
import random
import threading
import time

from google.cloud.pubsub_v1 import types
import six

import thread_names
import utils


CURR_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_TIME = 80


def publish_target(publisher, consumer, topic_path, logger):
    index = 0
    # Finish 10 seconds early.
    deadline = time.time() + MAX_TIME - 10.0
    while time.time() < deadline:
        if not utils.active(consumer):
            return

        for _ in six.moves.xrange(6):
            data = u'Wooooo! The claaaaaw! (index={})'.format(index)
            publisher.publish(
                topic_path,
                data.encode('utf-8'),
            )
            logger.info('Published: %s', data)
            index += 1

        time.sleep(random.random())


def publish_async(publisher, consumer, topic_path, logger):
    thread = threading.Thread(
        target=publish_target,
        args=(publisher, consumer, topic_path, logger),
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
    client_info = utils.get_client_info(
        topic_name, subscription_name, policy_class=utils.FlowControlPolicy)
    publisher, topic_path, subscriber, subscription_path = client_info

    # Create a topic.
    publisher.create_topic(topic_path)

    # Subscribe to the topic. We do this before the messages are
    # published so that we'll receive them as they come in.
    subscriber.create_subscription(subscription_path, topic_path)
    logger.info('Listening for messages on %s', subscription_path)
    flow_control = types.FlowControl(max_messages=8)
    subscription = subscriber.subscribe(
        subscription_path, flow_control=flow_control)
    sub_future = subscription.open(utils.AckCallback(logger))
    consumer = subscription._consumer

    # Set off async job to publish some messages.
    publish_async(publisher, consumer, topic_path, logger)

    # The subscriber is non-blocking, so we must keep the main thread from
    # exiting to allow it to process messages in the background.
    utils.heartbeats_block(logger, sub_future, max_time=MAX_TIME)

    # Do clean-up.
    subscription.close()
    publisher.delete_topic(topic_path)
    subscriber.delete_subscription(subscription_path)
    thread_names.save_tree(CURR_DIR, logger)
    thread_names.restore()
    utils.restore()


if __name__ == '__main__':
    main()
