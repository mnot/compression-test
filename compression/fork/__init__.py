# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import struct
import sys

from .. import BaseProcessor, format_http1, strip_conn_headers

class Processor(BaseProcessor):
  def __init__(self, options, is_request, params):
    BaseProcessor.__init__(self, options, is_request, params)
    path = os.path.join(os.getcwd(), params[0])
    self.process = subprocess.Popen(path,
                                    #bufsize=-1,
                                    shell=False,
                                    stdout=subprocess.PIPE,
                                     stdin=subprocess.PIPE)

  def compress(self, in_headers, host):
    http1_msg = format_http1(strip_conn_headers(in_headers))
    self.process.stdin.write(http1_msg)
    output = self.process.stdout.read(8)
    size = struct.unpack("q", output)[0]
    output = self.process.stdout.read(int(size))
    return output
