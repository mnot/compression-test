#!/usr/bin/env python

from collections import defaultdict

from . import BaseStreamifier, Stream

from publicsuffix import PublicSuffixList

class Streamifier(BaseStreamifier):
  """
  Use the Public Suffix List <http://publicsuffix.org> to split the messages
  into streams, one per direction per suffix.
  """
  def __init__(self):
    BaseStreamifier.__init__(self)
    self.psl = PublicSuffixList()

  def streamify(self, messages):
    """
    Given a list of messages (each a req, res tuple), return a list of
    Stream objects.
    """
    reqs = defaultdict(list)
    ress = defaultdict(list)
    suffixes = []
    for req, res in messages:
      host = req[':host']
      suffix = self.psl.get_public_suffix(host.split(":", 1)[0])
      if suffix not in suffixes:
        suffixes.append(suffix)
      reqs[suffix].append((req, host))
      ress[suffix].append((res, host))

    streams = []
    for suffix in suffixes:
      streams.append(Stream(suffix, reqs[suffix], 'req'))
      streams.append(Stream(suffix, ress[suffix], 'res'))
    return streams