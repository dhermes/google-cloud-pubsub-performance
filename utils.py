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
from google.cloud.pubsub_v1.subscriber import policy
from google.cloud import pubsub_v1


SCOPE = 'https://www.googleapis.com/auth/pubsub'
LOG_FORMAT = """\
timeLevel=%(relativeCreated)08d:%(levelname)s
logger=%(name)s
threadName=%(threadName)s
%(message)s
----------------------------------------"""
HEARTBEAT_TEMPLATE = """\
Heartbeat:
running=%s
done=%s
active threads (%d) =
%s
exception=%r"""
MAX_TIME = 300
DONE_HEARTBEATS = 4


def setup_root_logger():
    # NOTE: Must set the logging level on the "root" logger since
    #       the orchestration across threads is funky (I still do
    #       not **fully** understand it).
    logging.getLogger().setLevel(logging.DEBUG)
    logging.basicConfig(format=LOG_FORMAT)


def heartbeat(logger, future, done_count):
    is_running = future.running()
    is_done = future.done()
    if is_done:
        done_count += 1
        exception = future.exception()
    else:
        exception = None

    thread_count = threading.active_count()
    parts = ['  - ' + thread.name for thread in threading.enumerate()]
    assert thread_count == len(parts)
    pretty_names = '\n'.join(parts)

    logger.info(
        HEARTBEAT_TEMPLATE, is_running, is_done,
        thread_count, pretty_names, exception)

    return done_count


def heartbeats_block(logger, future):
    deadline = time.time() + MAX_TIME
    done_count = 0
    while time.time() < deadline and done_count < DONE_HEARTBEATS:
        done_count = heartbeat(logger, future, done_count)
        time.sleep(5)

    # If we exited due to the deadline, do one more heartbeat.
    if done_count < DONE_HEARTBEATS:
        heartbeat(logger, future, done_count)


def make_lease_deterministic():
    policy.base.random = NotRandom(3.0)


def get_client_info(topic_name, subscription_name):
    credentials, project = google.auth.default(scopes=(SCOPE,))

    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    topic_path = publisher.topic_path(project, topic_name)

    subscriber = pubsub_v1.SubscriberClient(
        policy_class=Policy, credentials=credentials)
    subscription_path = subscriber.subscription_path(
        project, subscription_name)

    return publisher, topic_path, subscriber, subscription_path


class NotRandom(object):

    def __init__(self, result):
        self.result = result

    def uniform(self, a, b):
        return self.result


class AckCallback(object):

    def __init__(self, logger):
        self.logger = logger

    def __call__(self, message):
        self.logger.info(' Received: %s', message.data.decode('utf-8'))
        message.ack()


class Policy(policy.thread.Policy):

    def on_exception(self, exception):
        policy.thread._LOGGER.debug('on_exception(%r)', exception)
        return super(Policy, self).on_exception(exception)
