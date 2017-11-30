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

help:
	@echo 'Makefile for google-cloud-pubsub examples'
	@echo ''
	@echo 'Usage:'
	@echo '   make run-not-found      Run "not found" script'
	@echo '   make run-no-messages    Run "no messages" script'
	@echo '   make venv-0.29.2        Create a virtual environment with'
	@echo '                           google-cloud-pubsub==0.29.2'
	@echo '   make clean              Clean generated files'
	@echo ''

venv-0.29.2:
	python -m virtualenv venv-0.29.2
	venv-0.29.2/bin/pip install \
	  'google-cloud-pubsub==0.29.2' \
	  'grpcio==1.7.0' \
	  'pydot==1.2.3' \
	  'networkx==2.0'

run-not-found: venv-0.29.2
	venv-0.29.2/bin/python not-found.py 2> not-found-0.29.2.txt

run-no-messages: venv-0.29.2
	venv-0.29.2/bin/python no-messages.py 2> no-messages-0.29.2.txt

clean:
	rm -fr \
	  __pycache__/ \
	  venv-0.29.2/

.PHONY: help run-not-found run-no-messages clean
