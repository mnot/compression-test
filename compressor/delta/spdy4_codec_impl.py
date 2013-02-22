#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import string
import struct

from bit_bucket import BitBucket
from collections import defaultdict
from collections import deque
import common_utils
from huffman import Huffman
from optparse import OptionParser
from ..spdy_dictionary import spdy_dict
from word_freak import WordFreak

options = {}

g_default_kvs = [
    (':scheme', 'http'),
    (':scheme', 'https'),
    (':method', 'get'),
    (':path', '/'),
    (':host', ''),
    ('cookie', ''),
    (':status', '200'),
    (':status-text', 'OK'),
    (':version', '1.1'),
    ('accept', ''),
    ('accept-charset', ''),
    ('accept-encoding', ''),
    ('accept-language', ''),
    ('accept-ranges', ''),
    ('allow', ''),
    ('authorizations', ''),
    ('cache-control', ''),
    ('content-base', ''),
    ('content-encoding', ''),
    ('content-length', ''),
    ('content-location', ''),
    ('content-md5', ''),
    ('content-range', ''),
    ('content-type', ''),
    ('date', ''),
    ('etag', ''),
    ('expect', ''),
    ('expires', ''),
    ('from', ''),
    ('if-match', ''),
    ('if-modified-since', ''),
    ('if-none-match', ''),
    ('if-range', ''),
    ('if-unmodified-since', ''),
    ('last-modified', ''),
    ('location', ''),
    ('max-forwards', ''),
    ('origin', ''),
    ('pragma', ''),
    ('proxy-authenticate', ''),
    ('proxy-authorization', ''),
    ('range', ''),
    ('referer', ''),
    ('retry-after', ''),
    ('server', ''),
    ('set-cookie', ''),
    ('status', ''),
    ('te', ''),
    ('trailer', ''),
    ('transfer-encoding', ''),
    ('upgrade', ''),
    ('user-agent', ''),
    ('vary', ''),
    ('via', ''),
    ('warning', ''),
    ('www-authenticate', ''),
    ('access-control-allow-origin', ''),
    ('content-disposition', ''),
    ('get-dictionary', ''),
    ('p3p', ''),
    ('x-content-type-options', ''),
    ('x-frame-options', ''),
    ('x-powered-by', ''),
    ('x-xss-protection', ''),
    ('connection', 'keep-alive'),
    ]

# Note: Huffman coding is used here instead of range-coding or
# arithmetic-coding because of its relative CPU efficiency and because it is
# fairly well known (though the canonical huffman code is a bit less well
# known, it is still better known than most other codings)


###### BEGIN IMPORTANT PARAMS ######
#  THESE PARAMETERS ARE IMPORTANT

# If strings_use_eof is true, then the bitlen is not necessary, and possibly
#  detrimental, as it caps the maximum length of any particular string.
string_length_field_bitlen = 0

# If strings_use_eof is false, however, then string_length_field_bitlen
#  MUST be >0
strings_use_eof = 1

# If strings_padded_to_byte_boundary is true, then it is potentially faster
# (in an optimized implementation) to decode/encode, at the expense of some
# compression efficiency.
strings_padded_to_byte_boundary = 1

# if strings_use_huffman is false, then strings will not be encoded with
# huffman encoding
strings_use_huffman = 1

###### END IMPORTANT PARAMS ######

def UnpackInt(input, bitlen, huff):
  """
  Reads an int from an input BitBucket and returns it.

  'bitlen' is between 1 and 32 (inclusive), and represents the number of bits
  to be read and interpreted as the int.

  'huff' is unused.
  """
  raw_input = input.GetBits(bitlen)[0]
  rshift = 0
  if bitlen <=8:
    arg = '%c%c%c%c' % (0,0, 0,raw_input[0])
    rshift = 8 - bitlen
  elif bitlen <=16:
    arg = '%c%c%c%c' % (0,0, raw_input[0], raw_input[1])
    rshift = 16 - bitlen
  elif bitlen <=24:
    arg = '%c%c%c%c' % (0,raw_input[0], raw_input[1], raw_input[2])
    rshift = 24 - bitlen
  else:
    arg = '%c%c%c%c' % (raw_input[0], raw_input[1], raw_input[2], raw_input[3])
    rshift = 32 - bitlen
  retval = (struct.unpack('>L', arg)[0] >> rshift)
  return retval

def UnpackStr(input_data, params, huff):
  """
  Reads a string from an input BitBucket and returns it.

  'input_data' is a BitBucket containing the data to be interpreted as a string.

  'params' is (bitlen_size, use_eof, pad_to_byte_boundary, use_huffman)

  'bitlen_size' indicates the size of the length field. A size of 0 is valid IFF
  'use_eof' is true.

  'use_eof' indicates that an EOF character will be used (for ascii strings,
  this will be a null. For huffman-encoded strings, this will be the specific
  to that huffman encoding).

  If 'pad_to_byte_boundary' is true, then the 'bitlen_size' parameter
  represents bits of size, else 'bitlen_size' represents bytes.


  if 'use_huffman' is false, then the string is not huffman-encoded.

  If 'huff' is None, then the string is not huffman-encoded. If 'huff' is not
  None, then it must be a Huffman compatible object which is used to do huffman
  decoding.
  """
  (bitlen_size, use_eof, pad_to_byte_boundary, use_huffman) = params
  if not use_huffman:
    huff = None
  if not use_eof and not bitlen_size:
    # without either a bitlen size or an EOF, we can't know when the string ends
    # having both is certainly fine, however.
    raise StandardError()
  if bitlen_size:
    bitlen = UnpackInt(input_data, bitlen_size, huff)
    if huff:
      retval = huff.DecodeFromBB(input_data, use_eof, bitlen)
    else:
      retval = input_data.GetBits(bitlen)[0]
  else:  # bitlen_size == 0
    if huff:
      retval = huff.DecodeFromBB(input_data, use_eof, 0)
    else:
      retval = []
      while True:
        c = input_data.GetBits8()
        retval.append(c)
        if c == 0:
          break
  if pad_to_byte_boundary:
    input_data.AdvanceToByteBoundary()
  retval = common_utils.ListToStr(retval)
  return retval

# this assumes the bits are near the LSB, but must be packed to be close to MSB
def PackInt(data, bitlen, val, huff):
  """ Packs an int of up to 32 bits, as specified by the 'bitlen' parameter into
  the BitBucket object 'data'.
  'data' the BitBucket object into which the int is written
  'bitlen' the number of bits used for the int
  'val' the value to be packed into data (limited by bitlen)
        If val is larger than 'bitlen', the bits near the LSB are packed.
  'huff' is unused.
  """
  if bitlen <= 0 or bitlen > 32 or val != (val & ~(0x1 << bitlen)):
    print 'bitlen: ', bitlen, ' val: ', val
    raise StandardError()
  if bitlen <= 8:
    tmp_val = struct.pack('>B', val << (8 - bitlen))
  elif bitlen <= 16:
    tmp_val = struct.pack('>H', val << (16 - bitlen))
  elif bitlen <= 24:
    tmp_val = struct.pack('>L', val << (24 - bitlen))[1:]
  else:
    tmp_val = struct.pack('>L', val << (32 - bitlen))
  data.StoreBits( (common_utils.StrToList(tmp_val), bitlen) )

def PackStr(data, params, val, huff):
  """
  Packs a string into the output BitBucket ('data').
  'data' is the BitBucket into which the string will be written.
  'params' is (bitlen_size, use_eof, pad_to_byte_boundary, use_huffman)
  bitlen_size - between 0 and 32 bits. It can be zero IFF 'use_eof' is true
  use_eof - if true, the string is encoded with an EOF character. When
            use_huffman is false, this character is '\0', but when
            use_huffman is true, this character is determined by the encoder
  pad_to_byte_boundary - if true, then enough bits are written to ensure that
                         the data ends on a byte boundary.
  'val' is the string to be packed
  'huff' is the Huffman object to be used when doing huffman encoding.
  """
  (bitlen_size, use_eof, pad_to_byte_boundary, use_huffman) = params
  # if eof, then don't technically need bitlen at all...
  if not use_huffman:
    huff = None

  if not use_eof and not bitlen_size:
    # without either a bitlen size or an EOF, we can't know when the string ends
    # having both is certainly fine, however.
    raise StandardError()
  val_as_list = common_utils.StrToList(val)
  len_in_bits = len(val) * 8
  if huff:
    (val_as_list, len_in_bits) = huff.Encode(val_as_list, use_eof)
    if pad_to_byte_boundary:
      len_in_bits = len(val_as_list) *8
  if bitlen_size:
    PackInt(data, bitlen_size, len_in_bits, huff)
  data.StoreBits( (val_as_list, len_in_bits) )
  if use_eof and not huff:
    data.StoreBits([[0],8])

str_pack_params = (string_length_field_bitlen, strings_use_eof,
                   strings_padded_to_byte_boundary, strings_use_huffman)
# This is the list of things to do for each fieldtype we may be packing.
# the first param is what is passed to the pack/unpack function.
# the second and third params are the packing and unpacking functions,
# respectively.
packing_instructions = {
  'opcode'      : (  8,             PackInt, UnpackInt),
  'index'       : ( 16,             PackInt, UnpackInt),
  'index_start' : ( 16,             PackInt, UnpackInt),
  'key_idx'     : ( 16,             PackInt, UnpackInt),
  'val'         : (str_pack_params, PackStr, UnpackStr),
  'key'         : (str_pack_params, PackStr, UnpackStr),
}

def PackOps(data, packing_instructions, ops, huff, group_id):
  """ Packs (i.e. renders into wire-format) the operations in 'ops' into the
  BitBucket 'data', using the 'packing_instructions' and possibly the Huffman
  encoder 'huff'
  """
  seder = Spdy4SeDer()
  data.StoreBits(seder.SerializeInstructions(ops, packing_instructions,
                                             huff, 1234, group_id, True))

def UnpackOps(data, packing_instructions, huff):
  """
  Unpacks wire-formatted ops into an in-memory representation
  """
  seder = Spdy4SeDer()
  return seder.DeserializeInstructions(data, packing_instructions, huff)

# The order in which to format and pack operations.
packing_order = ['opcode',
                 'index',
                 'index_start',
                 'key_idx',
                 'key',
                 'val',
                 ]

# opcode-name: opcode-value list-of-fields-for-opcode
opcodes = {
    'toggl': (0x1, 'index'),
    'trang': (0x2, 'index', 'index_start'),
    'clone': (0x3,                         'key_idx', 'val'),
    'kvsto': (0x4,          'key',                    'val'),
    'eref' : (0x5,          'key',                    'val'),

    #'etoggl': (0x5, 'index'),
    #'etrang': (0x6, 'index', 'index_start'),
    #'eclone': (0x7,                         'key_idx', 'val'),
    #'ekvsto': (0x8,          'key',                    'val'),
    }

# an inverse dict of opcode-val: opcode-name list-of-fields-for-opcode
opcode_to_op = {}
for (key, val) in opcodes.iteritems():
  opcode_to_op[val[0]] = [key] + list(val[1:])

def OpcodeToVal(opcode_name):
  """ Gets the opcode-value for an opcode-name"""
  return opcodes[opcode_name][0]

def FormatOp(op):
  """ Pretty-prints an op to a string for easy human consumption"""
  order = packing_order
  outp = ['{']
  inp = []
  for key in order:
    if key in op and key != 'opcode':
      inp.append("'%s': % 5s" % (key, repr(op[key])))
    if key in op and key == 'opcode':
      inp.append("'%s': % 5s" % (key, repr(op[key]).ljust(7)))
  for (key, val) in op.iteritems():
    if key in order:
      continue
    inp.append("'%s': %s" % (key, repr(op[key])))
  outp.append(', '.join(inp))
  outp.append('}')
  return ''.join(outp)

def FormatOps(ops, prefix=None):
  """ Pretty-prints an operation or list of operations for easy human
  consumption"""
  if prefix is None:
    prefix = ''
  if isinstance(ops, list):
    for op in ops:
      print prefix,
      print FormatOp(op)
    return
  for optype in ops.iterkeys():
    for op in ops[optype]:
      print prefix,
      print FormatOp(op)


def AppendToHeaders(headers, key, val):
  if key in headers:
    headers[key] += '\0' + val
  else:
    headers[key] = val

class Spdy4SeDer(object):  # serializer deserializer
  """
  A class which serializes into and/or deserializes from SPDY4 wire format
  """
  def MutateTogglesToToggleRanges(self, instructions):
    """
    Examines the 'toggl' operations in 'instructions' and computes the
    'trang' and remnant 'toggle' operations, returning them as:
    (output_toggles, output_toggle_ranges)
    """

    toggles = sorted(instructions['toggl'])
    ot = []
    otr = []
    for toggle in toggles:
      idx = toggle['index']
      if otr and idx - otr[-1]['index'] == 1:
        otr[-1]['index'] = idx
      elif ot and idx - ot[-1]['index'] == 1:
        otr.append(ot.pop())
        otr[-1]['index_start'] = otr[-1]['index']
        otr[-1]['index'] = idx
        otr[-1]['opcode'] = 'trang'
      else:
        ot.append(toggle)
    return [ot, otr]

  def OutputOps(self, packing_instructions, huff, data, ops, opcode):
    """
    formats ops (all of type represented by opcode) into wire-format, and
    stores them into the BitBucket represented by 'data'

    'data' the bitbucket into which everything is stored
    'packing_instructions' the isntructions on how to pack fields
    'huff' a huffman object possibly used for string encoding
    'ops' the operations to be encoded into spdy4 wire format and stored.
    'opcode' the type of all of the ops.

    The general format of such is:
    | opcode-type | num-opcodes | list-of-operations
    where num-opcodes cannot exceed 256, thus the function may output
    a number of such sequences.
    """
    if not ops:
      return;
    ops_idx = 0
    ops_len = len(ops)
    while ops_len > ops_idx:
      ops_to_go = ops_len - ops_idx
      iteration_end = min(ops_to_go, 256) + ops_idx
      data.StoreBits8(OpcodeToVal(opcode))
      data.StoreBits8(min(256, ops_to_go) - 1)
      orig_idx = ops_idx
      for i in xrange(ops_to_go):
        try:
          self.WriteOpData(data, ops[orig_idx + i], huff)
        except:
          print opcode, ops
          raise
        ops_idx += 1

  def WriteOpData(self, data, op, huff):
    """
    A helper function for OutputOps which does the packing for
    the operation's fields.
    """
    for field_name in packing_order:
      if not field_name in op:
        continue
      if field_name == 'opcode':
        continue
      (params, pack_fn, _) = packing_instructions[field_name]
      val = op[field_name]
      try:
        pack_fn(data, params, val, huff)
      except:
        print field_name, data, params, val
        raise

  def WriteControlFrameStreamId(self, data, stream_id):
    if (stream_id & 0x80000000):
      abort()
    data.StoreBits32(0x80000000 | stream_id)

  def WriteControlFrameBoilerplate(self,
      data,
      frame_len,
      flags,
      stream_id,
      group_id,
      frame_type):
    """ Writes the frame-length, flags, stream-id, and frame-type
    in SPDY4 format into the bit-bucket represented bt 'data'"""
    data.StoreBits16(frame_len)
    data.StoreBits8(flags)
    #data.StoreBits32(stream_id)
    self.WriteControlFrameStreamId(data, stream_id)
    data.StoreBits8(frame_type)
    data.StoreBits8(group_id)

  def SerializeInstructions(self,
      ops,
      packing_instructions,
      huff,
      stream_id,
      group_id,
      end_of_frame):
    """ Serializes a set of instructions possibly containing many different
    type of opcodes into SPDY4 wire format, discovers the resultant length,
    computes the appropriate SPDY4 boilerplate, and then returns this
    in a new BitBucket
    """
    #print 'SerializeInstructions\n', ops
    (ot, otr) = self.MutateTogglesToToggleRanges(ops)
    #print FormatOps({'toggl': ot, 'trang': otr, 'clone': ops['clone'],
    #                 'kvsto': ops['kvsto'], 'eref': ops['eref']})

    payload_bb = BitBucket()
    self.OutputOps(packing_instructions, huff, payload_bb, ot, 'toggl')
    self.OutputOps(packing_instructions, huff, payload_bb, otr, 'trang')
    self.OutputOps(packing_instructions, huff, payload_bb, ops['clone'],'clone')
    self.OutputOps(packing_instructions, huff, payload_bb, ops['kvsto'],'kvsto')
    self.OutputOps(packing_instructions, huff, payload_bb, ops['eref'], 'eref')

    (payload, payload_len) = payload_bb.GetAllBits()
    payload_len = (payload_len + 7) / 8  # partial bytes are counted as full
    frame_bb = BitBucket()
    self.WriteControlFrameBoilerplate(frame_bb, 0, 0, 0, group_id, 0)
    boilerplate_length = frame_bb.BytesOfStorage()
    frame_bb = BitBucket()
    overall_bb = BitBucket()
    bytes_allowed = 2**16 - boilerplate_length
    while True:
      #print 'payload_len: ', payload_len
      bytes_to_consume = min(payload_len, bytes_allowed)
      #print 'bytes_to_consume: ', bytes_to_consume
      end_of_frame = (bytes_to_consume <= payload_len)
      #print 'end_of_Frame: ', end_of_frame
      self.WriteControlFrameBoilerplate(overall_bb, bytes_to_consume,
                                        end_of_frame, stream_id, group_id, 0x8)
      overall_bb.StoreBits( (payload, bytes_to_consume*8))
      payload = payload[bytes_to_consume:]
      payload_len -= bytes_allowed
      if payload_len <= 0:
        break
    return overall_bb.GetAllBits()

  def DeserializeInstructions(self, frame, packing_instructions, huff):
    """ Takes SPDY4 wire-format data and de-serializes it into in-memory
    operations
    It returns these operations.
    """
    ops = []
    bb = BitBucket()
    bb.StoreBits(frame.GetAllBits())
    flags = 0
    #print 'DeserializeInstructions'
    while flags == 0:
      frame_len = bb.GetBits16() * 8
      #print 'frame_len: ', frame_len
      flags = bb.GetBits8()
      #print 'flags: ', flags
      stream_id = bb.GetBits32()
      #print 'stream_id: ', stream_id
      frame_type = bb.GetBits8()
      #print 'frame_type: ', frame_type
      group_id = bb.GetBits8()
      #print 'group_id: ', group_id
      while frame_len > 16:  # 16 bits minimum for the opcode + count...
        bits_remaining_at_start = bb.BitsRemaining()
        opcode_val = bb.GetBits8()
        #print 'opcode_val: ', opcode_val
        op_count = bb.GetBits8() + 1
        #print 'op_count: ', op_count
        opcode_description = opcode_to_op[opcode_val]
        opcode = opcode_description[0]
        fields = opcode_description[1:]
        for i in xrange(op_count):
          op = {'opcode': opcode}
          for field_name in packing_order:
            if not field_name in fields:
              continue
            (params, _, unpack_fn) = packing_instructions[field_name]
            val = unpack_fn(bb, params, huff)
            #print val
            op[field_name] = val
            #print "BitsRemaining: %d (%d)" % (bb.BitsRemaining(), bb.BitsRemaining() % 8)
          #print "Deser %d" % (bb.NumBits() - bb.BitsRemaining())
          #print op
          ops.append(op)
        bits_consumed = (bits_remaining_at_start - bb.BitsRemaining())
        #if not bits_consumed % 8 == 0:
        #  print "somehow didn't consume whole bytes..."
        #  print "Bits consumed: %d (%d)" % (bits_consumed, bits_consumed % 8)
        #  raise StandardError()
        frame_len -= bits_consumed
    #print 'ops: ', ops
    return (group_id, ops)

class HeaderGroup(object):
  """ A HeaderGroup is a list of ValueEntries (VEs) which are the key-values to
  be instantiated as a header frame """
  def __init__(self):
    self.hg_store = set()

  def Empty(self):
    return not self.hg_store

  def RemoveEntry(self, v_idx):
    try:
      self.hg_store.remove(v_idx)
    except KeyError:
      pass

  def Toggle(self, v_idx):
    self.hg_store.symmetric_difference_update([v_idx])

  def __repr__(self):
    return repr(self.hg_store)

#Note that this class mutates the things that are stored within...
class LRU(object):
  class Node(object):
    def __init__(self):
      self.n = None
      self.p = None
      self.d = None
  def __init__(self):
    self.first = None
    self.last = None

  def __getitem__(self, idx):
    if idx == 0 and self.first is not None:
      return self.first
    c = self.first
    for i in xrange(idx):
      c = c.n
    return c

  def remove(self, item):
    if item == self.first:
      self.first = item.n
    if item == self.last:
      self.last = item.p
    if item.p:
      item.p.n = item.n
    if item.n:
      item.n.p = item.p

  def append(self, item):
    if self.last is not None:
      self.last.n = item
    item.n = None
    item.p = self.last
    self.last = item
    if self.first is None:
      self.first = item


class Storage(object):
  """ This object keeps track of key and LRU ids, all keys and values, and the
  mechanism for expiring key/value entries as necessary"""
  class KE(object):
    def __init__(self, key_idx, key):
      self.key_ = key
      self.key_idx = key_idx
      self.ref_cnt = 0
      self.val_map = {}

    def key(self):
      return self.key_

    def __repr__(self):
      return repr({'key_idx': self.lru_idx, 'key': self.key_,
                   'ref_cnt': self.ref_cnt, 'val_map': self.val_map})

  class VE(object):
    def __init__(self, key, val, ke):
      self.lru_idx = None
      self.key_ = key
      self.val_ = val
      self.ke = ke
      self.groups = set()

    def key(self):
      return self.key_

    def val(self):
      return self.val_

    def __repr__(self):
      return repr({'lru_idx': self.lru_idx, 'key': self.key_,
                   'val': self.val_, 'ke':id(self.ke)})
  def __init__(self, max_byte_size, max_entries):
    self.key_map = {}
    self.key_ids = common_utils.IDStore(2**16)
    self.lru_ids = common_utils.IDStore(2**16)
    self.state_size = 0
    self.num_vals = 0
    self.max_vals = max_entries
    self.max_state_size = max_byte_size
    self.pinned = None
    self.remove_val_cb = None
    #self.lru = deque()
    self.lru = LRU()
    self.lru_idx_to_ve = {}
    self.key_idx_to_ke = {}

    for (k, v) in g_default_kvs:
      ke = self.FindKeyEntry(key)
      if ke is None:
        self.key_map[key] = ke = self.NewKE(key)
      ke.val_map[val] = ve = self.NewVE(key, val, ke)
      ve.lru_idx = lru_idx = self.GetNextUnusedLruId()
      self.lru_idx_to_ve[lru_idx] = ve
      self.lru_ids.minimum_id = lru_idx

  def PopOne(self):  ####
    if not self.lru:
      return None
    ve = self.lru[0]
    if self.remove_val_cb:
      self.remove_val_cb(ve)
    self.RemoveVal(ve)
    return 1

  def MakeSpace(self, space_required, adding_val):  ####
    """
    Makes enough space for 'space_required' new bytes and 'adding_val' new val
    entries by popping elements from the LRU (using PopOne)
    """
    while self.num_vals + adding_val > self.max_vals:
      if not self.PopOne():
        return
    while self.state_size + space_required > self.max_state_size:
      if not PopOne():
        return

  def FindKeyEntry(self, key): ####
    if key in self.key_map:
      return self.key_map[key]
    return None

  def FindKeyByKeyIdx(self, key_idx):
    return self.key_idx_to_ke.get(key_idx, None)

  def IncrementRefCnt(self, ke): ####
    ke.ref_cnt += 1

  def DecrementRefCnt(self, ke): ####
    ke.ref_cnt -= 1

  def NewKE(self, key): ####
    key_idx = self.GetNextUnusedKeyId()
    return Storage.KE(key_idx, key)

  def NewVE(self, key, val, ke):  ####
    return Storage.VE(key, val, ke)

  def FindOrAddKey(self, key): ####
    ke = self.FindKeyEntry(key)
    if ke is not None:
      return ke
    self.MakeSpace(len(key), 0)
    self.key_map[key] = ke = self.NewKE(key)
    key_idx = ke.key_idx
    if key_idx in self.key_idx_to_ke:
      raise StandardError()
    self.key_idx_to_ke[key_idx] = ke
    self.state_size += len(key)
    return ke

  def InsertVal(self, key, val): ####
    ke = self.FindOrAddKey(key)
    if ke.val_map.get(val, None) is not None:
      return None
    self.IncrementRefCnt(ke)
    self.MakeSpace(len(val), 1)
    self.num_vals += 1
    ke.val_map[val] = ve = self.NewVE(key, val, ke)
    self.DecrementRefCnt(ke)
    return ve

  def GetNextUnusedLruId(self):
    return Storage.GetNextUnusedId(self.lru_ids, self.lru_idx_to_ve)

  def GetNextUnusedKeyId(self):
    return Storage.GetNextUnusedId(self.key_ids, self.key_idx_to_ke)

  @staticmethod
  def GetNextUnusedId(idstore, mapdata):
    first_idx = idx = idstore.GetNext()
    while 1:
      if idx in mapdata:
        idx = idstore.GetNext()
        if idx == first_idx:
          print "Apparently ALL IDs are in use"
          raise StandardError()
        continue
      break
    return idx

  def AddToHeadOfLRU(self, ve): ####
    if ve.lru_idx >= 0:
      raise StandardError()
    if ve is not None:
      lru_idx = self.GetNextUnusedLruId()
      ve.lru_idx = lru_idx
      self.lru_idx_to_ve[lru_idx] = ve
      #print "Appending %d ve to LRU: " % lru_idx, ve
      self.lru.append(ve)

  def LookupFromIdx(self, lru_idx):
    return self.lru_idx_to_ve.get(lru_idx, None)

  def MoveToHeadOfLRU(self, ve):  ####
    try:
      self.lru.remove(ve)
      self.lru.append(ve)
    except:
      pass

  def RemoveFromLRU(self, ve): ####
    self.lru.remove(ve)
    lru_idx = ve.lru_idx
    del self.lru_idx_to_ve[lru_idx]
    ve.lru_idx = None

  def RemoveFromValMap(self, ve): ####
    self.state_size -= len(ve.val())
    self.num_vals -= 1
    del ve.ke.val_map[ve.val()]

  def MaybeRemoveFromKeyMap(self, ke): ####
    if not ke or len(ke.val_map) > 0 or ke.ref_cnt > 0:
      return
    self.state_size -= len(ke.key())

  def RemoveVal(self, ve): ####
    self.RemoveFromLRU(ve)
    self.RemoveFromValMap(ve)
    self.MaybeRemoveFromKeyMap(ve.ke)

  def SetRemoveValCB(self, cb): ####
    self.remove_val_cb = cb

  def FindValEntry(self, ke, val): ####
    if ke is None:
      return None
    return ke.val_map.get(val, None)

  def __repr__(self):
    retval = []
    for item in self.lru:
      if item is not None:
        retval.append("%r" % item)
      else:
        retval.append("(None)")

    return '\n'.join(retval)



class Spdy4CoDe(object):
  def __init__(self, params):
    param_dict = {}
    for param in params:
      kv = param.split('=')
      if len(kv) > 1:
        param_dict[kv[0]] = '='.join(kv[1:])
      else:
        param_dict[kv[0]] = None

    max_byte_size = 16*1024
    max_entries = 4096

    if 'max_byte_size' in param_dict:
      max_byte_size = int(param_dict['max_byte_size'])
    if 'max_entries' in param_dict:
      max_entries = int(param_dict['max_entries'])

    self.options = options
    self.header_groups = {}
    self.huffman_table = None
    self.wf = WordFreak()
    self.storage = Storage(max_byte_size, max_entries)
    def RemoveVEFromAllHeaderGroups(ve):
      for group_id in ve.groups:
        header_group = self.header_groups[group_id]
        header_group.RemoveEntry(ve.lru_idx)

    self.storage.SetRemoveValCB(RemoveVEFromAllHeaderGroups)

  def OpsToRealOps(self, in_ops, header_group):
    """ Packs in-memory format operations into wire format"""
    data = BitBucket()
    PackOps(data, packing_instructions, in_ops, self.huffman_table, header_group)
    return common_utils.ListToStr(data.GetAllBits()[0])

  def RealOpsToOps(self, realops):
    """ Unpacks wire format operations into in-memory format"""
    bb = BitBucket()
    bb.StoreBits((common_utils.StrToList(realops), len(realops)*8))
    return UnpackOps(bb, packing_instructions, self.huffman_table)

  def Compress(self, realops):
    """ basically does nothing"""
    ba = ''.join(realops)
    return ba

  def Decompress(self, op_blob):
    """ basically does nothing"""
    return op_blob

  def MakeToggl(self, index):
    return {'opcode': 'toggl', 'index': index}

  def MakeKvsto(self, key, val):
    return {'opcode': 'kvsto', 'val': val, 'key': key}

  def MakeClone(self, key_idx, val):
    return {'opcode': 'clone', 'val': val, 'key_idx': key_idx}

  def MakeERef(self, key, value):
    return {'opcode': 'eref', 'key': key, 'val': value}

  def FindOrMakeHeaderGroup(self, group_id):
    try:
      return self.header_groups[group_id]
    except KeyError:
      self.header_groups[group_id] = HeaderGroup()
      return self.header_groups[group_id]

  def RenumberVELruIdx(self, ve, group_id):
    v_idx = ve.lru_idx
    removals = []
    for group_id in ve.groups:
      header_group = self.header_groups[group_id]
      header_group.RemoveEntry(v_idx)
    ve.groups.clear()
    ve.groups.add(group_id)
    del self.storage.lru_idx_to_ve[v_idx]
    new_lru_idx = ve.lru_idx = self.storage.GetNextUnusedLruId()
    self.storage.lru_idx_to_ve[new_lru_idx] = ve
    self.header_groups[group_id].hg_store.add(new_lru_idx)
    #print "Renumbering: %d to %d " % (lru_idx, new_lru_idx)

  def AdjustHeaderGroupEntries(self, group_id):
    """ Moves elements which have been referenced/modified to the head of the LRU
    and possibly renumbers them"""
    header_group = self.header_groups[group_id]
    #print "Adjust b4: ", self.header_groups[group_id].hg_store
    for ve in [self.storage.LookupFromIdx(x) for x in sorted(header_group.hg_store)]:
      self.storage.MoveToHeadOfLRU(ve)
      self.RenumberVELruIdx(ve, group_id)
    #print "Adjust af: ", self.header_groups[group_id].hg_store


  def MakeOperations(self, headers, group_id):
    """ Computes the entire set of operations necessary to encode the 'headers'
    for header-group 'group_id'
    """
    instructions = {'toggl': [], 'clone': [], 'kvsto': [], 'eref': []}
    self.FindOrMakeHeaderGroup(group_id)  # make the header group if necessary

    headers_set = set()
    keep_set = set()
    done_set = set()
    for k, v in headers.iteritems():
      if k == 'cookie':
        splitlist = [x.strip(' ') for x in v.split(';')]
      else:
        splitlist = [x.strip(' ') for x in v.split('\0')]
      for elem in splitlist:
        headers_set.add( (k, elem) )

    for idx in self.header_groups[group_id].hg_store:
      entry = self.storage.LookupFromIdx(idx)
      kv = (entry.key() , entry.val() )
      if kv in headers_set:
        # keep it.
        keep_set.add(idx)
        headers_set.remove(kv)
      else:
        done_set.add(idx)
    #print "keep_set: ", sorted(keep_set)
    #print "done_set: ", sorted(done_set)
    #print "tbd_set: ", repr(headers_set)
    toggls = set()
    clones = []
    kvstos = []
    erefs = []

    for kv in headers_set:
      (key, val) = kv
      if key in [":path", "referer"]:
        erefs.append( (key, val) )
        continue
      k_idx = None
      v_idx = None

      ke = self.storage.FindKeyEntry(key)
      if ke is not None:
        k_idx = ke.key_idx

      ve = self.storage.FindValEntry(ke, val)
      if ve is not None:
        v_idx = ve.lru_idx

      if v_idx is not None:
        # a new toggle.
        toggls.add(v_idx)
      elif k_idx is not None:
        clones.append( (k_idx, val) )
        # a new clone
      else:
        # kvsto
        kvstos.append( (key, val) )
    #def Cleanup(x):
    #  y = dict(x)
    #  del y['ke']
    #  return y
    #print "   keeping on: \n\t\t\t", '\n\t\t\t'.join(
    #    [repr((x, Cleanup(self.storage.LookupFromIdx(x)))) for x in keep_set])
    #print "new toggls on: \n\t\t\t", '\n\t\t\t'.join(
    #    [repr((x, Cleanup(self.storage.LookupFromIdx(x)))) for x in toggls])
    #print "       clones: \n\t\t\t", '\n\t\t\t'.join([repr(x) for x in clones])
    #print "       kvstos: \n\t\t\t", '\n\t\t\t'.join([repr(x) for x in kvstos])


    full_toggl_list = toggls.union(done_set)
    for idx in full_toggl_list:
      instructions['toggl'].append(self.MakeToggl(idx))

    for (idx, val) in clones:
      op = self.MakeClone(idx, val)
      instructions['clone'].append(self.MakeClone(idx, val))

    for (idx, val) in kvstos:
      op = self.MakeKvsto(idx, val)
      instructions['kvsto'].append(op)

    for (key, val) in erefs:
      op = self.MakeERef(key, val)
      instructions['eref'].append(op)

    output_instrs = instructions['toggl'] + \
                    instructions['clone'] + instructions['kvsto'] + \
                    instructions['eref']
    #print FormatOps(output_instrs)

    #print "storage befor exe: ", self.storage.lru_storage.ring
    self.DecompressorExecuteOps(output_instrs, group_id)
    #print "storage after exe: ", self.storage.lru_storage.ring
    self.AdjustHeaderGroupEntries(group_id)

    #print self.storage.lru_storage.ring
    #print "CMP HGaf:", sorted(self.header_groups[group_id].hg_store)


    #print "Done making operations"
    #print '#' * 8
    return instructions

  def RealOpsToOpAndExecute(self, realops):
    """ Deserializes from SPDY4 wire format and executes the operations"""
    (group_id, ops) = self.RealOpsToOps(realops)
    self.FindOrMakeHeaderGroup(group_id)  # make the header group if necessary
    headers = self.DecompressorExecuteOps(ops, group_id)
    self.AdjustHeaderGroupEntries(group_id)
    return (group_id, ops, headers)

  def DoToggle(self, group_id, idx):
    if type(idx) == Storage.VE:
      ve = idx
      idx = ve.lru_idx
    else:
      ve = self.storage.LookupFromIdx(idx)
    if group_id in ve.groups:
      ve.groups.remove(group_id)
    else:
      ve.groups.add(group_id)
    self.header_groups[group_id].Toggle(idx)

  def DecompressorExecuteOps(self, ops, group_id):
    def MaybeAddTurnon(idx, addme):
      if not idx in self.header_groups[group_id].hg_store:
        addme.add(idx)

    header_group = self.FindOrMakeHeaderGroup(group_id)
    headers = {}
    turnons = set()
    for op in ops:
      if op['opcode'] == 'toggl':
        MaybeAddTurnon(op['index'], turnons)
      elif op['opcode'] == 'trang':
        for i in xrange(op['index_start'], op['index']+1):
          MaybeAddTurnon(i, turnons)

    for idx in turnons:
      ve = self.storage.LookupFromIdx(idx)
      #print "TRNON %d: %s: %s" % (idx, ve.key(), ve.val())
      AppendToHeaders(headers, ve.key(), ve.val())

    kvs_to_store = []
    for op in ops:
      opcode = op['opcode']
      if opcode == 'toggl':
        self.DoToggle(group_id, op['index'])
      elif opcode == 'trang':
        for i in xrange(op['index_start'], op['index']+1):
          self.DoToggle(group_id, i)
      elif opcode == 'clone':
        ke = self.storage.FindKeyByKeyIdx(op['key_idx'])
        kvs_to_store.append( (ke.key_, op['val']) )
      elif opcode == 'kvsto':
        kvs_to_store.append( (op['key'], op['val']) )
      elif opcode == 'eref':
        AppendToHeaders(headers, op['key'], op['val'])

    # now actually make the state changes to the LRU
    for kv in kvs_to_store:
      ve = self.storage.InsertVal(kv[0], kv[1])
      #print "Stored: %r" % ve
      if ve is None:
        continue
      self.storage.AddToHeadOfLRU(ve)
      self.DoToggle(group_id, ve)
    # and now instantiate the stuff from header_group which we haven't
    # yet instantiated.
    #uninstantiated = turnons.difference(header_group.hg_store)
    #print "turnons: ", turnons
    #print "hg_store: ", self.header_groups[group_id].hg_store
    uninstantiated = self.header_groups[group_id].hg_store.difference(turnons)
    #print "uninstantiated entries: ", uninstantiated
    for idx in uninstantiated:
      ve = self.storage.LookupFromIdx(idx)
      #print "XXXXXXXXXXXXXX UNINST %r:" % idx,
      #print "%s: %s" % (ve.key(), ve.val())
      AppendToHeaders(headers, ve.key(), ve.val())
    if 'cookie' in headers:
      headers['cookie'] = headers['cookie'].replace('\0', '; ')
    #print repr(self.storage)

    return headers

