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

import nox


PINNED_DEPS = (
    'grpcio==1.7.3',
    'pydot==1.2.3',
)
LOCAL = 'local'


def _run(directory, session, version, *extra_deps):
    session.interpreter = 'python3.6'
    if version == LOCAL:
        # NOTE: This assumes, but does not check, that google-cloud-python
        #       is cloned and the desired branch is checked out.
        path = os.path.join('google-cloud-python', 'pubsub')
        session.install(path)
    else:
        pubsub_dep = 'google-cloud-pubsub=={}'.format(version)
        session.install(pubsub_dep)

    # NOTE: We install pinned dependencies **after** ``google-cloud-pubsub``
    #       since some of them may override dependencies of
    #       ``google-cloud-pubsub``.
    all_deps = PINNED_DEPS + extra_deps
    session.install(*all_deps)

    # Add current directory to PYTHONPATH so that ``thread_names.py`` and
    # ``utils.py`` can be imported.
    env = {'PYTHONPATH': '.'}
    script_name = os.path.join(directory, 'script.py')
    session.run('python', script_name, env=env)


@nox.session
@nox.parametrize('version', ('0.29.1', '0.29.2', '0.29.4'))
def cpu_spike(session, version):
    _run('cpu-spike', session, version)


@nox.session
@nox.parametrize('version', ('0.29.2', '0.29.4'))
def flow_control(session, version):
    _run('flow-control', session, version)


@nox.session
@nox.parametrize('version', ('0.29.2', '0.29.4'))
def issue_4238(session, version):
    _run('issue-4238', session, version)


@nox.session
@nox.parametrize('version', ('0.29.2', '0.29.4'))
def message_after_recover(session, version):
    _run('message-after-recover', session, version)


@nox.session
@nox.parametrize('version', ('0.29.0', '0.29.1'))
def no_messages(session, version):
    _run('no-messages', session, version)


@nox.session
@nox.parametrize('version', ('0.29.4',))
def no_messages_too(session, version):
    _run('no-messages-too', session, version, 'psutil')


@nox.session
@nox.parametrize('version', ('0.29.0', '0.29.1', '0.29.2'))
def not_found(session, version):
    _run('not-found', session, version)
