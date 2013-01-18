#!/usr/bin/env python

"""
compression_test.py

Tests various HTTP header compression algorithms, to compare them.
"""

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=W0311

from collections import defaultdict
import locale
import optparse

from publicsuffix import PublicSuffixList

from harfile import read_har_file
from processors import Processors
from stream import Stream


class CompressionTester(object):
  """
  This is the thing.
  """
  msg_types = ['req', 'res']

  def __init__(self, output):
    self.options, self.args = self.parse_options()
    self.output = output
    self.tsv_out = defaultdict(list)  # accumulator for TSV output
    self.psl = PublicSuffixList()
    self.processors = Processors(self.options, self.msg_types, output)
    self.run()

  def run(self):
    "Let's do this thing."
    streams = []
    for filename in self.args:
      har_requests, har_responses = read_har_file(filename)
      messages = zip(har_requests, har_responses)
      streams.extend(self.streamify_messages(messages))
    for stream in streams:
      stream.print_header(self.output)
      self.processors.process_stream(stream)
      if self.options.verbose > 0:
        stream.print_summary(self.output, self.options.baseline)
    for msg_type in self.msg_types:
      ttl_stream = sum([s for s in streams if s.msg_type == msg_type])
      ttl_stream.name = "TOTAL"
      ttl_stream.print_header(self.output)
      ttl_stream.print_summary(self.output, self.options.baseline)
    if self.options.tsv:
      out = {}
      for msg_type in self.msg_types:
        out[msg_type] = [
          open("%s%s" % (self.options.prefix, "%s.tsv" % msg_type), 'w'), 
          0
        ]
        streams[0].print_tsv_header(out[msg_type][0].write)
      for stream in streams:
        fh, tsv_count = out[stream.msg_type]
        out[stream.msg_type][1] = stream.print_tsv(fh.write, tsv_count)
      for fh, count in out.values():
        fh.close()

  def streamify_messages(self, messages):
    """
    Given a list of messages (each a req, res tuple), return a list of
    Stream objects.
    """
    reqs = defaultdict(list)
    ress = defaultdict(list)
    suffixes = []
    for req, res in messages:
      host = req[':host']
      suffix = self.psl.get_public_suffix(host.split(":", 1)[0])
      if suffix not in suffixes:
        suffixes.append(suffix)
      reqs[suffix].append((req, host))
      ress[suffix].append((res, host))

    streams = []
    for suffix in suffixes:
      streams.append(Stream(suffix, reqs[suffix], 'req'))
      streams.append(Stream(suffix, ress[suffix], 'res'))
    return streams

  @staticmethod
  def parse_options():
    "Parse command-line options and return (options, args)."
    optp = optparse.OptionParser()
    optp.add_option('-v', '--verbose',
                  type='int',
                  dest='verbose',
                  help='set verbosity, 1-5 (default: %default)',
                  default=0,
                  metavar='VERBOSITY')
    optp.add_option('-c', '--codec',
                  action='append',
                  dest='processor_names',
                  help='compression modules to test, potentially with '
                  'parameters. '
                  'e.g. -c spdy3 -c fork="abc" '
                  '(default: %default)',
                  default=['http1'])
    optp.add_option('-b', '--baseline',
                  dest='baseline',
                  help='baseline codec to base comparisons upon. '
                  '(default: %default)',
                  default='http1')
    optp.add_option('-t', '--tsv',
                  action="store_true",
                  dest="tsv",
                  help="output TSV.",
                  default=False)
    optp.add_option('--prefix',
                  action="store",
                  dest="prefix",
                  help="Prefix for TSV file output.",
                  default="")
    return optp.parse_args()


if __name__ == "__main__":
  import os
  import sys
  if os.name == "nt":
    locale.setlocale(locale.LC_ALL, 'english-us')
  else:
    locale.setlocale(locale.LC_ALL, 'en_US')
  CompressionTester(sys.stdout.write)
