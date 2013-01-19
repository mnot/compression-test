#!/usr/bin/env python

from collections import defaultdict
from copy import copy
from importlib import import_module
import os
import sys

# pylint: disable=W0311


class Processors(object):
  """
  Contains the candidate processors that we want to compare.
  """
  module_dir = "compressor"

  def __init__(self, options, msg_types, output):
    self.options = options
    self.msg_types = msg_types
    self.output = output
    self.warned = {'http1_gzip': True}  # procs with no decompress support
    self.processors = self.get_processors(options.processor_names)

  def get_processors(self, processor_names):
    """
    Get a hash of codec names to processors.
    """
    procs = defaultdict(list)
    for name in processor_names:
      if "=" in name:
        module_name, param_str = name.split("=", 1)
        if param_str[0] == param_str[-1] == '"':
          param_str = param_str[1:-1]
        params = [param.strip() for param in param_str.split(',')]
      else:
        module_name = name
        params = []
      module = import_module("%s.%s" % (self.module_dir, module_name))
      procs['req'].append(module.Processor(self.options, True, params))
      procs['res'].append(module.Processor(self.options, False, params))
    return procs

  def process_stream(self, stream):
    """
    Process the messages in the stream with all processors, and record
    results.
    """
    for (hdrs, host) in stream.messages:
      results = self.process_message(hdrs, stream.msg_type, host)
      for proc_name, resu in results.items():
        if proc_name == self.options.baseline:
          ratio = 1.0
        else:
          ratio = 1.0 * resu['size'] / results[self.options.baseline]['size']
        stream.record_result(proc_name, resu['size'], ratio, resu['time'])

  def process_message(self, hdrs, msg_type, host):
    """
    message is a HTTP header dictionary in the format described in
    compression.BaseProcessor.

    msg_type is 'req' or 'res'.

    host is the host header of the associated request.

    Returns a dictionary of processor names mapped to their results.
    """
    results = {}
    for processor in self.processors[msg_type]:
      start_time = sum(os.times()[:2])
      compressed = processor.compress(copy(hdrs), host)
      results[processor.name] = {
        'size': len(compressed),
        'time': sum(os.times()[:2]) - start_time
      }
      if self.options.verbose > 3:
        txt = unicode(compressed, 'utf-8', 'replace') \
              .encode('utf-8', 'replace')
        self.output("# %s\n%s" % (processor.name, txt))
        if txt[-1] != "\n":
          self.output("\n\n")
      try:
        decompressed = processor.decompress(compressed)
      except NotImplementedError:
        if processor.name not in self.warned.keys():
          sys.stderr.write(
            "  WARNING: %s decompression not checked.\n" % processor.name
          )
          self.warned[processor.name] = True
        continue
      compare_result = self.compare_headers(copy(hdrs), decompressed)
      if compare_result:
        self.output('  - mismatch in %s' % processor.name)
        if self.options.verbose > 1:
          self.output(': ' + compare_result + "\n")
        self.output("\n")
    return results

  @staticmethod
  def compare_headers(a_hdr, b_hdr):
    """
    Compares two dicts of headers, and returns a message denoting any
    differences. It ignores:
     - ordering differences in cookies
     - connection headers
     - HTTP version
     - HTTP status phrase
    If nothing is different, it returns an empty string. If it is, it
    returns a string explaining what is different.
    """
    output = []
    for d_hdr in [a_hdr, b_hdr]:
      if 'cookie' in d_hdr.keys():
        splitvals = d_hdr['cookie'].split(';')
        d_hdr['cookie'] = \
          '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
    conn = [v.strip().lower() for v in a_hdr.get("connection", "").split(",")]
    for (key, val) in a_hdr.iteritems():
      if key in "connection" or conn:
        pass
      elif key in [':version', ':status-text']:
        pass
      elif not key in b_hdr:
        output.append('%s present in only one (A)' % key)
        continue
      elif val.strip() != b_hdr[key].strip():
        output.append('%s has mismatched values' % key)
        output.append('    a -> %s' % val)
        output.append('    b -> %s' % b_hdr[key])
      if b_hdr.has_key(key):
        del b_hdr[key]
    for key in b_hdr.keys():
        output.append('%s present in only one (B)' % key)
    return '\n'.join(output)
