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


import distutils.sysconfig
import logging
import os
import subprocess
import sys
import threading
import time

import google.auth
from google.cloud.pubsub_v1.subscriber import policy
from google.cloud import pubsub_v1
import pkg_resources


SCOPE = 'https://www.googleapis.com/auth/pubsub'
HERE = os.path.dirname(os.path.abspath(__file__))
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
ORIGINAL_STDERR = sys.stderr


def setup_logging(directory):
    # NOTE: Must set the logging level on the "root" logger since
    #       the orchestration across threads is funky (I still do
    #       not **fully** understand it).
    logging.getLogger().setLevel(logging.DEBUG)
    filename = os.path.join(
        directory,
        '{}.txt'.format(PUBSUB.version()),
    )
    logging.basicConfig(
        format=LOG_FORMAT,
        filename=filename,
        filemode='w',
    )
    # Redirect ``stderr`` to logging.
    sys.stderr = StdErrLogger()

    # Make the "current" logger.
    logger_name = '{}-repro'.format(os.path.basename(directory))
    return logging.getLogger(logger_name)


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


def done_count_extra(future, done_count):
    if PUBSUB.version() == '0.29.1':
        if done_count < DONE_HEARTBEATS:
            return done_count
        # We don't allow an exit while the consumer is active.
        if future._policy._consumer.active:
            return done_count - 1
        else:
            return done_count
    else:
        return done_count


def heartbeats_block(logger, future):
    deadline = time.time() + MAX_TIME
    done_count = 0
    while time.time() < deadline and done_count < DONE_HEARTBEATS:
        done_count = heartbeat(logger, future, done_count)
        done_count = done_count_extra(future, done_count)
        time.sleep(5)

    # If we exited due to the deadline, do one more heartbeat.
    if done_count < DONE_HEARTBEATS:
        heartbeat(logger, future, done_count)


def make_lease_deterministic():
    policy.base.random = NotRandom(3.0)


def get_client_info(topic_name, subscription_name, policy_class=None):
    credentials, project = google.auth.default(scopes=(SCOPE,))

    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    topic_path = publisher.topic_path(project, topic_name)

    if policy_class is None:
        policy_class = Policy
    subscriber = pubsub_v1.SubscriberClient(
        policy_class=policy_class, credentials=credentials)
    subscription_path = subscriber.subscription_path(
        project, subscription_name)

    return publisher, topic_path, subscriber, subscription_path


def restore():
    sys.stderr = ORIGINAL_STDERR


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

    def maintain_leases(self):
        result = super(Policy, self).maintain_leases()
        policy.base._LOGGER.debug(
            'Consumer inactive, ending lease maintenance.')
        return result


class StdErrLogger(object):

    HOME = os.path.expanduser('~')
    SITE_PACKAGES = distutils.sysconfig.get_python_lib()

    def write(self, error_msg):
        if error_msg == '\n':
            return

        # NOTE: Must first replace ${SITE_PACKAGES} since it **may** contain
        #       ${HOME} and ${HERE}.
        error_msg = error_msg.replace(self.SITE_PACKAGES, '${SITE_PACKAGES}')
        # NOTE: Must first replace ${HERE} since it **may** contain ${HOME}.
        error_msg = error_msg.replace(HERE, '${HERE}')
        error_msg = error_msg.replace(self.HOME, '${HOME}')
        logging.error(error_msg)


class PUBSUB(object):

    _version = None

    @staticmethod
    def _compute_version():
        distribution = pkg_resources.get_distribution('google-cloud-pubsub')
        full_version = distribution.version
        base_version, last_segment = full_version.rsplit('.', 1)
        if not last_segment.startswith('dev'):
            return full_version

        gcp_dir = os.path.join(HERE, 'google-cloud-python')
        branch_name = subprocess.check_output(
            ('git', 'rev-parse', '--abbrev-ref', 'HEAD'), cwd=gcp_dir)
        branch_name = branch_name.strip().decode('utf-8')
        commit_hash = subprocess.check_output(
            ('git', 'log', '-1', '--pretty=%H'), cwd=gcp_dir)
        commit_hash = commit_hash.strip().decode('utf-8')
        return '{}.{}.{}'.format(base_version, branch_name, commit_hash)

    @classmethod
    def version(cls):
        with threading.Lock():
            if cls._version is None:
                cls._version = cls._compute_version()

            return cls._version
