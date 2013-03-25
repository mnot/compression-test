#!/usr/bin/env python

from collections import defaultdict

from . import BaseStreamifier, Stream

class Streamifier(BaseStreamifier):
  """
  Split the messages into streams, one per direction per hostname.
  """
  def __init__(self, procs):
    BaseStreamifier.__init__(self, procs)

  def streamify(self, messages):
    """
    Given a list of messages (each a req, res tuple), return a list of
    Stream objects.
    """
    reqs = defaultdict(list)
    ress = defaultdict(list)
    hosts = []
    for req, res in messages:
      host = req[':host'].lower().strip()
      if host not in hosts:
        hosts.append(host)
      reqs[host].append((req, host))
      ress[host].append((res, host))

    streams = []
    for host in hosts:
      streams.append(Stream(host, reqs[host], 'req', self.procs))
      streams.append(Stream(host, ress[host], 'res', self.procs))
    return streams