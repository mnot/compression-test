#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from bit_bucket import BitBucket
import unittest

def RunTestCase(bb, testcase):
  pre_bb = str(bb)
  for instruction in testcase:
    (store_this, expected_output) = instruction
    bb.StoreBits(store_this)
    str_bb = str(bb)
    if str_bb != expected_output:
      print "Failure!: \"%s\" != \"%s\"" % (str_bb, expected_output)
      print "op: ", store_this
      print "Pre bb:   \"%s\"" % pre_bb
      print "expected: \"%s\"" % expected_output
      print "post bb:  \"%s\"" % str_bb
      self.fail()
      raise StandardError()
    pre_bb = str_bb

def ReformatExpectedStr(prefix, expected_str):
  old_expected_bits = expected_str.rsplit(' ')[0].translate(None, "|")
  new_expected_bits = prefix + old_expected_bits
  output = []
  for i in xrange(len(new_expected_bits)):
    if i % 8 == 0:
      output.extend('|')
    output.extend(new_expected_bits[i])
  output = ''.join(output)
  output += ' [%d]' % (len(new_expected_bits) % 8)
  return output

def StoreBitsFromString(bb, expected_bits_str):
  expected_bits = expected_bits_str.rsplit(' ')[0]
  for c in expected_bits:
    if c == '1':
      bb.StoreBit(1)
    elif c == '0':
      bb.StoreBit(0)
  return bb

class TestBitBucket(unittest.TestCase):
  def test_StoreBitsa(self):
    bb = BitBucket()
    testcase_a = [
      (([0xFF,0],6+8),  "|11111111|000000 [6]"),
      (([0xFF], 3),     "|11111111|00000011|1 [1]"),
      (([0x00], 3),     "|11111111|00000011|1000 [4]"),
      (([0xFF,0], 8+6), "|11111111|00000011|10001111|11110000|00 [2]"),
      (([0xFF], 4),     "|11111111|00000011|10001111|11110000|001111 [6]"),
      (([0x0], 4),      "|11111111|00000011|10001111|11110000|00111100|00 [2]"),
      ]
    RunTestCase(bb, testcase_a)

  def test_StoreBitsb(self):
    bb = BitBucket()
    testcase_b = [
      (([0xF0], 5), "|11110 [5]"),
      (([0x0F], 5), "|11110000|01 [2]"),
      (([0xF0], 5), "|11110000|0111110 [7]"),
      (([0x0F], 5), "|11110000|01111100|0001 [4]"),
      (([0xF0], 5), "|11110000|01111100|00011111|0 [1]"),
      (([0x0F], 5), "|11110000|01111100|00011111|000001 [6]"),
      (([0xF0], 5), "|11110000|01111100|00011111|00000111|110 [3]"),
      (([0x0F], 5), "|11110000|01111100|00011111|00000111|11000001 [0]"),
      (([0xF0], 5), "|11110000|01111100|00011111|00000111|11000001|11110 [5]"),
      ]
    RunTestCase(bb, testcase_b)

  def test_StoreBitsc(self):
    bb = BitBucket()
    testcase_c = [
      (([0xF0], 1),        "|1 [1]"),
      (([0x0F], 1),        "|10 [2]"),
      (([0xF0], 1),        "|101 [3]"),
      (([0x0F], 1),        "|1010 [4]"),
      (([0xF0], 1),        "|10101 [5]"),
      (([0x0F], 1),        "|101010 [6]"),
      (([0xF0], 1),        "|1010101 [7]"),
      (([0x0F], 1),        "|10101010 [0]"),
      (([0xF0], 1),        "|10101010|1 [1]"),
      (([0x00,0xFF], 8+7), "|10101010|10000000|01111111 [0]"),
      ]
    RunTestCase(bb, testcase_c)

  def test_StoreBitsd(self):
    bb = BitBucket()
    testcase_d = [
      (([0xF0], 8),        "|11110000 [0]"),
      (([0xF0], 8),        "|11110000|11110000 [0]"),
      (([0xF0], 1),        "|11110000|11110000|1 [1]"),
      (([0x0F], 8),        "|11110000|11110000|10000111|1 [1]"),
      ]
    RunTestCase(bb, testcase_d)

  def test_StoreBitse(self):
    bb = BitBucket()
    testcase_e = [
      (([0,52], 8+6), "|00000000|001101 [6]"),
      (([185], 8),    "|00000000|00110110|111001 [6]"),
     ]
    RunTestCase(bb, testcase_e)

  def test_Clear(self):
    bb = BitBucket()
    bb.StoreBits( ([0xff,0xff,0xff],23))
    if str(bb) != "|11111111|11111111|1111111 [7]":
      self.fail("basic storing of bits didn't work!")
    bb.Clear()
    assert str(bb) == " [0]"
    assert bb.output == []
    assert bb.out_byte == 0
    assert bb.out_boff == 0
    assert bb.idx_byte == 0
    assert bb.idx_boff == 0

  def test_StoreBit(self):
    bb = BitBucket()
    expected_output = "|10111010|11111111|00001111|0101 [4]"
    for c in expected_output:
      if c == '1':
        bb.StoreBit(1)
      elif c == '0':
        bb.StoreBit(0)
    assert expected_output == str(bb)

  def test_StoreBits4(self):
    bb = BitBucket()
    inp = [0xff,0xf0,0xf0,0xfd]
    for n in inp:
      bb.StoreBits4(n)
    assert str(bb) == "|11110000|00001101 [0]"

    bb.Clear()
    bb.StoreBit(0)
    for n in inp:
      bb.StoreBits4(n)
    assert str(bb) == "|01111000|00000110|1 [1]"

    bb.Clear()
    bb.StoreBit(0)
    bb.StoreBit(1)
    for n in inp:
      bb.StoreBits4(n)
    assert str(bb) == "|01111100|00000011|01 [2]"

    bb.Clear()
    bb.StoreBit(0)
    bb.StoreBit(1)
    bb.StoreBit(0)
    for n in inp:
      bb.StoreBits4(n)
    assert str(bb) == "|01011110|00000001|101 [3]"

    bb.Clear()
    bb.StoreBit(0)
    bb.StoreBit(1)
    bb.StoreBit(0)
    bb.StoreBit(1)
    for n in inp:
      bb.StoreBits4(n)
    assert str(bb) == "|01011111|00000000|1101 [4]"

  def test_StoreBits8(self):
    bb = BitBucket()
    inp = [0xff,0x00,0x00,0xdd]
    orig_expected_str = "|11111111|00000000|00000000|11011101 [0]"
    for offset in xrange(16):
      bb.Clear()
      for i in xrange(offset):
        bb.StoreBit(1)
      for n in inp:
        bb.StoreBits8(n)
      assert str(bb) == ReformatExpectedStr('1'*offset, orig_expected_str)

  def test_StoreBits16(self):
    bb = BitBucket()
    inp = [0xff,0xff, 0x00, 0x00, 0x00, 0x00, 0xdd, 0xdd]
    orig_expected_str = "|11111111"*2 + \
                        "|00000000"*2 + \
                        "|00000000"*2 + \
                        "|11011101"*2 + \
                        " [0]"
    for offset in xrange(32):
      bb.Clear()
      for i in xrange(offset):
        bb.StoreBit(1)
      for n in inp:
        bb.StoreBits8(n)
      assert str(bb) == ReformatExpectedStr('1'*offset, orig_expected_str)

  def test_StoreBits32(self):
    bb = BitBucket()
    inp = [0xff, 0xff, 0xff, 0xff,
           0x00, 0x00, 0x00, 0x00,
           0x00, 0x00, 0x00, 0x00,
           0xdd, 0xdd, 0xdd, 0xdd]
    orig_expected_str = "|11111111"*4 + \
                        "|00000000"*4 + \
                        "|00000000"*4 + \
                        "|11011101"*4 + \
                        " [0]"
    for offset in xrange(64):
      bb.Clear()
      for i in xrange(offset):
        bb.StoreBit(1)
      for n in inp:
        bb.StoreBits8(n)
      assert str(bb) == ReformatExpectedStr('1'*offset, orig_expected_str)

  def test_GetBits4(self):
    bb = BitBucket()
    inp = [0xd, 0xd, 0xd, 0xd]
    for offset in xrange(16):
      bb.Clear()
      StoreBitsFromString(bb, "1" * offset + "|11011101|11011101 [0]")
      for i in xrange(offset):
        bb.GetBit()
      for i in xrange(len(inp)):
        assert bb.GetBits4() == inp[i]

  def test_GetBits8(self):
    bb = BitBucket()
    inp = [0xdd, 0xee, 0xaa, 0xdd]
    bitstr = "|11011101|11101110|10101010|11011101 [0]"
    for offset in xrange(16):
      bb.Clear()
      StoreBitsFromString(bb, ("1" * offset) + bitstr)
      for i in xrange(offset):
        bb.GetBit()
      for i in xrange(len(inp)):
        assert bb.GetBits8() == inp[i]

  def test_GetBits16(self):
    bb = BitBucket()
    inp = [0xdddd, 0xeeee, 0xaaaa, 0xdddd]
    bitstr = "|11011101"*2 + \
             "|11101110"*2 + \
             "|10101010"*2 + \
             "|11011101"*2 + \
             " [0]"
    for offset in xrange(32):
      bb.Clear()
      StoreBitsFromString(bb, ("1" * offset) + bitstr)
      for i in xrange(offset):
        bb.GetBit()
      for i in xrange(len(inp)):
        assert bb.GetBits16() == inp[i]

  def test_GetBits32(self):
    bb = BitBucket()
    inp = [0xdddddddd, 0xeeeeeeee, 0xaaaaaaaa, 0xdddddddd]
    bitstr = "|11011101"*4 + \
             "|11101110"*4 + \
             "|10101010"*4 + \
             "|11011101"*4 + \
             " [0]"
    for offset in xrange(64):
      bb.Clear()
      StoreBitsFromString(bb, ("1" * offset) + bitstr)
      for i in xrange(offset):
        bb.GetBit()
      for i in xrange(len(inp)):
        assert bb.GetBits32() == inp[i]

  def test_AdvanceReadPtrToByteBoundary(self):
    bb = BitBucket()
    for offset in xrange(16):
      bb.Clear()
      StoreBitsFromString(bb, "1" * 32)
      for i in xrange(offset):
        bb.GetBit()
      old_idx_byte = bb.idx_byte
      old_idx_boff = bb.idx_boff
      assert bb.idx_byte == offset / 8
      assert bb.idx_boff == offset % 8
      bb.AdvanceReadPtrToByteBoundary()
      if old_idx_boff == 0:
        assert bb.idx_boff == old_idx_boff
        assert bb.idx_byte == old_idx_byte
      else:
        assert bb.idx_boff == 0
        assert bb.idx_byte == (old_idx_byte + 1)

unittest.main()


