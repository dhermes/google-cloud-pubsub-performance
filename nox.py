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


GRPC = 'grpcio >= 1.8.2'
GRPC_OLD = 'grpcio == 1.7.3'
GRPC_NO_BINARY = object()
GRPC_CUSTOM = os.path.abspath(
    'grpcio-1.7.4.dev1-cp36-cp36m-manylinux1_x86_64.whl')
PINNED_DEPS = (
    GRPC,
    'pydot == 1.2.3',
)
LOCAL = 'local'
CUSTOM = 'custom'


def _run(directory, session, version, *extra_deps):
    session.interpreter = 'python3.6'
    all_deps = PINNED_DEPS + extra_deps

    if version == LOCAL:
        # NOTE: This assumes, but does not check, that google-cloud-python
        #       is cloned and the desired branch is checked out.
        path = os.path.join('google-cloud-python', 'pubsub')
        session.install(path)
    elif version == CUSTOM:
        all_deps = tuple(dep for dep in all_deps if dep != GRPC)
        all_deps += (GRPC_CUSTOM,)
        session.install('google-cloud-pubsub == 0.29.4')
    else:
        pubsub_dep = 'google-cloud-pubsub == {}'.format(version)
        session.install(pubsub_dep)

    # Remove ``grpcio`` duplicates.
    if GRPC_OLD in all_deps:
        all_deps = tuple(dep for dep in all_deps if dep != GRPC)

    # Special handling for ``GRPC_NO_BINARY`` sentinel.
    if GRPC_NO_BINARY in all_deps:
        all_deps = tuple(dep for dep in all_deps
                         if dep not in (GRPC, GRPC_NO_BINARY))
        no_binary = True
    else:
        no_binary = False

    # NOTE: We install pinned dependencies **after** ``google-cloud-pubsub``
    #       since some of them may override dependencies of
    #       ``google-cloud-pubsub``.
    session.install(*all_deps)

    if no_binary:
        # NOTE: I have no idea why I must include ``grpcio`` twice in this
        #       command but it fails silently without.
        session.run(
            'pip', 'install', GRPC,
            '--ignore-installed', '--no-binary', 'grpcio')

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
@nox.parametrize('version', ('0.29.4', CUSTOM, '0.30.1'))
def no_messages_too(session, version):
    extra_deps = ('psutil', 'boltons')
    if version == '0.29.4':
        extra_deps += (GRPC_OLD,)
    if version == '0.30.1':
        extra_deps += (GRPC_NO_BINARY,)
    _run('no-messages-too', session, version, *extra_deps)


@nox.session
@nox.parametrize('version', ('0.29.0', '0.29.1', '0.29.2'))
def not_found(session, version):
    _run('not-found', session, version)


@nox.session
@nox.parametrize('version', ('0.29.4', '0.30.0'))
def publish_many(session, version):
    _run('publish-many', session, version)
