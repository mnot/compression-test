# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#
# Binary-Optimized Header Encoding Compressor Test
# Author: James M Snell <jasnell@gmail.com> ...
# Based on latest draft: draft-snell-httpbis-bohe-01
#
import zlib
import struct
import random
from .. import spdy_dictionary, BaseProcessor, strip_conn_headers

#
# This is an alternative bohe strategy that uses random assignment
# of individual headers to isolated compressed header blocks.  The
# idea is that, to prevent CRIME style compression-ratio attacks,
# headers are assigned randomly at serialization to one of three 
# distinct compression blocks, which are then composed together in
# a random order. In theory, an attacker would have no way of knowing
# which block their contain their reference data.
#  
# +-------------+--------------------------+
# | num_headers |   block 1 len (4 bytes)  |
# +-------------+--------------------------+
# |        compressed header block 1       |
# +----------------------------+-----------+
# |  block 2 len (4 bytes)     |           |
# +----------------------------+           |
# |        compressed header block 2       |
# +----------------------------+-----------+
#

def bin_encoder(obj,val):
  if 'values' in obj and val in obj['values']:
    out = []
    out.append(struct.pack('!H',obj['id']))
    out.append(obj['values'][val])
    return ''.join(out)
  elif 'fallback' in obj:
    return obj['fallback'](obj,val)
  else:
    return text_encoder(obj,val)
  
def text_encoder(obj,val):
  out = []
  out.append(struct.pack('!H',obj['id']))
  out.append(struct.pack('!L', 0x80 << 16 | len(val))[1:])
  out.append(val)
  return ''.join(out)
  
def date_encoder(obj,val):
  #out = []
  #out.append(struct.pack('!H',obj['id']))
  # TODO: Binary Date Output
  #return ''.join(out)
  return text_encoder(obj,val)
  
def ext_encoder(key,val):
  out = []
  out.append(struct.pack('!B', 128 | len(key)))
  out.append(key)
  out.append(struct.pack('!L', 0x80 << 16 | len(val))[1:])
  out.append(val)
  return ''.join(out)
  
opt_headers = {
  ':scheme': {
    'id': 0x00,
    'enc':bin_encoder
  },
  ':version': {
    'id': 0x01,
    'enc':bin_encoder,
    'values': {
      '1.0': struct.pack('!BBBBB',0x00, 0x00, 0x02, 0x01, 0x00),
      '1.1': struct.pack('!BBBBB',0x00, 0x00, 0x02, 0x01, 0x01),
      '2.0': struct.pack('!BBBBB',0x00, 0x00, 0x02, 0x02, 0x00)
    },
    'fallback': text_encoder
  },
  ':method': {
    'id':0x02,
    'enc':bin_encoder,
    'values': {
      'GET':     struct.pack('!BBBB',0x00, 0x00, 0x01, 0x01),
      'POST':    struct.pack('!BBBB',0x00, 0x00, 0x01, 0x02),
      'PUT':     struct.pack('!BBBB',0x00, 0x00, 0x01, 0x03),
      'DELETE':  struct.pack('!BBBB',0x00, 0x00, 0x01, 0x04),
      'PATCH':   struct.pack('!BBBB',0x00, 0x00, 0x01, 0x05),
      'HEAD':    struct.pack('!BBBB',0x00, 0x00, 0x01, 0x06),
      'OPTIONS': struct.pack('!BBBB',0x00, 0x00, 0x01, 0x07),
      'CONNECT': struct.pack('!BBBB',0x00, 0x00, 0x01, 0x08)
    },
    'fallback': text_encoder
  },
  ':host': {
    'id': 0x03,
    'enc':text_encoder
  },
  ':path': {
    'id': 0x04,
    'enc':text_encoder
  },
  ':status': {
    'id': 0x05,
    'enc':bin_encoder
  },
  ':status-text': {
    'id': 0x06,
    'enc':text_encoder
  },
  'content-length': {
    'id': 0x07,
    'enc':bin_encoder
  },
  'content-type': {
    'id': 0x08,
    'enc':text_encoder
  },
  'content-encoding': {
    'id': 0x09,
    'enc':text_encoder
  },
  'expect': {
    'id': 0x0A,
    'enc':text_encoder
  },
  'location': {
    'id': 0x0B,
    'enc':text_encoder
  },
  'last-modified': {
    'id': 0x0C,
    'enc':date_encoder
  },
  'etag': {
    'id': 0x0D,
    'enc':text_encoder
  },
  'if-match': {
    'id': 0x0E,
    'enc':text_encoder
  },
  'if-none-match': {
    'id': 0x0F,
    'enc':text_encoder
  },
  'if-modified-since': {
    'id': 0x10,
    'enc':date_encoder
  },
  'if-unmodified-since': {
    'id': 0x11,
    'enc':date_encoder
  },
  'age': {
    'id': 0x12,
    'enc':text_encoder
  },
  'cache-control': {
    'id': 0x13,
    'enc':text_encoder
  },
  'expires': {
    'id': 0x14,
    'enc':date_encoder
  },
  'vary': {
    'id': 0x15,
    'enc':bin_encoder
  },
  'accept': {
    'id': 0x16,
    'enc':text_encoder
  },
  'accept-language': {
    'id': 0x17,
    'enc':text_encoder
  },
  'accept-charset': {
    'id': 0x18,
    'enc':text_encoder
  },
  'accept-encoding': {
    'id': 0x19,
    'enc':text_encoder
  },
  'allow': { 
    'id': 0x1A,
    'enc':bin_encoder
  },
  'content-language': {
    'id': 0x1B,
    'enc':text_encoder
  },
  'content-location': {
    'id': 0x1C,
    'enc':text_encoder
  },
  'date': {
    'id': 0x1D,
    'enc':date_encoder
  },
  'from': {
    'id': 0x1E,
    'enc':text_encoder
  },
  'warning': {
    'id': 0x1F,
    'enc':text_encoder
  },
  'cookie': {
    'id': 0x20,
    'enc': text_encoder,
    'compress': False
  },
  'set-cookie': {
    'id': 0x21,
    'enc': text_encoder,
    'compress': False
  },
  'cookie2': {
    'id': 0x20,
    'enc': text_encoder,
    'compress': False
  },
  'set-cookie2': {
    'id': 0x21,
    'enc': text_encoder,
    'compress': False
  }
}

def do_compress(obj):
  return not('compress' in obj and not obj['compress'])

class Processor(BaseProcessor):
  def __init__(self, options, is_request, params):
    BaseProcessor.__init__(self, options, is_request, params)
    self.compressors = [
      zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, 15),
      zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, 15)
    ]
    self.compressors[0].compress(spdy_dictionary.spdy_dict)
    self.compressors[1].compress(spdy_dictionary.spdy_dict)
    self.compressors[0].flush(zlib.Z_SYNC_FLUSH)
    self.compressors[1].flush(zlib.Z_SYNC_FLUSH)


  def compress(self, in_headers, host):
    frame = []
    blocks = self.BoheHeadersFormat(strip_conn_headers(in_headers))
    num_headers = blocks[0]
    block1 = self.compressors[0].compress(blocks[1])
    block1 += self.compressors[0].flush(zlib.Z_SYNC_FLUSH)
    
    block2 = self.compressors[1].compress(blocks[2])
    block2 += self.compressors[1].flush(zlib.Z_SYNC_FLUSH)
    
    frame_len = len(block1) + len(block2)
    frame.append(struct.pack('!L', 0x1 << 31 | 0x11 << 15 | 0x8))
    frame.append(struct.pack('!L', frame_len + 8))
    frame.append(struct.pack('!L', 1))
    frame.append(struct.pack('!B', num_headers))
    frame.append(struct.pack('!L', len(block1)))
    frame.append(block1)
    frame.append(struct.pack('!L', len(block2)))
    frame.append(block2)
    return ''.join(frame)

  def BoheHeadersFormat(self, request):
    buckets = [[],[],[]]
    for (key, val) in request.iteritems():
      if key in opt_headers:
        obj = opt_headers[key]
        enc = obj['enc'](obj,val)
        buckets[random.randint(0,1)].append(enc)
      else:
        enc = ext_encoder(key,val)
        buckets[random.randint(0,1)].append(enc)
    random.shuffle(buckets)
    return len(request.keys()), ''.join(buckets[0]), ''.join(buckets[1])