#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import string
import struct
import copy

from bit_bucket import BitBucket
from collections import defaultdict
from collections import deque
import common_utils
from huffman import Huffman
from optparse import OptionParser
from word_freak import WordFreak
import lrustorage

g_default_kvs = [
    (':scheme', 'http'),
    (':path', '/'),
    (':method', 'get'),
    (':scheme', 'https'),
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
g_string_length_field_bitlen = 0

# If strings_use_eof is false, however, then g_string_length_field_bitlen
#  MUST be >0
g_strings_use_eof = 1

# If strings_padded_to_byte_boundary is true, then it is potentially faster
# (in an optimized implementation) to decode/encode, at the expense of some
# compression efficiency.
g_strings_padded_to_byte_boundary = 1

# if strings_use_huffman is false, then strings will not be encoded with
# huffman encoding
g_strings_use_huffman = 1

###### END IMPORTANT PARAMS ######

def UnpackInt8(inp_stream, bitlen, huff):
  return inp_stream.GetBits8()

def UnpackInt16(inp_stream, bitlen, huff):
  return inp_stream.GetBits16()

def UnpackInt32(inp_stream, bitlen, huff):
  return inp_stream.GetBits32()

def UnpackInt(inp_stream, bitlen, huff):
  """
  Reads an int from an input BitBucket and returns it.

  'bitlen' is between 1 and 32 (inclusive), and represents the number of bits
  to be read and interpreted as the int.

  'huff' is unused.
  """
  raw_in_stream = inp_stream.GetBits(bitlen)[0]
  rshift = 0
  if bitlen <= 8:
    arg = '%c%c%c%c' % (0,0, 0,raw_in_stream[0])
    rshift = 8 - bitlen
  elif bitlen <= 16:
    arg = '%c%c%c%c' % (0,0, raw_in_stream[0], raw_in_stream[1])
    rshift = 16 - bitlen
  elif bitlen <= 24:
    arg = '%c%c%c%c' % (0,raw_in_stream[0], raw_in_stream[1], raw_in_stream[2])
    rshift = 24 - bitlen
  else:
    arg = '%c%c%c%c' % (raw_in_stream[0], raw_in_stream[1],
                        raw_in_stream[2], raw_in_stream[3])
    rshift = 32 - bitlen
  retval = (struct.unpack('>L', arg)[0] >> rshift)
  return retval

def UnpackVarInt(inp_stream, bitlen, huff):
  # unpacks a varint encoded int.
  val = inp_stream.GetBits4()
  if val < 0x0f:
    return val

  val = inp_stream.GetBits8()
  if val < 0xff:
    return val

  val = inp_stream.GetBits16()
  if val < 0xffff:
    return val

  val = inp_stream.GetBits32()
  return val

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
        if c == 0:
          break
        retval.append(c)
  if pad_to_byte_boundary:
    input_data.AdvanceReadPtrToByteBoundary()
  return common_utils.ListToStr(retval)

# this assumes the bits are near the LSB, but must be packed to be close to MSB
def PackInt8(data, bitlen, val, huff):
  data.StoreBits8(val)

def PackInt16(data, bitlen, val, huff):
  data.StoreBits16(val)

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

def PackVarInt(data, bitlen, val, huff):
  if val < 0x0f:
    data.StoreBits4(val)
    return
  data.StoreBits4(0x0f)

  if val < 0xff:
    data.StoreBits8(val)
    return
  data.StoreBits8(0xff)

  if val < 0xffff:
    data.StoreBits16(val)
    return
  data.StoreBits16(0xffff)

  data.StoreBits32(val)

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

g_str_pack_params = (g_string_length_field_bitlen, g_strings_use_eof,
                   g_strings_padded_to_byte_boundary, g_strings_use_huffman)
del g_string_length_field_bitlen
del g_strings_use_eof
del g_strings_padded_to_byte_boundary
del g_strings_use_huffman
# This is the list of things to do for each fieldtype we may be packing.
# the first param is what is passed to the pack/unpack function.
# the second and third params are the packing and unpacking functions,
# respectively.
g_default_packing_instructions = {
  'opcode'      : (    8,             PackInt8 , UnpackInt8),
  'index'       : (   16,             PackInt16, UnpackInt16),
  'index_start' : (   16,             PackInt16, UnpackInt16),
  'val'         : (g_str_pack_params, PackStr  , UnpackStr),
  'key'         : (g_str_pack_params, PackStr  , UnpackStr),
}

def PackOps(data, packing_instructions, ops, huff, group_id, verbose):
  """ Packs (i.e. renders into wire-format) the operations in 'ops' into the
  BitBucket 'data', using the 'packing_instructions' and possibly the Huffman
  encoder 'huff'
  """
  seder = Spdy4SeDer()
  data.StoreBits(seder.SerializeInstructions(ops, packing_instructions,
                                             huff, 1234, group_id, True,
                                             verbose))

def UnpackOps(data, packing_instructions, huff):
  """
  Unpacks wire-formatted ops into an in-memory representation
  """
  seder = Spdy4SeDer()
  return seder.DeserializeInstructions(data, packing_instructions, huff)

# The order in which to format and pack operations.
g_packing_order = ['opcode',
                 'index',
                 'index_start',
                 'key',
                 'val',
                 ]

# opcode-name: opcode-value list-of-fields-for-opcode
g_opcodes = {
    'stoggl': (0x0, 'index'),
    'etoggl': (0x1, 'index'),
    'strang': (0x2, 'index', 'index_start'),
    'etrang': (0x3, 'index', 'index_start'),
    'sclone': (0x4, 'index', 'val'),
    'eclone': (0x5, 'index', 'val'),
    'skvsto': (0x6,   'key', 'val'),
    'ekvsto': (0x7,   'key', 'val'),
    }

# an inverse dict of opcode-val: opcode-name list-of-fields-for-opcode
g_opcode_to_op = {}
for (key, val) in g_opcodes.iteritems():
  g_opcode_to_op[val[0]] = [key] + list(val[1:])
del key
del val

def OpcodeToVal(opcode_name):
  """ Gets the opcode-value for an opcode-name"""
  return g_opcodes[opcode_name][0]

def FormatOp(op):
  """ Pretty-prints an op to a string for easy human consumption"""
  order = g_packing_order
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
  output = []
  if isinstance(ops, list):
    for op in ops:
      output.append(prefix)
      output.extend(FormatOp(op))
      output.append('\n');
    return ''.join(output)
  for optype in ops.iterkeys():
    for op in ops[optype]:
      output.append(prefix)
      output.extend(FormatOp(op))
      output.append('\n');
  return ''.join(output)

def AppendToHeaders(headers, key, val):
  if key in headers:
    headers[key] += '\0' + val
  else:
    headers[key] = val

def PrintHex(output_bytes):
  output_bytes_len = len(output_bytes)
  for i in xrange(0, output_bytes_len, 16):
    last_byte = min(i+16, output_bytes_len)
    line = output_bytes[i:last_byte]
    to_hex = lambda x: ' '.join(['{:02X}'.format(i) for i in x])
    to_str = lambda x: ''.join([31 < i < 127 and chr(i) or '.' for i in x])
    print '{:47} | {}'.format(to_hex(line), to_str(line))
  print

class Stats:
  class HeaderStat:
    def __init__(self, length):
      self.count = 1
      self.vlen = length
    def __repr__(self):
      return "{'c': %d, 'vlen': %d}" % (self.count, self.vlen)
  class HeaderBytesSentStat:
    def __init__(self, klen, vlen):
      self.count = 1
      self.klen = klen
      self.vlen = vlen

    def __repr__(self):
      return "{'c': %d, 'klen': %d, 'vlen': %d}" % (self.count,
          self.klen, self.vlen)

  def __init__(self):
    # key, {count, vlen}
    self.raw_header_stats = {}
    # key, {count, key_bytes_saved, v_bytes_saved}
    self.header_bytes_sent_stats = {}
    # opcode, {count, {histogram of fieldcount}}
    self.op_stats = {}
    # histogram of dist-from-end
    self.idx_stats = {}

  def __str__(self):
    return '\n'.join(["raw_header_stats=" + repr(self.raw_header_stats),
      "header_bytes_sent_stats=" + repr(self.header_bytes_sent_stats),
      "op_stats=" + repr(self.op_stats),
      "idx_stats=" + repr(self.idx_stats)])

  def DistFromNewest(self, storage, seq_num):
    if seq_num < storage.lru_storage.offset:
      return -1
    first_seq_num = storage.lru_storage.ring[0].seq_num
    if first_seq_num > seq_num:
      if storage.lru_storage.max_seq_num:
        lru_idx = (storage.lru_storage.max_seq_num - first_seq_num) + \
                  (seq_num - storage.lru_storage.offset)
    else:
      lru_idx = seq_num - first_seq_num
    return len(storage.lru_storage.ring) - lru_idx

  def Process(self, storage, headers, ops):
    def AddHeaderByteSentStats(key, klen, vlen):
      try:
        self.header_bytes_sent_stats[key].count += 1
        self.header_bytes_sent_stats[key].vlen += vlen
        self.header_bytes_sent_stats[key].klen += klen
      except:
        self.header_bytes_sent_stats[key] = Stats.HeaderBytesSentStat(klen,
                                                                      vlen)
    ##
    opcounts = {'stoggl': 0, 'etoggl': 0,
                'strang': 0, 'etrang': 0,
                'sclone': 0, 'eclone': 0,
                'skvsto': 0, 'ekvsto': 0}

    for k,v in headers.iteritems():
      nulls = 0
      for i in v:
        if i == '\0':
          nulls += 1
      try:
        self.raw_header_stats[k].count += 1 + nulls
        self.raw_header_stats[k].vlen += len(v) - nulls
      except:
        self.raw_header_stats[k] = Stats.HeaderStat(len(v) - nulls)
        self.raw_header_stats[k].count += nulls

    # process distances from the end and construct op fieldcounts
    # for this set of ops.
    for op in ops:
      opcode = op['opcode']
      opcounts[opcode] += 1
      # handle counting bytes sent.
      if opcode[1:] == 'clone':
        idx = op['index']
        kv = storage.LookupFromIdx(idx)
        AddHeaderByteSentStats(kv.key(), 0, len(op['val']))
      elif opcode[1:] == 'kvsto':
        AddHeaderByteSentStats(op['key'], len(op['key']), len(op['val']))

      for name in ['index', 'index_start']:
        if name in op:
          idx = op[name]
          try:
            self.idx_stats[self.DistFromNewest(storage, idx)] += 1
          except:
            self.idx_stats[self.DistFromNewest(storage, idx)] = 1

    # Now deal with operation field count frequencies.
    for k in opcounts.keys():
      if not k in self.op_stats:
        self.op_stats[k] = {}
    for k,v in opcounts.iteritems():
      self.op_stats[k].__setitem__(v, self.op_stats[k].get(v,0) + 1)

g_stats = Stats()


class Spdy4SeDer(object):  # serializer deserializer
  """
  A class which serializes into and/or deserializes from SPDY4 wire format
  """
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
      ops_to_go = min(ops_len - ops_idx, 16)

      opcode_val = OpcodeToVal(opcode)
      opcode_val_and_op_count = (opcode_val << 4| (ops_to_go-1) & 0x0f)
      data.StoreBits8(opcode_val_and_op_count)

      for i in xrange(ops_to_go):
        try:
          self.WriteOpData(data, ops[ops_idx], huff, packing_instructions)
        except:
          print opcode, ops
          raise
        ops_idx += 1

  def WriteOpData(self, data, op, huff, packing_instructions):
    """
    A helper function for OutputOps which does the packing for
    the operation's fields.
    """
    for field_name in g_packing_order:
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
    data.StoreBits8(frame_type)
    data.StoreBits8(flags)
    self.WriteControlFrameStreamId(data, stream_id)
    data.StoreBits8(group_id)

  def SerializeInstructions(self,
      ops,
      packing_instructions,
      huff,
      stream_id,
      group_id,
      end_of_frame,
      verbose):
    """ Serializes a set of instructions possibly containing many different
    type of opcodes into SPDY4 wire format, discovers the resultant length,
    computes the appropriate SPDY4 boilerplate, and then returns this
    in a new BitBucket
    """
    #print 'SerializeInstructions\n', ops
    if verbose >= 5:
      print
      print "stream_id: %s group_id: %s" % (stream_id, group_id)
      print FormatOps(ops)
      print

    payload_bb = BitBucket()
    for opcode, oplist in ops.iteritems():
      self.OutputOps(packing_instructions, huff, payload_bb, oplist, opcode)

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
    if verbose >= 5:
      PrintHex(overall_bb.GetAllBits()[0])

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
      frame_len = bb.GetBits16() * 8 # in bits
      #print 'frame_len: ', frame_len
      frame_type = bb.GetBits8()
      #print 'frame_type: ', frame_type
      flags = bb.GetBits8()
      #print 'flags: ', flags
      stream_id = bb.GetBits32()
      #print 'stream_id: ', stream_id
      group_id = bb.GetBits8()
      #print 'group_id: ', group_id
      while frame_len > 8:
        bits_remaining_at_start = bb.BitsRemaining()
        try:
          opcode_val_and_op_count = bb.GetBits8()
          opcode_val = opcode_val_and_op_count >> 4
          op_count = (opcode_val_and_op_count & 0x0f) + 1
          opcode_description = g_opcode_to_op[opcode_val]
          opcode = opcode_description[0]
          fields = opcode_description[1:]
          for i in xrange(op_count):
            op = {'opcode': opcode}
            for field_name in g_packing_order:
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
        except:
          break
    #print 'ops: ', ops
    return (group_id, ops)

class HeaderGroup(object):
  """ A HeaderGroup is a list of ValueEntries (VEs) which are the key-values to
  be instantiated as a header frame """
  def __init__(self):
    self.hg_store = set()

  def Empty(self):
    return not self.hg_store

  def TouchEntry(self, v_idx):
    if v_idx is None:
      raise StandardError()
    self.hg_store.add(v_idx)

  def RemoveEntry(self, v_idx):
    try:
      self.hg_store.remove(v_idx)
    except KeyError:
      pass

  def Toggle(self, v_idx):
    self.hg_store.symmetric_difference_update([v_idx])

  def __repr__(self):
    return repr(self.hg_store)

class Storage(object):
  """ This object keeps track of key and LRU ids, all keys and values, and the
  mechanism for expiring key/value entries as necessary"""
  def __init__(self, max_byte_size, max_entries, max_index_size):
    self.static_storage = lrustorage.LruStorage()
    for k,v in g_default_kvs:
      self.static_storage.Store(lrustorage.KV(k,v))
    self.lru_storage = lrustorage.LruStorage(max_byte_size,
                                             max_entries,
                                             max_index_size,
                                             len(self.static_storage))

  def SetRemoveValCB(self, remove_val_cb):
    self.lru_storage.pop_cb = remove_val_cb

  def LookupFromIdx(self, entry_seqnum):
    if entry_seqnum < len(self.static_storage):
      return self.static_storage.Lookup(entry_seqnum)
    return self.lru_storage.Lookup(entry_seqnum)

  def InsertVal(self, entry):
    if self.lru_storage.Reserve(entry, 1):
      self.lru_storage.Store(entry)
      return self.lru_storage.ring[-1].seq_num
    return None

  def FindEntryIdx(self, key, val):
    retval = [None, None]
    (ke, ve) = self.lru_storage.FindKeyValEntries(key, val)
    if ke is not None:
      retval[0] = ke.seq_num
      if ve is not None:
        retval[1] = ve.seq_num
      else:
        (__, ve) = self.static_storage.FindKeyValEntries(key, val)
        if ve is not None:
          retval[1] = ve.seq_num
    else:
      (ke, ve) = self.static_storage.FindKeyValEntries(key, val)
      if ke is not None:
        retval[0] = ke.seq_num
      if ve is not None:
        retval[1] = ve.seq_num
    #print "\t\tLooking for(%s, %s): found at: (%r, %r)" % \
    #    (key, val, retval[0], retval[1])
    return retval

  def __repr__(self):
    return repr(self.lru_storage)

def IsTrueWithDefault(param_dict, key, default):
  if not key in param_dict or param_dict[key] is None:
    return default
  string = param_dict[key]
  if (string == "True" or
      string == "true" or
      string == '1' or
      string == 't'):
    return 1
  return 0

class Spdy4CoDe(object):
  def __init__(self, params, description, options):
    self.description = description
    self.packing_instructions = copy.deepcopy(g_default_packing_instructions)
    param_dict = {}
    for param in params:
      kv = param.split('=')
      if len(kv) > 1:
        param_dict[kv[0]] = '='.join(kv[1:])
      else:
        param_dict[kv[0]] = None

    max_byte_size = 4*1024
    max_index = 2**16 - 1
    max_entries = 1024


    if 'max_byte_size' in param_dict:
      max_byte_size = int(param_dict['max_byte_size'])
    if 'max_entries' in param_dict:
      max_entries = min(max_index - len(g_default_kvs),
                        int(param_dict['max_entries']))
    if IsTrueWithDefault(param_dict, 'small_index', True):
      self.packing_instructions['index']       = (8, PackInt8, UnpackInt8);
      self.packing_instructions['index_start'] = (8, PackInt8, UnpackInt8);

      max_index = 256 - 1
      max_entries = min(max_index - len(g_default_kvs), max_entries)

    if IsTrueWithDefault(param_dict, 'varint_encoding', False):
      self.packing_instructions['index']       = (8, PackVarInt, UnpackVarInt);
      self.packing_instructions['index_start'] = (8, PackVarInt, UnpackVarInt);

    self.hg_adjust =       IsTrueWithDefault(param_dict, 'hg_adjust', False)
    self.implicit_hg_add = IsTrueWithDefault(param_dict, 'implicit_hg_add', False)
    self.refcnt_vals =     IsTrueWithDefault(param_dict, 'refcnt_vals', False)
    self.only_etoggles =   IsTrueWithDefault(param_dict, 'only_etoggles', False)

    self.options = options
    self.header_groups = {}
    self.huffman = None
    #self.wf = WordFreak()  # for figuring out the letter freq counts
    self.storage = Storage(max_byte_size, max_entries, max_index)
    def RemoveVIdxFromAllHeaderGroups(entry):
      v_idx = entry.seq_num
      to_be_removed = []
      for group_id, header_group in self.header_groups.iteritems():
        header_group.RemoveEntry(v_idx)
        if header_group.Empty():
          to_be_removed.append(group_id)
      for group_id in to_be_removed:
        del self.header_groups[group_id]

    self.storage.SetRemoveValCB(RemoveVIdxFromAllHeaderGroups)

  def OpsToRealOps(self, in_ops, header_group):
    """ Packs in-memory format operations into wire format"""
    data = BitBucket()
    PackOps(data, self.packing_instructions, in_ops, self.huffman,
        header_group, self.options.verbose)
    return common_utils.ListToStr(data.GetAllBits()[0])

  def RealOpsToOps(self, realops):
    """ Unpacks wire format operations into in-memory format"""
    bb = BitBucket()
    bb.StoreBits((common_utils.StrToList(realops), len(realops)*8))
    return UnpackOps(bb, self.packing_instructions, self.huffman)

  def Compress(self, realops):
    """ basically does nothing"""
    ba = ''.join(realops)
    return ba

  def Decompress(self, op_blob):
    """ basically does nothing"""
    return op_blob

  def MakeSToggl(self, index):
    return {'opcode': 'stoggl', 'index': index}

  def MakeEToggl(self, index):
    return {'opcode': 'etoggl', 'index': index}

  def MakeSKvsto(self, key, val):
    return {'opcode': 'skvsto', 'val': val, 'key': key}

  def MakeEKvsto(self, key, value):
    return {'opcode': 'ekvsto', 'key': key, 'val': value}

  def MakeSClone(self, index, val):
    return {'opcode': 'sclone', 'val': val, 'index': index}

  def MakeEClone(self, index, val):
    return {'opcode': 'eclone', 'val': val, 'index': index}

  def MutateTogglesToTrangs(self, instructions):
    def FigureOutRanges(ops, new_opcode):
      toggles = sorted(copy.deepcopy(ops))
      ot = []
      otr = []
      collapsed = 0
      for toggle in toggles:
        idx = toggle['index']
        if otr and idx - otr[-1]['index'] == 1:
          otr[-1]['index'] = idx
          collapsed += 1
        elif ot and idx - ot[-1]['index'] == 1:
          otr.append(ot.pop())
          otr[-1]['index_start'] = otr[-1]['index']
          otr[-1]['index'] = idx
          otr[-1]['opcode'] = new_opcode
          collapsed += 1
        else:
          ot.append(toggle)
      if collapsed <= 2:
        ot = sorted(ops)
        otr = []
      return [ot, otr]
    etggl, etrng = FigureOutRanges(instructions['etoggl'], 'etrang')
    stggl, strng = FigureOutRanges(instructions['stoggl'], 'strang')
    instructions['etoggl'] = etggl
    instructions['etrang'] = etrng
    instructions['stoggl'] = stggl
    instructions['strang'] = strng

  def FindOrMakeHeaderGroup(self, group_id):
    try:
      return self.header_groups[group_id]
    except KeyError:
      self.header_groups[group_id] = HeaderGroup()
      return self.header_groups[group_id]

  def TouchHeaderGroupEntry(self, group_id, v_idx):
    if v_idx is None:
      raise StandardError()
    header_group = self.FindOrMakeHeaderGroup(group_id)
    #print "\t\t\ttouching/adding idx: %r in group: %d" % (v_idx, group_id)
    header_group.TouchEntry(v_idx)

  def MakeOperations(self, headers, group_id):
    """ Computes the entire set of operations necessary to encode the 'headers'
    for header-group 'group_id'
    """
    instructions = {'stoggl': [], 'etoggl': [],
                    'sclone': [], 'eclone': [],
                    'skvsto': [], 'ekvsto': []}
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
    stoggls = set()

    for kv in headers_set:
      (key, val) = kv
      (k_idx, v_idx) = self.storage.FindEntryIdx(key, val)
      if v_idx is not None:
        # a new toggle.
        if not self.only_etoggles:
          stoggls.add(v_idx)
        else:
          instructions['etoggl'].append(self.MakeEToggl(v_idx))
      elif k_idx is not None:
        if key in [":path"]:
          instructions['eclone'].append(self.MakeEClone(k_idx, val) )
        else:
          instructions['sclone'].append(self.MakeSClone(k_idx, val) )
      else:
        # kvsto
        instructions['skvsto'].append(self.MakeSKvsto(key, val) )

    full_toggl_list = stoggls.union(done_set)
    for idx in full_toggl_list:
      instructions['stoggl'].append(self.MakeSToggl(idx))
    self.MutateTogglesToTrangs(instructions)

    output_instrs = []
    for oplist in instructions.values():
      output_instrs.extend(oplist)
    #### If wishing to track stats, uncomment out the following.
    #g_stats.Process(self.storage, headers, output_instrs)
    #self.wf.LookAt(output_instrs)
    self.DecompressorExecuteOps(output_instrs, group_id)
    return instructions

  def RealOpsToOpAndExecute(self, realops):
    """ Deserializes from SPDY4 wire format and executes the operations"""
    (group_id, ops) = self.RealOpsToOps(realops)
    self.FindOrMakeHeaderGroup(group_id)  # make the header group if necessary
    headers = self.DecompressorExecuteOps(ops, group_id)
    return (group_id, ops, headers)

  def Store(self, kv):
    if self.refcnt_vals:
      return self.storage.InsertVal(lrustorage.KV(kv.key_, kv.val_))
    return self.storage.InsertVal(lrustorage.KV(kv.key_, kv.val()))

  def DecompressorExecuteOps(self, ops, group_id):
    store_later = deque()
    stoggles = set()
    etoggles = set()
    headers = dict()
    current_header_group = self.FindOrMakeHeaderGroup(group_id)

    for op in ops:
      opcode = op['opcode']
      if opcode == 'stoggl':
        lru_idx = op['index']
        stoggles.symmetric_difference_update([lru_idx])
      elif opcode == 'etoggl':
        lru_idx = op['index']
        etoggles.symmetric_difference_update([lru_idx])
      elif opcode == 'strang':
        lru_idx_last = op['index']
        lru_idx_start = op['index_start']
        for lru_idx in xrange(lru_idx_start, lru_idx_last+1):
          stoggles.symmetric_difference_update([lru_idx])
      elif opcode == 'etrang':
        lru_idx_last = op['index']
        lru_idx_start = op['index_start']
        for lru_idx in xrange(lru_idx_start, lru_idx_last+1):
          etoggles.symmetric_difference_update([lru_idx])
      elif opcode == 'sclone':
        lru_idx = op['index']
        val = op['val']
        kv = self.storage.LookupFromIdx(lru_idx)
        AppendToHeaders(headers, kv.key(), val)
        store_later.append(lrustorage.KV(kv.key_, val))
      elif opcode == 'eclone':
        lru_idx = op['index']
        val = op['val']
        kv = self.storage.LookupFromIdx(lru_idx)
        AppendToHeaders(headers, kv.key(), val)
      elif opcode == 'skvsto':
        key = op['key']
        val = op['val']
        AppendToHeaders(headers, key, val)
        store_later.append(lrustorage.KV(key, val))
      elif opcode == 'ekvsto':
        key = op['key']
        val = op['val']
        AppendToHeaders(headers, key, val)

    # modify and store the new header group.
    current_header_group.hg_store.symmetric_difference_update(stoggles)
    kv_references = etoggles.symmetric_difference(current_header_group.hg_store)

    for lru_idx in kv_references:
      kv = self.storage.LookupFromIdx(lru_idx)
      AppendToHeaders(headers, kv.key(), kv.val())

    if self.hg_adjust:
      hg_store_later = []
      for lru_idx in sorted(current_header_group.hg_store):
        kv = self.storage.LookupFromIdx(lru_idx)
        hg_store_later.append((kv, lru_idx));
    # Modify the LRU.
    for kv in store_later:
      new_idx = self.Store(kv)
      if self.implicit_hg_add and new_idx is not None:
        current_header_group.hg_store.add(new_idx)
    if self.hg_adjust:
      for kv, old_idx in hg_store_later:
        if old_idx in current_header_group.hg_store:
          current_header_group.hg_store.remove(old_idx)
        new_idx = self.Store(kv)
        if new_idx is not None:
          current_header_group.hg_store.add(new_idx)

    if 'cookie' in headers:
      headers['cookie'] = headers['cookie'].replace('\0', '; ')
    return headers

  def Done(self):
    pass



