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
import threading
import time

import six

# Should be next to this file.
import thread_names
import utils


LOGGER = logging.getLogger('not-found-repro')
CURR_DIR = os.path.dirname(os.path.abspath(__file__))


def publish_target(count, interval, publisher, topic_path):
    for index in six.moves.range(count):
        data = u'Wooooo! The claaaaaw! (index={})'.format(index)
        publisher.publish(
            topic_path,
            data.encode('utf-8'),
        )
        LOGGER.info('Published: %s', data)
        time.sleep(interval)


def publish_async(publisher, topic_path):
    thread = threading.Thread(
        target=publish_target,
        args=(5, 3.0, publisher, topic_path),
        name='Thread-ReproPublish',
    )
    thread.start()


def main():
    # Do set-up.
    utils.setup_root_logger()
    thread_names.monkey_patch()
    utils.make_lease_deterministic()

    # Get clients and resource paths.
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    client_info = utils.get_client_info(topic_name, 's-not-exist')
    publisher, topic_path, subscriber, subscription_path = client_info

    # Create a topic.
    publisher.create_topic(topic_path)

    # Subscribe to the topic. We do this before the messages are
    # published so that we'll receive them as they come in.
    LOGGER.info('Listening for messages on %s', subscription_path)
    subscription = subscriber.subscribe(subscription_path)
    sub_future = subscription.open(utils.AckCallback(LOGGER))

    # Set off async job to publish some messages.
    publish_async(publisher, topic_path)

    # The subscriber is non-blocking, so we must keep the main thread from
    # exiting to allow it to process messages in the background.
    utils.heartbeats_block(LOGGER, sub_future)

    # Do clean-up.
    publisher.delete_topic(topic_path)
    thread_names.save_tree(CURR_DIR)
    thread_names.restore()


if __name__ == '__main__':
    main()