#!/usr/bin/env python

class BaseProcessor(object):
  "Base class for compression processors."
  def __init__(self, options, is_request, params):
    self.options = options
    self.is_request = is_request
    self.params = params

  def compress(self, in_headers, host):
    """
    'in_headers' are the headers that will be processed
    'host' is the host header value for the request (or associated request,
    if it is a response).
       
    Return value is a dictionary with the following contents:
    
    {
      'contents': [compressed result],
      'size': [size of the compressed contents],
    }
    """
    raise NotImplementedError