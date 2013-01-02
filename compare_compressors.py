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
from importlib import import_module
import locale
import optparse
import sys

import harfile

locale.setlocale(locale.LC_ALL, 'en_US')

class CompressionTester(object):
  """
  This is the thing.
  """
  msg_types = ['req', 'res']
  
  def __init__(self):
    self.output = sys.stdout.write
    self.warned = {'http1_gzip': True}  # procs with no decompress support
    self.lname = 0  # longest processor name
    self.options, self.args = self.parse_options()
    self.codec_processors = self.get_compressors()
    if self.options.tsv:
      self.run_tsv(self.options.tsv)
    else:
      self.run_text()

      
  def run_text(self):
    messages = []
    for filename in self.args:
      har_requests, har_responses = harfile.read_har_file(filename)
      both = zip(har_requests, har_responses)
      for req, res in both:
        messages.append(('req', req, req[':host']))
        messages.append(('res', res, req[':host']))
    self.ttls = self.process_messages(messages)
    for msg_type in self.msg_types:
      self.print_results(self.ttls.get(msg_type, {}), msg_type, True)


  def run_tsv(self, message_type):
    requests = []
    responses = []
    for filename in self.args:
      har_requests, har_responses = harfile.read_har_file(filename)
      requests.extend(har_requests)
      responses.extend(har_responses)
    both = zip(requests, responses)
    count = 0
    for request, response in both:
      count += 1
      if message_type == 'req':
        results = self.process_message(request, 'req', request[':host'])
      elif message_type == 'res':
        results = self.process_message(response, 'res', request[':host'])
      else:
        sys.stderr.write("Unknown message type; must be 'req' or 'res'.\n")
        sys.exit(1)
      if count == 1:
        codecs = results.keys()
        codecs.sort()
        titles = [codec for codec in codecs if codec[0] != "_"]
        self.output("num\t" + "\t".join(titles) + "\n")
      self.tsv_results(count, [results])
      
    
  def process_messages(self, messages):
    "Let's do this thing."
    if len(messages) == 0:
      sys.stderr.write("Nothing to process.\n")
      return {}
    
    ttls = dict([(msg_type, defaultdict(lambda:{
      'size': 0,
      'maxr': 0,
      'minr': 1e20,
      'ratio_list': [],
    })) for msg_type in self.msg_types])
    
    for (message_type, message, host) in messages:
      results = self.process_message(message, message_type, host)
      for name, result in results.items():
        target = ttls[message_type][name]
        target['size'] += result['size']
        target['maxr'] = max(target['maxr'], result['ratio'])
        target['minr'] = min(target['minr'], result['ratio'])
        target['ratio_list'].append(result['ratio'])
      ttls[message_type]['_num'] = len(messages)
    
    for message_type in self.msg_types:
      baseline_ratio = ttls[message_type][self.options.baseline]['size']
      for name, result in ttls[message_type].items():
        if name[0] == "_":
          continue
        result['ratio'] = 1.0 * result['size'] / baseline_ratio
        result['std'] = self.meanstdv(result['ratio_list'])[1]

    return ttls

  
  def process_message(self, message, message_type, host):
    """
    message is a HTTP header dictionary in the format described in
    compression.BaseProcessor.
    
    message_type is 'req' or 'res'.
    
    host is the host header of the associated request.
    
    Returns a dictionary of processor names mapped to their results.
    """
    procs = [
      (name, proc[self.msg_types.index(message_type)]) for name, proc in \
       self.codec_processors.items()
    ]
    results = {}
    for name, processor in procs:
      compressed = processor.compress(message, host)
      if self.options.verbose > 2:
        a = unicode(compressed, 'utf-8', 'replace').encode('utf-8', 'replace')
        self.output("\n# %s\n%s\n\n" % (name, a)) 
      decompressed = None
      try:
        decompressed = processor.decompress(compressed)
      except NotImplementedError:
        if name not in self.warned.keys():
          sys.stderr.write("WARNING: %s decompression not checked.\n" % name)
          self.warned[name] = True
      if decompressed:
        compare_result = self.compare_headers(message, decompressed)
        if compare_result:
          sys.stderr.write('*** COMPRESSION ERROR in %s.\n' % name)
          if self.options.verbose >= 1:
            self.output(compare_result + "\n\n")
      
      results[name] = {
        'compressed': compressed,
        'decompressed': decompressed,
        'size': len(compressed)
      }
    if self.options.baseline in results.keys():
      baseline_size = results[self.options.baseline]['size']
      if baseline_size > 0:
        for name, result in results.items():
          result['ratio'] = 1.0 * result['size'] / baseline_size
    if self.options.verbose >= 2 and not self.options.tsv:
      self.print_results(results, message_type)
    return results

  
  def print_results(self, results, message_type, stats=False):
    """
    Output a summary of the results. Expects results to be the dictionary
    format described in compression.BaseProcessor.
    """
    
    if stats:
      self.output("%i %s messages processed\n" %
        (results['_num'], message_type))
    
    codecs = results.keys()
    codecs.sort()
    
    lines = []
    for name in codecs:
      if name[0] == "_":
        continue
      ratio = results[name].get('ratio', 0)
      compressed_size = results[name].get('size', 0)
      pretty_size = locale.format("%13d", compressed_size, grouping=True)
      if stats:
        minr = results[name].get('minr', 0)
        maxr = results[name].get('maxr', 0)
        std = results[name]['std']
        lines.append(
          (message_type, name, pretty_size, ratio, minr, maxr, std)
        )
      else:
        lines.append((message_type, name, pretty_size, ratio))
    
    if stats:
      self.output(
        '%%%ds        compressed | ratio min   max   std\n' % self.lname % ''
      )
      fmt = '%%s %%%ds %%s | %%2.2f  %%2.2f  %%2.2f  %%2.2f\n' % self.lname
    else:
      self.output('%%%ds        compressed | ratio\n' % self.lname % '')
      fmt = '%%s %%%ds %%s | %%2.2f\n' % self.lname
    for line in sorted(lines):
      self.output(fmt % line)

    self.output("\n")

    if self.options.verbose > 1 and not stats:
      self.output("-" * 80 + "\n")
        


  def tsv_results(self, num, results_list):
    """
    Output TSV; takes a record number and a list of results objects.
    """
    items = [num]
    for results in results_list:
      codecs = results.keys()
      codecs.sort()
      for name in codecs:
        if name[0] == "_":
          continue
        items.append(results[name].get('size', 0))
    self.output("%s\n" % "\t".join([str(item) for item in items]))
      
  
  def get_compressors(self):
    """
    Get a hash of codec names to processors.
    """
    codec_processors = {}
    for codec in self.options.codec:
      if "=" in codec:
        module_name, param_str = codec.split("=", 1)
        if param_str[0] == param_str[-1] == '"':
          param_str = param_str[1:-1]
        params = [param.strip() for param in param_str.split(',')]
      else:
        module_name = codec
        params = []
      if len(module_name) > self.lname:
        self.lname = len(module_name)
      module = import_module("compressor.%s" % module_name)
      codec_processors[module_name] = ( # same order as self.msg_types
        module.Processor(self.options, True, params),
        module.Processor(self.options, False, params)
      )
    return codec_processors

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
                  dest='codec',
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
                  action="store",
                  dest="tsv",
                  help="output in TSV. Requires an argument for the "
                  "message type; 'req' or 'res'.",
                  default=False)
    return optp.parse_args()

  
  @staticmethod
  def compare_headers(a_hdr, b_hdr):
    """
    Compares two dicts of headers, and returns a message denoting any
    differences. It ignores ordering differences in cookies, but tests that
    all the content does exist in both.
    If nothing is different, it returns an empty string.
    """
    output = []
    for d_hdr in [a_hdr, b_hdr]:
      if 'cookie' in d_hdr.keys():
        splitvals = d_hdr['cookie'].split(';')
        d_hdr['cookie'] = \
          '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
    for (key, val) in a_hdr.iteritems():
      if not key in b_hdr:
        output.append('\tkey: %s present in only one (A)' % key)
        continue
      if val.strip() != b_hdr[key].strip():
        output.append('\tkey: %s has mismatched values:' % key)
        output.append('\t  a -> %s' % val)
        output.append('\t  b -> %s' % b_hdr[key])
      del b_hdr[key]
    for key in b_hdr.keys():
        output.append('\tkey: %s present in only one (B)' % key)
    return '\n'.join(output)


  @staticmethod
  def meanstdv(members):
    """
    Calculate mean and standard deviation of data x[]:
        mean = {\sum_i x_i \over n}
        std = sqrt(\sum_i (x_i - mean)^2 \over n-1)
    """
    from math import sqrt
    num, mean, std = len(members), 0, 0
    for item in members:
      mean = mean + item
    mean = mean / float(num)
    for item in members:
      std = std + (item - mean)**2
    std = sqrt(std / float(num - 1))
    return mean, std


if __name__ == "__main__":
  CompressionTester()
