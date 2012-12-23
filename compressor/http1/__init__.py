# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from .. import BaseProcessor, spdy_dictionary, format_http1, parse_http1

class Processor(BaseProcessor):
  def compress(self, in_headers, host):
    return format_http1(in_headers)

  def decompress(self, compressed):
    return parse_http1(compressed)