# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import string

class WordFreak:
  """
  Observes and accumulates letter frequencies.
  Though it is called 'Word'Freq, it is better thought of
  as letter freq.
  """
  def __init__(self):
    self.code = []
    self.character_freaks = []
    self.length_freaks = {}
    self.eofs = 0
    for i in xrange(256 + 1):
      self.character_freaks.append(0)

  def LookAt(self, ops):
    for op in ops:
      for key in ['key', 'val']:
        if key in op:
          self.length_freaks[len(op[key])] = \
            self.length_freaks.get(len(op[key]),0) + 1
          self.character_freaks[256] += 1
          for c in op[key]:
            self.character_freaks[ord(c)] += 1

  def SortedByFreq(self):
    x = [ (chr(i), self.character_freaks[i]) \
          for i in xrange(len(self.character_freaks))]
    return sorted(x, key=lambda x: x[1], reverse=True)

  def GetFrequencies(self):
    return self.character_freaks

  def __repr__(self):
    printable = string.digits + string.letters + string.punctuation + ' '
    max_freq = 0
    for i in self.character_freaks:
      if i > max_freq:
        max_freq = i
    freq_len = len("%d" % max_freq)
    retval = ["["]
    cur_pair = ""
    cur_line = "  "
    format_string = "(%%s, %%%dd)," % freq_len
    for i in xrange(len(self.character_freaks)):
      if i < 128 and chr(i) in printable:
        sym = '{:>4}'.format(repr(chr(i)))
      else:
        sym = '{:>4}'.format(repr(i))
      cur_pair = format_string % (sym, self.character_freaks[i])
      if len(cur_pair) + len(cur_line) > 60:
        retval.append(cur_line)
        cur_line = "  "
      cur_line = cur_line + cur_pair
    if cur_line != "  ":
      retval.append(cur_line)
    retval.append(']')

    return '\n'.join(retval)

  def __str__(self):
    return self.__repr__()

