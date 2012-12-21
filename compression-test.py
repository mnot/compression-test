#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from importlib import import_module
import locale
import optparse
import re
import sys

import harfile


locale.setlocale(locale.LC_ALL, 'en_US')


def main():

  options, args = parse_options()

  # load .har files
  requests = []
  responses = []
  for filename in args:
    (har_requests, har_responses) = harfile.ReadHarFile(filename)
    requests.extend(har_requests)
    responses.extend(har_responses)

  if len(requests) == 0:
    sys.stderr.write("Nothing to process; exiting.\n")
    sys.exit(1)

  # load indicated codec modules and prepare for their execution
  codec_names = []
  req_accum = {}
  rsp_accum = {}
  request_processors = {}
  response_processors = {}
  codec_processors, longest_module_name = get_codecs(options)

  for module_name, processor in codec_processors.items():
    req_accum[module_name] = [0,0]
    rsp_accum[module_name] = [0,0]

  for i in xrange(len(requests)):
    request = requests[i]
    response = responses[i]
    if options.verbose >= 2:
      print '#' * 80 
      print '    ####### request-path: "%s"' % requests[i][':path'][:80]
    ProcessAndFormat("request", "req",
        longest_module_name,
        [(name, proc[0]) for name, proc in codec_processors.items()],
        request, request,
        req_accum,
        options)
    ProcessAndFormat("response", "rsp",
        longest_module_name,
        [(name, proc[1]) for name, proc in codec_processors.items()],
        request, response,
        rsp_accum,
        options)

  if options.verbose > 2:
    print '#' * 80 
    print '#' * 80 
    print

  baseline_size = 0
  lines = []
  if options.baseline in req_accum:
    baseline_size = req_accum[options.baseline][1]
  for module_name, stats in req_accum.iteritems():
    (compressed_size, uncompressed_size) = stats
    ratio = 0
    if baseline_size > 0:
      ratio = 1.0* compressed_size / baseline_size
    lines.append(('req',
                  module_name,
                  locale.format("%10d", uncompressed_size, grouping=True),
                  locale.format("%10d", compressed_size, grouping=True),
                  ratio) )
  if options.baseline in rsp_accum:
    baseline_size = rsp_accum[options.baseline][1]
  for module_name, stats in rsp_accum.iteritems():
    (compressed_size, uncompressed_size) = stats
    ratio = 0
    if baseline_size > 0:
      ratio = 1.0* compressed_size / baseline_size
    lines.append(('rsp',
                  module_name,
                  locale.format("%10d", uncompressed_size, grouping=True),
                  locale.format("%10d", compressed_size, grouping=True),
                  ratio) )
  print ('\t %% %ds   uncompressed | compressed | ratio' % (
         longest_module_name+10)) % ''
  line_format = '\t%%s %% %ds: %%s | %%s | %%2.2f ' % (
      longest_module_name+10)
  for line in sorted(lines):
    print line_format % line
  print
  

def parse_options():
  "Parse command-line options and return (options, args)."
  op = optparse.OptionParser()
  op.add_option('-n', '--new',
                type='int',
                dest='n',
                help='use the new serialization method',
                default=0)
  op.add_option('-v', '--verbose',
                type='int',
                dest='verbose',
                help='Sets verbosity. At v=1, the opcodes will be printed. '
                'At v=2, so will the headers [default: %default]',
                default=0,
                metavar='VERBOSITY')
  op.add_option('-f', '--force_streamgroup',
                dest='f',
                help='If set, everything will use stream-group 0. '
                '[default: %default]',
                default=0)
  op.add_option('-c', '--codec',
                action='append',
                dest='codec',
                help='If set, the argument will be parsed as a'
                'comma-separated list of compression module names'
                'to use and the parameters to be passed to each. '
                'e.g. -c http1_gzip -c spdy3 -c exec="param1,param2"'
                '[default: %default]',
                default=[])
  op.add_option('-b', '--baseline',
                dest='baseline',
                help='Baseline codec-- all comparitive ratios are based on'
                'this',
                default='http1_gzip')

  return op.parse_args()  

def get_codecs(options):
  "Get a hash of codec names to modules. Also return the longest module name."
  longest_module_name = 0
  codec_processors = {}
  for codec in options.codec:
    if "=" in codec:
      module_name, param_str = codec.split("=", 1)
      if param_str[0] == param_str[-1] == '"':
        param_str = param_str[1:-1]
      params = [param.strip() for param in param_str.split(',')]
    else:
      module_name = codec
      params = []
    if len(module_name) > longest_module_name:
      longest_module_name = len(module_name)
    module = import_module("compression.%s" % module_name)
    codec_processors[module_name] = (
      module.Processor(options, True, params), 
      module.Processor(options, False, params)
    )
  return codec_processors, longest_module_name
    

  

def CompareHeaders(a, b):
  """
  Compares two sets of headers, and returns a message denoting any
  differences. It ignores ordering differences in cookies, but tests that all
  the content does exist in both.
  If nothing is different, it returns an empty string.
  """
  a = dict(a)
  b = dict(b)
  output = []
  if 'cookie' in a:
    splitvals = a['cookie'].split(';')
    a['cookie'] = '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
  if 'cookie' in b:
    splitvals = b['cookie'].split(';')
    b['cookie'] = '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
  for (k,v) in a.iteritems():
    if not k in b:
      output.append('\tkey: %s present in only one (A)' % k)
      continue
    if v != b[k]:
      output.append('\tkey: %s has mismatched values:' % k)
      output.append('\t  -> %s' % v)
      output.append('\t  -> %s' % b[k])
    del b[k]
  for (k, v) in b.iteritems():
      output.append('\tkey: %s present in only one (B)' % k)
  return '\n'.join(output)


def ProcessAndFormat(top_message,
                     frametype_message,
                     protocol_name_field_width,
                     framers,
                     request, test_frame,
                     accumulator,
                     options):
  """
  This uses the various different framing classes to encode/compress,
  potentially report on the results of each, and then accumulates stats on the
  effectiveness of each.

  'top_message' is the message printed at the top of the results, e.g.
  "request foo"

  'frametype_message' denotes the kind of message, e.g. request or response.

  'framers' is a dictionary of protocol_name: framer. It *must* include a
  'spdy4' and 'http1' framer if the function is to do its job properly.

  'request' is the request associated with the test_frame. If the test_frame
  is a request, this would simply be a repetition of that. If the test_frame
  is a response, this would be the request which engendered the response.

  'accumulator' is a dictionary of protocol_name to list-of-ints (of size
  two). this function adds the compressed and uncompressed sizes into the
  dictionary entry corresponding to the protocol_name for each of the framers
  in 'framers'.
  """
  if options.verbose >= 1:
    print '    ######## %s ########' % top_message
  processing_results = []

  baseline_size = None
  for protocol_name, framer in framers:
    result = framer.ProcessFrame(test_frame, request)
    processing_results.append((protocol_name, result))
    if protocol_name == options.baseline:
      baseline_size = len(result['serialized_ops'])

    if options.verbose >= 2 and 'decompressed_interpretable_ops' in result:
      framer.PrintOps(result['decompressed_interpretable_ops'])
    if 'output_headers' in result:
      output_headers = result['output_headers']
      message = CompareHeaders(test_frame, output_headers)
      if message:
        print 'Something is wrong with this frame.'
        if options.verbose >= 1:
          print message
        if options.verbose >= 5:
          print 'It should be:'
          for k,v in        request.iteritems(): print '\t%s: %s' % (k,v)
          print 'but it was:'
          for k,v in output_headers.iteritems(): print '\t%s: %s' % (k,v)

  lines = []
  for protocol_name, results in processing_results:
    compressed_size = len(results['compressed'])
    uncompressed_size = len(results['serialized_ops'])
    accumulator[protocol_name][0] += compressed_size
    accumulator[protocol_name][1] += uncompressed_size
    if baseline_size is not None:
      ratio = 1.0 * compressed_size / baseline_size
    else:
      ratio = 0
    lines.append( ('%s %s' % (protocol_name, frametype_message),
                  uncompressed_size,
                  compressed_size,
                  ratio) )
  if options.verbose >= 1:
    print ('\t%% %ds              UC  |  CM  | ratio' % (
           protocol_name_field_width+10)) % ''
    line_format = '\t%% %ds frame size: %%4d | %%4d | %%2.2f ' % (
        protocol_name_field_width+10)
    for line in sorted(lines):
      print line_format % line
    print



if __name__ == "__main__":
  main()
