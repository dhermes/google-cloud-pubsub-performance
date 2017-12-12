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

from __future__ import print_function

import argparse
import os


CURR_DIR = os.path.dirname(os.path.abspath(__file__))
SEPARATOR = '-' * 40 + '\n'
OUR_SEPARATOR = '=' * 40


def get_args():
    parser = argparse.ArgumentParser(description='Check the logs.')
    parser.add_argument('--filename', required=True)
    parser.add_argument('--show-all', dest='show_all', action='store_true')
    return parser.parse_args()


def get_content(log_message):
    time_level, logger, thread_name, content = log_message.split('\n', 3)
    assert time_level.startswith('timeLevel=')
    assert logger == 'logger=grpc._channel'
    assert thread_name == 'threadName=Thread-gRPC-ConsumeRequestIterator'
    first, content = content.split('\n', 1)
    assert first == 'consume_request_iterator() sent:'
    return content


def main():
    args = get_args()
    log_file = os.path.join(CURR_DIR, args.filename)
    with open(log_file, 'r') as file_obj:
        content = file_obj.read()

    assert content.endswith(SEPARATOR)
    log_messages = content[:-len(SEPARATOR)].split(SEPARATOR)
    grpc_bidi = [message for message in log_messages
                 if 'consume_request_iterator' in message]

    if args.show_all:
        to_print = SEPARATOR.join([''] + grpc_bidi + [''])
        print(to_print, end='')
    else:
        ack_reqs = []
        other_reqs = []
        for message in grpc_bidi:
            if 'ack_ids: ' in message:
                msg_content = get_content(message)
                if msg_content.startswith('ack_ids: '):
                    ack_reqs.append(msg_content)
                else:
                    # NOTE: We intentionally don't add the very long lease
                    #       management requests to ``other_reqs``.
                    count1 = msg_content.count('modify_deadline_seconds: ')
                    count2 = msg_content.count('modify_deadline_ack_ids: ')
                    assert count1 == count2
                    assert count1 > 0
            else:
                other_reqs.append(message)

        print('Non-ack messages:')
        print(OUR_SEPARATOR)
        print(SEPARATOR.join(other_reqs), end='')
        print(OUR_SEPARATOR)
        template = 'Total consume_request_iterator() messages: {}'
        print(template.format(len(grpc_bidi)))
        print('Acks sent: {}'.format(len(ack_reqs)))


if __name__ == '__main__':
    main()
