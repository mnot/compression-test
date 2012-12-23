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
  """Take the frame and format it as HTTP/1"""
  out_frame = []
  fl = ''
  avoid_list = []
  if ':method' in frame:
    fl = '%s %s %s%s' % (
        frame[':method'], frame[':path'], frame[':version'], delimiter)
    avoid_list = [':method', ':path', ':version', ':scheme']
  else:
    fl = '%s %s %s%s' % (
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
  

# FIXME: function to strip connection headers

def parse_http1(message):
  """Take a HTTP1 message and return the header structure for it."""
  out = {}
  lines = message.strip().split("\n")
  top_line = lines.pop(0).split(None, 2)
  for line in lines:
    if not line: break
    name, value = line.split(":", 1)
    name = name.lower()
    if out.has_key(name):
      out[name] += "\0" + value.strip()
    else:
      out[name] = value.strip()
  if "host" in out.keys():
    out[":scheme"] = "http" # FIXME
    out[':method'] = top_line[0]
    out[':path'] = top_line[1]
    out[':version'] = top_line[2].strip()
    out[':host'] = out['host']
    del out['host']
  else:
    out[':version'] = top_line[0]
    out[':status'] = top_line[1]
    out[':status-text'] = top_line[2].strip()
  return out