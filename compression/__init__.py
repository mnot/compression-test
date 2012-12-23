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
    
    
def format_http1(frame, delimiter="\r\n"):
  """Takes the frame and formats it as HTTP/1"""
  out_frame = []
  fl = ''
  avoid_list = []
  if ':method' in frame:
    fl = '%s %s HTTP/%s%s' % (
        frame[':method'], frame[':path'], frame[':version'], delimiter)
    avoid_list = [':method', ':path', ':version']
  else:
    fl = 'HTTP/%s %s %s%s' % (
        frame[':version'], frame[':status'], frame[':status-text'], delimiter)
    avoid_list = [':version', ':status', ':status-text']
  out_frame.append(fl)
  
  for (key, val) in frame.iteritems():
    if key in avoid_list:
      continue
    if key == ':host':
      key = 'host'
    for individual_val in val.split('\x00'):
      out_frame.append(key)
      out_frame.append(': ')
      out_frame.append(individual_val)
      out_frame.append(delimiter)
  out_frame.append(delimiter)
  return ''.join(out_frame)