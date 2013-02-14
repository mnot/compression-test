# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import zlib
import re

import header_freq_tables
import spdy4_codec_impl
import huffman
import common_utils
from .. import BaseProcessor

# There are a number of TODOS in the spdy4
#      have near indices. Possibly renumber whever something is referenced)

class Processor(BaseProcessor):
  """
  This class formats header frames in SPDY4 wire format, and then reads the
  resulting wire-formatted data and restores the data. Thus, it compresses and
  decompresses header data.

  It also keeps track of letter frequencies so that better frequency tables
  can eventually be constructed for use with the Huffman encoder.
  """
  def __init__(self, options, is_request, params):
    BaseProcessor.__init__(self, options, is_request, params)
    self.compressor   = spdy4_codec_impl.Spdy4CoDe(params)
    self.decompressor = spdy4_codec_impl.Spdy4CoDe(params)
    self.hosts = {}
    self.group_ids = common_utils.IDStore(2**31)
    self.wf = self.compressor.wf
    if is_request:
      request_freq_table = header_freq_tables.request_freq_table
      self.compressor.huffman_table = huffman.Huffman(request_freq_table)
      self.decompressor.huffman_table = huffman.Huffman(request_freq_table)
    else:
      response_freq_table = header_freq_tables.response_freq_table
      self.compressor.huffman_table = huffman.Huffman(response_freq_table)
      self.decompressor.huffman_table = huffman.Huffman(response_freq_table)

  def PrintOps(self, ops):
    for op in ops:
      print "\t", spdy4_codec_impl.FormatOp(op)

  def compress(self, inp_headers, host):
    normalized_host = re.sub('[0-1a-zA-Z-\.]*\.([^.]*\.[^.]*)', '\\1',
                             host)
    if normalized_host in self.hosts:
      group_id = self.hosts[normalized_host]
    else:
      group_id = self.group_ids.GetNext()
      self.hosts[normalized_host] = group_id
    inp_ops = self.compressor.MakeOperations(inp_headers, group_id)
    inp_real_ops = self.compressor.OpsToRealOps(inp_ops, group_id)
    compressed_blob = self.compressor.Compress(inp_real_ops)
    return compressed_blob

  def decompress(self, compressed_blob):
    out_real_ops = self.decompressor.Decompress(compressed_blob)
    try:
      (group_id, out_ops, out_headers) = \
          self.decompressor.RealOpsToOpAndExecute(out_real_ops)
    except:
      raise
    return out_headers


