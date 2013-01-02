# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from .. import BaseProcessor, strip_conn_headers, format_http1
from collections import defaultdict
import re
import calendar
from email.utils import parsedate as lib_parsedate
from urlparse import urlsplit
import os.path  

class Processor(BaseProcessor):
  """
  This compressor does a few things:

  * It compares the current set of outgoing headers to the last set on
    the connection. If a header has the same value (character-for-character),
    a reference to it is sent in the 'ref' header instead.

  * Common header names are tokenised using the lookups table. If a header
    name does not occur there, its name will be preceded with a "!".

  * Header types that are known to be dates are expressed as a hexidecimal
    number of seconds since the epoch.    
    
  * "\n" is used as a line delimiter, instead of "\r\n".
  
  * No space is inserted between the ":" and the start of the header value.
  """

  lookups = {
    'x-content-type-options': 'xct',
    'content-encoding': 'ce', 
    'access-control-allow-origin': 'ac',
    'content-type': 'ct',
    'accept-language': 'al', 
    'accept-encoding': 'ae', 
    'accept-ranges': 'ar',
    'user-agent': 'ua',
    'server': 's',
    'referer': 'r',
    'accept': 'a',
    'cookie': 'c',
    'last-modified': 'lm',
    'cache-control': 'cc',
    'pragma': 'p',
    'vary': 'v',
    'date': 'd',
    'expires': 'x',
    'content-length': 'cl',
    'etag': 'e',
    'content-language': 'la',
    'via': 'vi',
    'set-cookie': 'sc',
    'p3p': 'p3',
  }
  
  date_hdrs = [
    'last-modified',
    'date',
    'expires'
  ]
  
  url_reqhdrs = [
    'referer'
  ]
  
  def __init__(self, options, is_request, params):
    BaseProcessor.__init__(self, options, is_request, params)
    self.last = None

  def compress(self, in_headers, host):
    headers = {}
    refs = []
    for name, value in strip_conn_headers(in_headers).items():
      if name in self.date_hdrs:
        try:
          headers[self.hdr_name(name)] = "%x" % parse_date(value)
        except ValueError:
          pass
      elif self.last \
      and (name[0] != ":" or name == ':host') \
      and self.last.get(name, None) == value:
        if name == ':host':
          name = 'h'
        refs.append(name)
#      elif name in self.url_reqhdrs:
#        url = urlsplit(value)
#        if url.scheme.lower() == in_headers[':scheme'] \
#        and url.netloc.lower() == in_headers[':host']:
#          # hack hack hack
#          prefix = os.path.commonprefix([url.path, in_headers[':path']]) 
#          if prefix != "":
#            l = len(prefix) + len(in_headers[':scheme']) + #len(in_headers[":host"]) + 3
#            value = value[l:]
#        headers[self.hdr_name(name)] = value
      else:
        headers[self.hdr_name(name)] = value
    self.last = in_headers
    if refs:
      headers["ref"] = ",".join([self.hdr_name(ref) for ref in refs])
    out = []
    return format_http1(headers, delimiter="\n", valsep=":", host='h')
  

#  def decompress(self, compressed):
#    return compressed

  def hdr_name(self, name):
    if name[0] == ":":
      return name
    return self.lookups.get(name, "!%s" % name)



DATE = r"""(?:\w{3},\ [0-9]{2}\ \w{3}\ [0-9]{4}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ GMT |
         \w{6,9},\ [0-9]{2}\-\w{3}\-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ GMT |
         \w{3}\ \w{3}\ [0-9 ][0-9]\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ [0-9]{4})
        """
        
def parse_date(value):
    """Parse a HTTP date. Raises ValueError if it's bad."""
    if not re.match(r"%s$" % DATE, value, re.VERBOSE):
        raise ValueError
    date_tuple = lib_parsedate(value)
    if date_tuple is None:
        raise ValueError
    # http://sourceforge.net/tracker/index.php?func=detail&aid=1194222&group_id=5470&atid=105470
    if date_tuple[0] < 100:
        if date_tuple[0] > 68:
            date_tuple = (date_tuple[0]+1900,)+date_tuple[1:]
        else:
            date_tuple = (date_tuple[0]+2000,)+date_tuple[1:]
    date = calendar.timegm(date_tuple)
    return date