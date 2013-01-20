#!/usr/bin/env python

"""
Serialise ASCII as seven bits.

Yes, I threw up a bit too.
"""

from bitarray import bitarray

def encode(text):
  ba = bitarray()
  out = bitarray()
  ba.fromstring(text)
  s = 0
  while s < len(ba):
    byte = ba[s:s+8]
    out.extend(byte[1:8])
    s += 8
#  print out
  return out.tobytes()

def decode(bits):
  ba = bitarray()
  out = bitarray()
  ba.frombytes(bits)
  s = 0
  while s < len(ba):
    seven = ba[s:s+7]
    out.append(0)
    out.extend(seven)
    s += 7
  return out.tostring()[:-1].encode('ascii')
	

if __name__ == "__main__":
  import sys
  instr = sys.argv[1].strip().encode('ascii')
  print "before: %s" % len(instr)
  f = encode(instr)
  print "after: %s" % len(f)
  g = decode(f)
  assert instr == g, "\n%s\n%s" % (repr(instr), repr(g))
