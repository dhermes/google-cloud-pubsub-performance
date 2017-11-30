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
	@echo '   make run            Run script'
	@echo '   make venv-0.29.2    Create a virtual environment with'
	@echo '                       google-cloud-pubsub==0.29.2'
	@echo '   make clean          Clean generated files'
	@echo ''

venv-0.29.2:
	python -m virtualenv venv-0.29.2
	venv-0.29.2/bin/pip install \
	  'google-cloud-pubsub==0.29.2' \
	  'pydot==1.2.3' \
	  'networkx==2.0'

run: venv-0.29.2
	venv-0.29.2/bin/python script.py

clean:
	rm -fr venv-0.29.2/

.PHONY: help run clean
