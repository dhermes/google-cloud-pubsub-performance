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
    'grpcio==1.7.0',
    'pydot==1.2.3',
    'networkx==2.0',
)
VERSIONS = (
    '0.29.1',
    '0.29.2',
)


def _run(directory, session, version):
    session.interpreter = 'python3.6'
    session.install(*PINNED_DEPS)
    pubsub_dep = 'google-cloud-pubsub=={}'.format(version)
    session.install(pubsub_dep)

    # Add current directory to PYTHONPATH so that ``thread_names.py`` and
    # ``utils.py`` can be imported.
    env = {'PYTHONPATH': '.'}
    script_name = os.path.join(directory, 'script.py')
    session.run('python', script_name, env=env)


@nox.session
@nox.parametrize('version', VERSIONS)
def not_found(session, version):
    _run('not-found', session, version)


@nox.session
@nox.parametrize('version', VERSIONS)
def no_messages(session, version):
    _run('no-messages', session, version)
