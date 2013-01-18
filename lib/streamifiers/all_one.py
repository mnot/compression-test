#!/usr/bin/env python

from . import BaseStreamifier, Stream

class Streamifier(BaseStreamifier):
  """
  Put all messages into two streams, requests and responses.
  """
  def streamify(self, messages):
    reqs, ress = [], []
    for req, res in messages:
      host = req[':host']
      reqs.append((req, host))
      ress.append((res, host))
    req_stream = Stream('all', reqs, 'req', self.procs)
    res_stream = Stream('all', ress, 'res', self.procs)
    return [req_stream, res_stream]
