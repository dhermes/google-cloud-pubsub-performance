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
import six

import grpc_patches


SCOPES = ('https://www.googleapis.com/auth/pubsub',)
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
LOGGER_BASE = logging.getLogger(
    'google.cloud.pubsub_v1.subscriber.policy.base')
LOGGER_THREAD = logging.getLogger(
    'google.cloud.pubsub_v1.subscriber.policy.thread')


def setup_logging(directory, spin_also=False):
    grpc_patches.patch(spin_also)
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


class HeartbeatHelper(object):

    def __init__(self):
        self.template = ''
        self.extra_args = ()

    @staticmethod
    def _base_inc(future, done_count):
        if future.done():
            done_count += 1
        return done_count

    def increment_done(self, future, done_count):
        done_count = self._base_inc(future, done_count)

        if PUBSUB.version() in ('0.29.0', '0.29.1'):
            if done_count < DONE_HEARTBEATS:
                return done_count
            # We don't allow an exit while the consumer is active.
            if active(future._policy._consumer):
                return done_count - 1
            else:
                return done_count
        else:
            return done_count


def heartbeat(logger, future, done_count, helper):
    is_running = future.running()
    is_done = future.done()
    if is_done:
        exception = future.exception()
    else:
        exception = None
    done_count = helper.increment_done(future, done_count)

    thread_count = threading.active_count()
    parts = ['  - ' + thread.name for thread in threading.enumerate()]
    assert thread_count == len(parts)
    pretty_names = '\n'.join(parts)

    template = HEARTBEAT_TEMPLATE + helper.template
    args = (
        template,
        is_running,
        is_done,
        thread_count,
        pretty_names,
        exception,
    )
    args += helper.extra_args
    logger.info(*args)

    return done_count


def active(consumer):
    if PUBSUB.version() in ('0.29.0', '0.29.1', '0.29.2'):
        return consumer.active
    else:
        return not consumer.stopped.is_set()


def heartbeats_block(
        logger, future, max_time=MAX_TIME, helper=HeartbeatHelper()):
    deadline = time.time() + max_time
    done_count = 0
    while time.time() < deadline and done_count < DONE_HEARTBEATS:
        done_count = heartbeat(logger, future, done_count, helper)
        time.sleep(5)

    # If we exited due to the deadline, do one more heartbeat.
    if done_count < DONE_HEARTBEATS:
        heartbeat(logger, future, done_count, helper)


def make_lease_deterministic(random_mod=None):
    if random_mod is None:
        random_mod = NotRandom(3.0)
    policy.base.random = random_mod


def get_client_info(
        topic_name, subscription_name, credentials=None,
        policy_class=None, batch_class=None):
    if credentials is None:
        credentials, project = google.auth.default(scopes=SCOPES)
    else:
        _, project = google.auth.default()

    publisher_kwargs = {'credentials': credentials}
    if batch_class is not None:
        publisher_kwargs['batch_class'] = batch_class
    publisher = pubsub_v1.PublisherClient(**publisher_kwargs)
    topic_path = publisher.topic_path(project, topic_name)

    if policy_class is None:
        policy_class = Policy
    subscriber = pubsub_v1.SubscriberClient(
        policy_class=policy_class, credentials=credentials)
    subscription_path = subscriber.subscription_path(
        project, subscription_name)

    return publisher, topic_path, subscriber, subscription_path


def get_stack(num_frames):
    # NOTE: Import at **runtime** since ``boltons`` is an optional
    #       dependency.
    from boltons import tbutils

    parts = []
    for level in six.moves.xrange(num_frames + 2, 2, -1):
        try:
            callpoint = tbutils.Callpoint.from_current(level)
            parts.append(callpoint.tb_frame_str())
        except ValueError as exc:
            assert exc.args == ('call stack is not deep enough',)

    stack_text = ''.join(parts)
    return StdErrLogger.sanitize(stack_text)


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
        return message


class Policy(policy.thread.Policy):

    def on_exception(self, exception):
        LOGGER_THREAD.debug('on_exception(%r)', exception)
        return super(Policy, self).on_exception(exception)

    def maintain_leases(self):
        result = super(Policy, self).maintain_leases()
        if PUBSUB.version() in ('0.29.0', '0.29.1'):
            LOGGER_BASE.debug(
                'Consumer inactive, ending lease maintenance.')
        return result


class FlowControlPolicy(Policy):

    POLICY_INFO_TEMPLATE = (
        '  num_messages = {:d}\n'
        '  max_messages = {}\n'
        '  num_bytes = {:d}\n'
        '  max_bytes = {}')

    def _get_policy_info(self):
        return self.POLICY_INFO_TEMPLATE.format(
            len(self.managed_ack_ids),
            self.flow_control.max_messages,
            self._bytes,
            self.flow_control.max_bytes,
        )

    def close(self):
        LOGGER_THREAD.debug('Closing policy %r.', self)
        return super(FlowControlPolicy, self).close()

    def open(self, callback):
        LOGGER_THREAD.debug('Opening policy %r with %r.', self, callback)
        return super(FlowControlPolicy, self).open(callback)

    @property
    def _load(self):
        policy_info = self._get_policy_info()
        result = super(FlowControlPolicy, self)._load
        LOGGER_BASE.debug(
            'Policy._load: %s\ninfo =\n%s', result, policy_info)
        return result


class StdErrLogger(object):

    HOME = os.path.expanduser('~')
    SITE_PACKAGES = distutils.sysconfig.get_python_lib()

    @classmethod
    def sanitize(cls, value):
        # NOTE: Must first replace ${SITE_PACKAGES} since it **may** contain
        #       ${HOME} and ${HERE}.
        value = value.replace(cls.SITE_PACKAGES, '${SITE_PACKAGES}')
        # NOTE: Must first replace ${HERE} since it **may** contain ${HOME}.
        value = value.replace(HERE, '${HERE}')
        return value.replace(cls.HOME, '${HOME}')

    def write(self, error_msg):
        if error_msg == '\n':
            return

        error_msg = self.sanitize(error_msg)
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
