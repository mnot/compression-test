
import hpack
from .. import BaseProcessor, spdy_dictionary, format_http1

class Processor(BaseProcessor):
  def __init__(self, options, is_request, params):
    BaseProcessor.__init__(self, options, is_request, params)
    self.compressor = hpack.Encoder()
    self.decompressor = hpack.Decoder()
    self.sensitive = []

  def compress(self, in_headers, host):
    headers = [(n,v,n.lower() in self.sensitive) for (n,v) in in_headers.items()]
    return self.compressor.encode(headers)

  def decompress(self, compressed):
    return self.decompressor.decode(compressed)