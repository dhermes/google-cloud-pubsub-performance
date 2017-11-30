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
import threading
import time

import google.auth
import six

from google.cloud import pubsub_v1

# Should be next to this file.
import thread_names
import utils


LOGGER = logging.getLogger('not-found-repro')
MAX_TIME = 300


def info(published, data):
    data = data.decode('utf-8')
    if published:
        msg = 'Published: {}'.format(data)
    else:
        msg = ' Received: {}'.format(data)
    LOGGER.info(msg)


def ack_callback(message):
    info(False, message.data)
    message.ack()


def get_topic_path(project, publisher):
    topic_name = 't-repro-{}'.format(int(1000 * time.time()))
    return publisher.topic_path(project, topic_name)


def publish(count, interval, publisher, topic_path):
    for index in six.moves.range(count):
        data = u'Wooooo! The claaaaaw! (index={})'.format(index)
        data = data.encode('utf-8')
        publisher.publish(
            topic_path,
            data,
        )
        info(True, data)
        time.sleep(interval)


def main():
    utils.setup_root_logger()
    thread_names.monkey_patch()
    utils.make_lease_deterministic()

    credentials, project = google.auth.default(scopes=(utils.SCOPE,))
    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    topic_path = get_topic_path(project, publisher)
    subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
    subscription_path = subscriber.subscription_path(project, 's-not-exist')

    # Create a topic.
    publisher.create_topic(topic_path)

    # Subscribe to the topic. This must happen before the messages
    # are published.
    subscription = subscriber.subscribe(subscription_path)

    # Set off async job to publish some messages.
    thread = threading.Thread(
        target=publish,
        args=(5, 3, publisher, topic_path),
        name='Thread-ReproPublish',
    )
    thread.start()

    # Actually open the subscription and hold it open.
    sub_future = subscription.open(ack_callback)

    # The subscriber is non-blocking, so we must keep the main thread from
    # exiting to allow it to process messages in the background.
    msg = 'Listening for messages on {}'.format(subscription_path)
    LOGGER.info(msg)

    deadline = time.time() + MAX_TIME
    done_count = 0
    while time.time() < deadline:
        done_count = utils.heartbeat(LOGGER, sub_future, done_count)
        if done_count > 3:
            break
        time.sleep(5)

    thread_names.save_tree('not-found-0.29.2.svg')

    # Do clean-up.
    publisher.delete_topic(topic_path)

    thread_names.restore()


if __name__ == '__main__':
    main()
