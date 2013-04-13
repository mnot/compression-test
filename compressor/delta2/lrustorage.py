#!/usr/bin/python
from collections import deque

class RefCntString:
  def __init__(self, x):
    self.decr = 1
    if type(x) is str:
      self.data = [x, 1]
    else:
      self.data = x.data
      self.data[1] += 1

  def refcnt(self):
    return self.data[1]

  def done(self):
    self.data[1] -= self.decr
    self.decr = 0

  def __str__(self):
    return self.data[0]

  def __repr__(self):
    return '"%s":%d' % (self.data[0], self.data[1])

  def __len__(self):
    if self.data[1] > 1:
      return 0
    return len(self.data[0])

def ComputeKVHash(key, val):
  khash = hash(key)
  kvhash = khash + hash(val)
  return (khash, kvhash)

class KV:
  def __init__(self, key=None, val=None, seq_num=None):
    self.key_ = RefCntString(key)
    self.val_ = RefCntString(val)
    (self.khash, self.kvhash) = ComputeKVHash(str(key), str(val))
    self.seq_num = seq_num

  def done(self):
    self.key_.done()
    self.val_.done()

  def key(self):
    return str(self.key_)

  def val(self):
    return str(self.val_)

  def ByteSize(self):
    return len(self.val_) + len(self.key_)

  def __repr__(self):
    return "{(%r, %s) %r %r %r}" % \
        (repr(self.key_), repr(self.val_), self.seq_num, self.khash, self.kvhash)

class LruStorage:
  def __init__(self, max_bytes=None, max_items=None, max_seq_num=None,
               offset=None):
    self.ring = deque()
    self.byte_size = 0
    self.max_items = max_items
    self.max_bytes = max_bytes
    self.max_seq_num = max_seq_num

    self.pop_cb = None
    self.offset = offset
    if offset is None:
      self.offset = 0
    self.seq_num = self.offset

  def __repr__(self):
    return "{%s %r}" % (self.seq_num, self.ring)

  def Reserve(self, entry, item_count):
    if self.max_items == 0 or self.max_bytes == 0:
      return 0
    if self.max_items is not None:
      while len(self.ring) + item_count > self.max_items:
        if not self.PopOne():
          return  0 # can't pop one, nothing more to do.
    if self.max_bytes is not None:
      while self.byte_size + entry.ByteSize() > self.max_bytes:
        if not self.PopOne():
          return 0 # can't pop one, nothing more to do.
    return 1

  def PopOne(self):
    if not self.ring:
      return 0
    item = self.ring.popleft()
    self.byte_size -= item.ByteSize()
    item.done()
    #print "POPPING: ", item.seq_num
    if self.pop_cb is not None:
      self.pop_cb(item)
    return 1

  def Store(self, item):
    item_byte_size = item.ByteSize()
    if self.max_bytes is not None and self.byte_size + item_byte_size > self.max_bytes:
      error_string =' '.join([
        "Max bytes exceeded",
        "max bytes: %d" % self.max_bytes,
        "self.byte_size: %d" % self.byte_size,
        "item.ByteSize: %d" % item.ByteSize()])
      raise MemoryError(error_string)
    if self.max_items and (self.max_items < (len(self.ring) + 1)):
      raise MemoryError("max_items exceeded")
    item.seq_num = self.seq_num
    self.seq_num += 1
    if self.max_seq_num is not None and self.seq_num >= self.max_seq_num:
      self.seq_num = self.offset
    self.byte_size += item_byte_size
    self.ring.append(item)

  def SeqNumToIdxFromLeft(self, seq_num):
    #print "\tlen(ring): ", len(self.ring),
    first_seq_num = self.ring[0].seq_num
    if seq_num < self.offset:
      raise IndexError("Negative indices unsupported: ", seq_num)
    if first_seq_num > seq_num:
      #print " fsn: %d, sn: %d" % (first_seq_num, seq_num)
      if self.max_seq_num:
        #print " A ",
        lru_idx = (self.max_seq_num - first_seq_num) + (seq_num - self.offset)
      else:
        raise IndexError("MaxSeqNum not defined and "
                         "seq_num(%d) < first_seq_num(%d)" %
                         (seq_num, first_seq_num))
    else:
      #print " B ",
      lru_idx = seq_num - first_seq_num
    #print "idx_from_left: ", lru_idx
    return lru_idx

  def Lookup(self, seq_num):
    lru_idx = self.SeqNumToIdxFromLeft(seq_num)
    #print "Looking up: ", lru_idx
    try:
      entry = self.ring[lru_idx]
    except IndexError:
      print self.ring
      print "len(ring): ", len(self.ring)
      print "lru_idx: ", lru_idx
      print "seq_num requested:", seq_num
      print "first_seq_num:", self.ring[0].seq_num
      raise
    if entry.seq_num != seq_num:
      print "Something strange has happened"
      print "entry: ", entry
      print self.ring
      print "lru_idx: ", lru_idx
      print "seq_num requested:", seq_num
      print "first_seq_num:", self.ring[0].seq_num
      raise StandardError()
    return entry

  def FindKeyValEntries(self, key, val):
    # Looks for key/vals starting from the last entry
    (khash, kvhash) = ComputeKVHash(key, val)
    ke = None
    for i in xrange(len(self.ring) - 1, -1, -1):
      item = self.ring[i]
      if khash == item.khash and item.key() == key:
        ke = item
        if kvhash == item.kvhash and item.val() == val:
          return (item.seq_num, item.seq_num)
        for j in xrange(i - 1, -1, -1):
          item = self.ring[j]
          if kvhash == item.kvhash and item.key() == key and item.val() == val:
            return (item.seq_num, item.seq_num)
        return (ke.seq_num, None)
    return (None, None)

  def __len__(self):
    return len(self.ring)

  def __repr__(self):
    return repr(self.ring)
