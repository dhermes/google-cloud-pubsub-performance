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

from google.cloud.pubsub_v1.subscriber.policy import base


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


def make_lease_deterministic():
    base.random = NotRandom(3.0)


class NotRandom(object):

    def __init__(self, result):
        self.result = result

    def uniform(self, a, b):
        return self.result
