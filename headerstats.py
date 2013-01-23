#!/usr/bin/env python

"""
compression_test.py

Tests various HTTP header compression algorithms, to compare them.

requires: https://github.com/axiak/pybloomfiltermmap
"""

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=W0311

from pybloomfilter import BloomFilter
from collections import defaultdict
from importlib import import_module
from datetime import datetime
from Cookie import BaseCookie
import sys
import locale
import optparse
import struct

from lib.harfile import read_har_file
from lib.processors import Processors


def epoch(dt):
  return (dt - datetime.utcfromtimestamp(0)).total_seconds()

NEW_EPOCH = epoch(datetime(1990,1,1,0,0,0,0))

# Optimized date encoding based on NEW_EPOCH VALUE
def enc_date(val, typ='req'):
  try:
    _v = epoch(datetime.strptime(val, '%a, %d %b %Y %H:%M:%S GMT')) - NEW_EPOCH 
    return struct.pack('!I',_v)
  except:
    # parse it as delta-seconds... at least try 
    try:
      val = max(0,int(val))
    except:
      # it's an invalid timestamp... just set to 0 and move on
      val = 0
    return enc_uvarint(val)
    
# Encode a number as a uvarint (unsigned variable length int)
def enc_uvarint(val, typ='req'):
  if '' == val:
    val = 0
  # on the offchance there are multiple values... TODO: handle this better...
  if hasattr(val,'split'):
    val = val.split('\x00')[0]
  val = max(0,int(val)) 
  v = ''
  shift = True
  while shift:
    shift = val >> 7
    v += chr((val & 0x7F) | (0x80 if shift != 0 else 0x00))
    val = shift
  return v
  
# Encoding a Set-Cookie header value.. basic encoding (no extensions supported beyond HttpOnly and Secure)
def enc_setcookie(val, typ='req'):
  vals = val.split('\x00');
  encoded = ''
  for v in vals:
    if len(encoded) > 0:
      encoded += '\x00';
    v = v.replace(']','_') # work around parsing bug for some cookie values
    v = v.replace('[','_')
    cookie = BaseCookie(v)
    for n in cookie:
      morsel = cookie[n]
      encoded += '.' #non-op... represent the bit flags
      encoded += struct.pack('!B',len(n))
      encoded += n
      encoded += struct.pack('!L',len(morsel.value))
      for f in ['path', 'domain']:
        l = len(morsel[f])
        encoded += struct.pack('!H',l)
        if l > 0:
          encoded += morsel[f]
      if len(morsel['max-age']) > 0:
        encoded += enc_uvarint(morsel['max-age'])
      else:
        encoded += enc_date(morsel['expires'])
  return encoded

# Encoding Cache-Control...

# adapted from httplib2 (https://code.google.com/p/httplib2/source/browse/python3/httplib2/__init__.py)
def _parse_cache_control(cc):
    cc = cc.replace('\x00', ',')
    retval = {}
    parts =  cc.split(',')
    parts_with_args = [tuple([x.strip().lower() for x in part.split("=", 1)]) for part in parts if -1 != part.find("=")]
    parts_wo_args = [(name.strip().lower(), 1) for name in parts if -1 == name.find("=")]
    retval = dict(parts_with_args + parts_wo_args)
    return retval

def valOrZero(parts,m):
  if m in parts:
    return parts[m]
  else: 
    return 0

def enc_cachecontrol(val, typ='req'):
  parts = _parse_cache_control(val)
  encoded = '_'; #represent first flags bit.. easier this way
  encoded += enc_uvarint(valOrZero(parts,'max-age'))
  if typ == 'req':
    encoded += enc_uvarint(valOrZero(parts,'max-stale'))
    encoded += enc_uvarint(valOrZero(parts,'min-fresh'))
    encoded += enc_uvarint(0) # num exts
  else:
    encoded += enc_uvarint(valOrZero(parts,'s-maxage'))
    if 'no-cache' in parts and hasattr(parts,'len') and len(parts['no-cache']) > 0:
      encoded += enc_uvarint(1)
      encoded += struct.pack('!B',len(parts['no-cache']))
      encoded += parts['no-cache']
    else:
      encoded += enc_uvarint(0) # num_no_cache_headers
    encoded += enc_uvarint(0) # num_private_headers
    encoded += enc_uvarint(0) # num exts
  return encoded



encoders = {
  'last-modified': enc_date,
  'date': enc_date,
  'expires': enc_date,
  'if-modified-since': enc_date,
  'if-unmodified-since': enc_date,
  ':status': enc_uvarint,
  'content-length': enc_uvarint,
  'age': enc_uvarint,
  'set-cookie': enc_setcookie,
  'cache-control': enc_cachecontrol
}




class Counter(object):
  """
  BloomFilter-based unique value count
  """
  
  def __init__(self):
    self.bloom = BloomFilter(10000,0.1)
    self.uniques = 0
    self.count = 0
    self.val_freek = {}
    
  def inc(self,val):
    self.count += 1
    if not self.bloom.add(val):
      self.uniques += 1

    if not val in self.val_freek:
      self.val_freek[val] = 1
    else:
      self.val_freek[val] += 1
      
  def ratio(self):
    return float(self.uniques)/float(self.count)

  def freeks(self):
    tw = sum(v for k,v in self.val_freek.items())
    ret = {}
    for k,v in self.val_freek.items():
      ret[k] = (float(v)/float(tw)) * 100
    return ret

class CompressionTester(object):
  """
  This is the thing.
  """
  msg_types = ['req', 'res']
  streamifier_dir = "lib.streamifiers"
  default_processor = "http1"
  c = {
    'req':{
      '_TOTAL_HEADER_VALUE_LEN': 0,
      '_TOTAL_ENCODED_VALUE_LEN': 0,
      '_TOTAL_MESSAGES': 0,
      '_TOTAL_HEADER_INSTANCES': 0
    },
    'res':{
      '_TOTAL_HEADER_VALUE_LEN': 0,
      '_TOTAL_ENCODED_VALUE_LEN': 0,
      '_TOTAL_MESSAGES': 0,
      '_TOTAL_HEADER_INSTANCES': 0
    }
  }
  # tracks variability of all headers across all samples tested...
  v = {}

  def __init__(self, output):
    self.options, self.args = self.parse_options()
    self.output = output
    self.tsv_out = defaultdict(list)  # accumulator for TSV output
    self.processors = Processors(self.options, self.msg_types, output)
    self.streamify = self.load_streamifier(self.options.streamifier)
    self.run()

  def run(self):
    "Let's do this thing."
    streams = []
    for filename in self.args:
      har_requests, har_responses = read_har_file(filename)
      messages = zip(har_requests, har_responses)
      streams.extend(self.streamify(messages))
    for stream in streams:
      section = self.c[stream.msg_type]
      for (hdrs, host) in stream.messages:
        section['_TOTAL_MESSAGES'] += 1
        for (key,val) in hdrs.iteritems():
          if not key in self.v:
            self.v[key] = Counter()
          self.v[key].inc(val)
          
          encoded = val
          if key in encoders:
            encoded = encoders[key](val, stream.msg_type)
          
          if not key in section:
            section[key] = {
              'C':0,
              'T':0,
              'A':0.0,
              'L':sys.maxint,
              'H':0,
              'ET':0,
              'EA':0.0,
              'EL':sys.maxint,
              'EH':0,
              'V': Counter()}
          l = len(val)
          el = len(encoded)
          section['_TOTAL_HEADER_VALUE_LEN'] += l
          section['_TOTAL_HEADER_INSTANCES'] += 1
          section['_TOTAL_ENCODED_VALUE_LEN'] += el
          k = section[key]
          k['C'] += 1
          k['T'] += l
          k['A'] = float(k['T']) / float(k['C'])
          k['L'] = min(k['L'], l)
          k['H'] = max(k['H'], l)
          
          k['ET'] += el
          k['EA'] = float(k['ET']) / float(k['C'])
          k['EL'] = min(k['EL'],el)
          k['EH'] = max(k['EH'],el)
          
          k['V'].inc(val)
    for section,data in self.c.iteritems():
      print '%s: ' % section
      print 'TOTAL HEADER VALUE LENGTH:     %d' % data['_TOTAL_HEADER_VALUE_LEN']
      print 'NUMBER OF UNIQUE HEADERS:      %d' % (len(data) - 4)
      print 'TOTAL NUMBER OF HEADERS:       %d' % data['_TOTAL_HEADER_INSTANCES']
      print 'TOTAL NUMBER OF MESSAGES:      %d' % data['_TOTAL_MESSAGES']
      print 'TOTAL BYTES SAVED BY ENCODING: %d' % (data['_TOTAL_HEADER_VALUE_LEN'] - data['_TOTAL_ENCODED_VALUE_LEN'])
      
      for (key,value) in sorted(data.iteritems(), key=lambda(k,v): (v,k), reverse=True):
        if not key[0] == '_':
          print '%s: ' % key
          print ' Instances:   %d' % value['C']
          print ' Total:       %d' % value['T']
          print ' Average:     %.2f' % value['A']
          print ' Low:         %d' % value['L']
          print ' High:        %d' % value['H']
          print ' Variability: %.4f' % value['V'].ratio()
          print ' Percent of Total Size: %.6f' % ((float(value['T']) / float(data['_TOTAL_HEADER_VALUE_LEN'])) * 100)
          print ' Percent of Total Count: %.6f' % ((float(value['C']) / float(data['_TOTAL_HEADER_INSTANCES'])) * 100)
          if key in encoders:
            print ' Encoded: '
            print '  Total:      %d' % value['ET']
            print '  Average:    %.2f' % value['EA']
            print '  Low:        %d' % value['EL']
            print '  High:       %d' % value['EH']
            print '  Ratio:      %.2f' % (100 - ((float(value['ET']) / float(value['T'])) * 100))
          print '\n'
 
    print 'TOTAL VARIABILITY FOR ALL HEADERS:'
    tmp = {}
    fmt = "{:<20} {:<50} {:<20}"
    for (key,value) in self.v.iteritems():
      tmp[key] = value.ratio()
    ord = sorted(tmp,key=tmp.get)
    for key in sorted(tmp,key=tmp.get):
      print fmt.format(key,tmp[key],self.v[key].count)
      
    print '\n'
    print 'Header Frequencies:'
    for (key,value) in self.v.items():
      print '  %s: ' % key
      for k,v in value.freeks().items():
        print '    %.2f - %s' % (v,k)
    print '\n'

    
  def load_streamifier(self, name):
    "Load the streamifier specified in the options."
    return import_module("%s.%s" % (self.streamifier_dir, name)) \
      .Streamifier([p.name for p in self.processors.processors['req']]) \
      .streamify

  def parse_options(self):
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
                  default=[self.default_processor])
    optp.add_option('-b', '--baseline',
                  dest='baseline',
                  help='baseline codec to base comparisons upon. '
                  '(default: %default)',
                  default=self.default_processor)
    optp.add_option('-t', '--tsv',
                  action="store_true",
                  dest="tsv",
                  help="output TSV.",
                  default=False)
    optp.add_option('-s', '--streamifier',
                  dest="streamifier",
                  help="streamifier module to use (default: %default).",
                  default="public_suffix")
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
