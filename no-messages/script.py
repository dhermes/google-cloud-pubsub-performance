# Copyright 2017 Google Inc. All rights reserved.
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
import os
import time

import thread_names
import utils


LOGGER = logging.getLogger('no-messages-repro')
CURR_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # Do set-up.
    utils.setup_root_logger()
    thread_names.monkey_patch()
    utils.make_lease_deterministic()

    # Get clients and resource paths.
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    subscription_name = 's-repro-{}'.format(int(1000 * time.time()))
    client_info = utils.get_client_info(topic_name, subscription_name)
    publisher, topic_path, subscriber, subscription_path = client_info

    # Create a topic, though we won't push messages to it.
    publisher.create_topic(topic_path)

    # Subscribe to the topic, even though it won't publish any messages.
    subscriber.create_subscription(subscription_path, topic_path)
    LOGGER.info('Listening for messages on %s', subscription_path)
    subscription = subscriber.subscribe(subscription_path)
    sub_future = subscription.open(utils.AckCallback(LOGGER))

    # The subscriber is non-blocking, so we must keep the main thread from
    # exiting to allow it to process messages in the background.
    utils.heartbeats_block(LOGGER, sub_future)

    # Do clean-up.
    publisher.delete_topic(topic_path)
    subscriber.delete_subscription(subscription_path)
    thread_names.save_tree(CURR_DIR)
    thread_names.restore()


if __name__ == '__main__':
    main()
