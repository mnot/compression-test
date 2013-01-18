#!/usr/bin/env python

from ..stream import Stream

class BaseStreamifier(object):
  """
  Base class for a streamifier.
  """
  def __init__(self):
    pass
    
  def streamify(self, messages):
    """
    Given a list of messages (each a req, res tuple), return a list of
    Stream objects.
    """
    raise NotImplementedError