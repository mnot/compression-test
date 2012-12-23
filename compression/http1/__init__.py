# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from .. import common_utils, BaseProcessor, spdy_dictionary

class Processor(BaseProcessor):
  def compress(self, in_headers, host):
    return common_utils.FormatAsHTTP1(in_headers)
