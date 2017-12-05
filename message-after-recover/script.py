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

import thread_names
import utils


CURR_DIR = os.path.dirname(os.path.abspath(__file__))


class Policy(utils.Policy):

    def __init__(self, *args, **kwargs):
        super(Policy, self).__init__(*args, **kwargs)
        self.recovered = False

    def on_exception(self, exception):
        recover = super(Policy, self).on_exception(exception)
        if recover:
            self.recovered = True
        return recover


def publish_target(policy, interval, publisher, topic_path, logger):
    while not policy.recovered:
        time.sleep(interval)

    data = u'After the policy recovered from failure.'
    publisher.publish(
        topic_path,
        data.encode('utf-8'),
    )
    logger.info('Published: %s', data)

    # After publishing, sleep for 20 seconds and then close the policy.
    time.sleep(20.0)
    policy.close()


def publish_async(policy, publisher, topic_path, logger):
    thread = threading.Thread(
        target=publish_target,
        args=(policy, 10.0, publisher, topic_path, logger),
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
        topic_name, subscription_name, policy_class=Policy)
    publisher, topic_path, subscriber, subscription_path = client_info

    # Create a topic, though we won't push messages to it.
    publisher.create_topic(topic_path)

    # Subscribe to the topic, even though it won't publish any messages.
    subscriber.create_subscription(subscription_path, topic_path)
    logger.info('Listening for messages on %s', subscription_path)
    subscription = subscriber.subscribe(subscription_path)
    sub_future = subscription.open(utils.AckCallback(logger))

    # Set off async job that will publish a single message once the
    # subscriber recovers.
    publish_async(subscription, publisher, topic_path, logger)

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
