#!/usr/bin/python

from lrustorage import LruStorage
from lrustorage import KV
from lrustorage import RefCntString
import unittest

class TestLruStorage(unittest.TestCase):
  def test_BasicFunctionality(self):
    max_items = 10
    max_byte_size = 7*2*max_items
    s = LruStorage(max_byte_size, max_items)
    key_fmt = "key_%03d"
    val_fmt = "val_%03d"
    for i in xrange(max_items):
      s.Store(KV(key_fmt % i, val_fmt % i))
    self.assertEqual(len(s.ring), max_items)
    self.assertEqual(s.byte_size, max_byte_size)
    for i in xrange(max_items):
      entry = s.Lookup(i)
      self.assertEqual(entry.key(), key_fmt % i)
      self.assertEqual(entry.val(), val_fmt % i)
      self.assertEqual(entry.seq_num, i)

  def test_MaxItemSize(self):
    caught_error = 0

    max_items = 10
    max_byte_size = 10000000
    s = LruStorage(max_byte_size, max_items)
    key_fmt = "key_%03d"
    val_fmt = "val_%03d"
    try:
      for i in xrange(max_items+10):
        s.Store(KV(key_fmt % i, val_fmt % i))
    except MemoryError as me:
      caught_error = 1
    if not caught_error:
      self.fail("Failure: Attempted to store too many ITEMS, but no exception")
      return

  def test_MaxByteSize(self):
    caught_error = 0

    max_items = 10
    max_byte_size = 7*2*(max_items - 1)
    s = LruStorage(max_byte_size, max_items)
    key_fmt = "key_%03d"
    val_fmt = "val_%03d"
    try:
      for i in xrange(max_items + 1):
        s.Store(KV(key_fmt % i, val_fmt % i))
    except MemoryError as me:
      if i == max_items - 1:
        caught_error = 1
    if not caught_error:
      self.fail("Failure: Attempted to store too many BYTES, but no exception")
      return

  def test_FindKeyValEntries(self):
    caught_error = 0

    max_items = 10
    max_byte_size = 7*2*max_items
    s = LruStorage(max_byte_size, max_items)
    key_fmt = "key_%03d"
    val_fmt = "val_%03d"
    for i in xrange(max_items):
      s.Store(KV(key_fmt % i, val_fmt % i))

    (ke, ve) = s.FindKeyValEntries("key_009", "")
    self.assertEqual(ke.key(), "key_009")
    self.assertIsNone(ve)
    (ke, ve) = s.FindKeyValEntries("key_001", "val_001")
    self.assertEqual(ke.key(), "key_001")
    self.assertEqual(ve.key(), "key_001")
    self.assertEqual(ve.val(), "val_001")

  def test_PopOne(self):
    caught_error = 0

    max_items = 10
    max_byte_size = 7*2*max_items
    s = LruStorage(max_byte_size, max_items)
    key_fmt = "key_%03d"
    val_fmt = "val_%03d"
    for i in xrange(max_items):
      s.Store(KV(key_fmt % i, val_fmt % i))

    self.assertEqual(s.Lookup(0).key(), key_fmt % 0)

    for i in xrange(0, max_items):
      entry = s.Lookup(i)
      s.PopOne()
      try:
        s.Lookup(i)
      except IndexError as ie:
        caught_error = 1
      if not caught_error:
        print s.ring
        print s.Lookup(i)
        self.fail("Failure: PopOne() didn't pop the first element")
        return

    self.assertEqual(s.byte_size, 0)
    self.assertEqual(len(s.ring), 0)

    caught_error = 0
    try:
      s.PopOne()
    except:
      caught_error = 1
      pass
    if not caught_error:
      self.fail("Did PopOne() with empty LruStorage, and got no error!?")
      return

  def test_Reserve(self):
    max_items = 10
    max_byte_size = 1000
    s = LruStorage(max_byte_size, max_items)
    key_fmt = "key_%06d"
    val_fmt = "val_%06d"
    for i in xrange(max_items + 10):
      if i < max_items:
        kv = KV(key_fmt % i, val_fmt % i)
        s.Store(kv)
      else:
        try:
          kv = KV(key_fmt % i, val_fmt % i)
          s.Store(kv)
          self.fail("This shouldn't have worked. Error.")
          return
        except MemoryError as me:
          s.Reserve(kv.ByteSize(), 1)
          kv = KV(key_fmt % i, val_fmt % i)
          s.Store(kv)
    s = LruStorage(20, max_items)
    s.Store(KV("12345", "67890"))
    s.Store(KV("12345", "67890"))
    try:
      s.Store(KV("12345", "678901"))
      self.fail("This shouldn't have worked. Error.")
      return
    except MemoryError as me:
      s.Reserve(11,1)
      s.Store(KV("12345", "678901"))
      self.assertEqual(len(s.ring), 1)

  def test_RollOver(self):
    max_items = 64
    max_seq_num = 64
    max_byte_size = (6+4)*2*max_items
    s = LruStorage(max_byte_size, max_items, max_seq_num)
    key_fmt = "key_%06d"
    val_fmt = "val_%06d"
    for i in xrange(max_items + max_items/2):
      kv = KV(key_fmt % i, val_fmt % i)
      s.Reserve(kv.ByteSize(), 1)
      s.Store(kv)
    for i in xrange(max_items/2, max_items + max_items/2):
      key_str = key_fmt % i
      item = s.Lookup(i % max_seq_num)
      self.assertEqual(item.key(), key_str)

  def test_RollOverWithOffset(self):
    max_items = 64
    max_seq_num = 128
    offset = 60
    max_byte_size = (6+4)*2*max_items
    s = LruStorage(max_byte_size, max_items, max_seq_num, offset)
    key_fmt = "key_%06d"
    val_fmt = "val_%06d"
    idx = offset
    for i in xrange(offset, max_items*3 + offset):
      if idx >= max_seq_num:
        idx = offset
      key_str = key_fmt % idx
      kv = KV(key_fmt % idx, val_fmt % idx)
      s.Reserve(kv.ByteSize(), 1)
      s.Store(kv)
      item = s.Lookup(idx)
      self.assertEqual(item.seq_num, idx)
      self.assertEqual(item.key(), key_str)
      idx += 1

  def test_RefCntString(self):
    orig = "foobarbaz"
    ref1 = RefCntString(orig)
    self.assertEqual(len(ref1), len(orig))
    self.assertEqual(ref1.refcnt(), 1)

    ref2 = RefCntString(ref1)
    self.assertEqual(ref1.refcnt(), 2)
    self.assertEqual(len(ref1), 0)
    self.assertEqual(ref2.refcnt(), 2)
    self.assertEqual(len(ref2), 0)

    ref3 = RefCntString(ref2)
    self.assertEqual(ref1.refcnt(), 3)
    self.assertEqual(len(ref1), 0)
    self.assertEqual(ref2.refcnt(), 3)
    self.assertEqual(len(ref2), 0)
    self.assertEqual(ref3.refcnt(), 3)
    self.assertEqual(len(ref2), 0)

    ref1.done()
    self.assertEqual(ref2.refcnt(), 2)
    self.assertEqual(len(ref2), 0)
    self.assertEqual(ref3.refcnt(), 2)
    self.assertEqual(len(ref2), 0)

    ref2.done()
    self.assertEqual(ref3.refcnt(), 1)
    self.assertEqual(len(ref3), len(orig))

unittest.main()

