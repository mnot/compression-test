# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import heapq
from collections import deque
from bit_bucket import BitBucket
from common_utils import FormatAsBits
import string

class Huffman(object):
  """
  This class takes in a frequency table, constructs a huffman code, and
  then allows for encoding and decoding of strings.
  """
  def __init__(self, freq_table):
    self.code_tree = None
    self.code_table = []
    self.branches = []
    self.decode_table = []
    divisor = 1
    while True:
      max_code_len = self.BuildCodeTree(freq_table, divisor)
      #print "max_code_len: ", max_code_len
      if max_code_len <= 32:
        break
      divisor *= 2
    self.BuildCodeTable(self.code_tree)
    #print self.FormatCodeTable()

  @staticmethod
  def GetNextNode(internals, leaves):
    if internals and leaves:
      if leaves[0][0] <= internals[0][0]:
        return leaves.popleft()

  def BuildCodeTree(self, freq_table, divisor):
    """ Given a frequency table (a list of tuples of (symbol, frequency-count)),
    constructs the huffman tree which is to say a tree where the root of any
    subtree is the sum of the weight of its children, and where subtrees are
    constructed by examining the node with the smallest weight """
    def MN(x):
      if isinstance(x, int):
        return x
      return ord(x)
    if len(freq_table) < 2:
      # that'd be stupid...
      raise StandardError()

    leaves = deque()
    internals = deque()
    for elem in freq_table:
      (sym, freq) = elem
      if freq == 0:
        freq = 1.0/512
      weight = freq * 1.0 / divisor
      leaves.append( (weight, MN(sym), 0, []) )

    # freq_table is (symbol, count)
    # code_tree is [freq, symbol, depth, children]
    leaves = deque(sorted(leaves))
    internals = deque()
    while len(leaves) + len(internals) > 1:
      children = []
      while len(children) < 2:
        if leaves and internals:
          if leaves[0][0] <= internals[0][0]:
            children.append(leaves.popleft())
          else:
            children.append(internals.popleft())
        elif leaves:
          children.append(leaves.popleft())
        else:
          children.append(internals.popleft())
      internals.append([(children[0][0] + children[1][0]), None,
                         max(children[0][2], children[1][2]) + 1, children])
    if len(leaves):
      raise StandardError()
    self.code_tree = internals.pop()
    return self.code_tree[2]

  @staticmethod
  def DiscoverDepthAndStoreIt(depth_to_sym, root):
    d = deque([(root, 0)])
    while d:
      (c, depth) = d.popleft()
      if c[1] is not None:
        c_depth_val =  depth_to_sym.get(depth, [])
        c_depth_val.append(c[:2])
        depth_to_sym[depth] = c_depth_val
      if c[3] and len(c[3]) > 0:
        for n in c[3]:
          d.append((n, depth + 1))

  def BinaryStringToBREP(self, binary_string):
    """
    Given a string containing '1's and '0's, construct the binary
    representation which is (list-of-bytes, number-of-bits-as-int)
    """
    output = []
    bitlen = len(binary_string)
    if not bitlen:
      raise StandardError()
    index = 0
    while index + 8 < bitlen:
      output.append(int(binary_string[index:index+8],2))
      index += 8
    if index != bitlen:
      final = binary_string[index:bitlen]
      for i in xrange(8 - (bitlen - index)):
        final += '0'
      output.append(int(final, 2))
    return (output, bitlen)


  def BuildCanonicalCodeTable(self):
    depth_to_sym = {}
    Huffman.DiscoverDepthAndStoreIt(depth_to_sym, self.code_tree)
    code = -1
    prev_code_length = 0
    canonical_code_table = {}
    for k,v in depth_to_sym.iteritems():
      current_code_length = k
      #print k
      for sym in sorted(map(lambda x: x[1], v)):
        code = code + 1
        code = (code << (current_code_length - prev_code_length))
        prev_code_length = current_code_length
        #print "\t{:>3}".format(sym),
        #if sym < 127 and \
        #   chr(sym) in (string.digits + string.letters
        #              + string.punctuation + ' ' + '\t'):
        #  print '  %4s' % repr(chr(sym)),
        #else:
        #  print '      ',
        tmp_code = code
        tmp_code_len = current_code_length
        f = deque()
        canonical_code_table[sym] = (self.BinaryStringToBREP(
            ('{0:0%db}' % current_code_length).format(tmp_code)),
            code)
    self.canonical_code_table = []
    for sym in xrange(len(canonical_code_table)):
      self.canonical_code_table.append(canonical_code_table[sym])
    self.code_table = [x for x,_ in self.canonical_code_table]

  def RebuildDecodeTreeFromCanonicalCodes(self):
    root = [None, None, 0, [None, None]]
    for sym in xrange(len(self.canonical_code_table)):
      (code, _) = self.canonical_code_table[sym]
      bb = BitBucket()
      bb.StoreBits(code)
      curr = root
      while not bb.AllConsumed():
        bit = bb.GetBits(1)[0][0] >> 7
        if curr[3][bit] is None:
          curr[3][bit] = [None, None, curr[2]+1, [None, None]]
        curr = curr[3][bit]
      curr[1] = sym
      curr[3] = []
    self.code_tree = root

  @staticmethod
  def Equivalent(sorted_by_code, idx1, idx2, msb, bw):
    #print "msb: %d, bw: %d " % (msb, bw),
    #print "FOO", sorted_by_code[idx1][1], "BAR", sorted_by_code[idx2][1]
    cur_code = sorted_by_code[idx1][0]
    nxt_code = sorted_by_code[idx2][0]
    #print (cur_code, nxt_code)
    #print (cur_code << msb, nxt_code << msb)
    #print (((cur_code << msb) & 0xFFFFFFFF),
    #       ((nxt_code << msb) & 0xFFFFFFFF))
    #print ((((cur_code << msb) & 0xFFFFFFFF) >> (32 - bw)),
    #       (((nxt_code << msb) & 0xFFFFFFFF) >> (32 - bw)))

    cur_idx = ((cur_code << msb) & 0xFFFFFFFF) >> (32 - bw)
    nxt_idx = ((nxt_code << msb) & 0xFFFFFFFF) >> (32 - bw)
    return cur_idx == nxt_idx

  @staticmethod
  def MakeBranchEntry(base_idx, branch_idx, msb, bw):
    mask = ((0xFFFFFFFF << (32 - bw)) & 0xFFFFFFFF) >> msb
    shift = 32 - min(msb + bw, 32)
    return (base_idx, branch_idx, mask, shift)

  def BuildDecodeTableHelper(self, sorted_by_code, decode_table,
                             branches, begin, end, msb, bw):
    branch_idx = len(branches)
    branches.append(Huffman.MakeBranchEntry(len(decode_table), branch_idx, msb, bw))
    decode_table_idx = len(decode_table)
    #print "BW: ", bw
    decode_table += [(0,0,0) for i in xrange(0x1 << bw)]
    run_start = begin
    run_end = begin
    while run_end < end:
      while Huffman.Equivalent(sorted_by_code, run_start, run_end, msb, bw):
        run_end += 1
        if run_end == end:
          break
      dist = run_end - run_start
      cur_code = sorted_by_code[run_start][0]
      cur_idx = ((cur_code << msb) & 0xFFFFFFFF) >> (32 - bw)
      if dist == 1:
        sym = sorted_by_code[run_start][1]
        decode_table[decode_table_idx + cur_idx] = (sym, branch_idx, 1)
      else:
        sym = sorted_by_code[run_end - 1][1]
        nxt_code_len = self.canonical_code_table[sym][0][1]
        #print "nxt_code_len: ", nxt_code_len
        #print "sym: ", sym
        nxt_bit_len = nxt_code_len - (msb + bw)
        #print "NBL: ", nxt_bit_len
        decode_table[decode_table_idx + cur_idx] = (0, 0, 0)
        #print "NBW: ", min(bw, nxt_bit_len)
        self.BuildDecodeTableHelper(sorted_by_code, decode_table, branches,
                                    run_start, run_end,
                                    msb + bw, min(bw, nxt_bit_len))
      run_start = run_end

  def BuildDecodeTable(self):
    lookup_bits = 8
    self.branches = []  # (base_idx, ref, mask, shift)
    self.decode_table = []  # (sym, next_table, valid)
    sorted_by_code = []  # (code, sym)
    for i in xrange(len(self.canonical_code_table)):
      sym = i
      code = self.canonical_code_table[i][1]
      code <<= (32 - self.canonical_code_table[i][0][1])
      sorted_by_code.append( (code, sym) )
    sorted_by_code.sort()
    #print sorted_by_code
    self.BuildDecodeTableHelper(sorted_by_code,
                                self.decode_table, self.branches,
                                0, len(sorted_by_code), 0, lookup_bits)
    for i in xrange(len(self.decode_table)):
      if not self.decode_table[i][2]:
        self.decode_table[i] = self.decode_table[i-1]
    #Huffman.PrintDecodeTableAndBranches(self.decode_table, self.branches)

  @staticmethod
  def PrintDecodeTableAndBranches(decode_table, branches):
    print "decode_table: "
    for (sym, branch_idx, valid) in decode_table:
      if sym < 127 and \
         chr(sym) in (string.digits + string.letters
                    + string.punctuation + ' ' + '\t'):
        print '\t%5s' % repr(chr(sym)),
      else:
          print '\t(%4d)' % sym,
      print branch_idx
    print "branches: "
    print '\n\t'.join([''] + [repr((a,b,'{0:032b}'.format(c),d))
                              for (a,b,c,d) in branches])

  def BuildCodeTable(self, code_tree):
    """ Given a code-tree as constructed in BuildCodeTree, construct a table
    useful for doing encoding of a plaintext symbol into into its huffman
    encoding.  The table is ordered in the order of symbols, and contains the
    binary representation of the huffman encoding for each symbol.
    """
    self.BuildCanonicalCodeTable()
    #self.BuildDecodeTable()
    self.RebuildDecodeTreeFromCanonicalCodes()
    return

    queue = deque([(code_tree, '')])
    pre_table = []
    while queue:
      (tree, path_so_far) = queue.popleft()
      (freq, name, depth, children) = tree
      if name != None:
        if not isinstance(name, int):
          pre_table.append( (ord(name), str(path_so_far)) )
        else:
          pre_table.append( (    name , str(path_so_far)) )
      if children:
        queue.appendleft( (children[0], str(path_so_far + '0')) )
        queue.appendleft( (children[1], str(path_so_far + '1')) )
    pre_table = sorted(pre_table, key=lambda x: x[0])
    for i in xrange(len(pre_table)):
      (name, binary_string) = pre_table[i]
      if i != name:
        raise StandardError()
      self.code_table.append(self.BinaryStringToBREP(binary_string))

  def EncodeToBB(self, bb, text, include_eof):
    """
    Given a BitBucket 'bb', and a string 'text', encode the string using the
    pre-computed huffman codings and store them into the BitBucket. if
    'include_eof' is true, then an EFO will also be encoded at the end.
    """
    for c in text:
      try:
        bb.StoreBits(self.code_table[c])
      except:
        print "code_table:", self.code_table
        raise
    if include_eof:
      bb.StoreBits(self.code_table[256])

  def Encode(self, text, include_eof):
    """
    Encodes 'text' using the pre-computed huffman coding, and returns it as
    a tuple of (list-of-bytes, number-of-bits-as-int). If 'include_eof' is true,
    then an EOF will be encoded at the end.
    """
    bb = BitBucket()
    self.EncodeToBB(bb, text, include_eof)
    return bb.GetAllBits()

  def DecodeFromBB(self, bb, includes_eof, bits_to_decode):
    """
    Decodes the huffman-encoded text stored in the BitBucket 'bb back into a
    plaintext string.  If 'includes_eof' is true, then it is assumed that the
    string was encoded with an EOF.  If bits_to_decode > 0, then 'includes_eof'
    is allowed to be false, and that many bits will be consumed from the
    BitBucket
    """
    output = []
    total_bits = 0
    if not includes_eof and bits_to_decode <= 0:
      # That can't work.
      raise StandardError()
    if bits_to_decode <= 0:
      bits_to_decode = -1
    while bits_to_decode < 0 or total_bits < bits_to_decode:
      root = self.code_tree
      while root[1] is None:
        bit = bb.GetBits(1)[0][0] >> 7
        root = root[3][bit]
        total_bits += 1
      if includes_eof and root[1] is not None and root[1] == 256:
        break
      elif root[1] is not None:
        output.append(root[1])
      else:
        raise StandardError()
    if bits_to_decode > 0 and total_bits < bits_to_decode:
      bb.GetBits(bits_to_decode - total_bits)
    return output

  def FormatCodeTable(self):
    """
    Makes a formatted version of the code table, useful for debugging
    """
    printable = string.digits + string.letters + string.punctuation + ' '
    x = sorted([(i,FormatAsBits( self.code_table[i]))
                for i in xrange(len(self.code_table))])
    retval = []
    for entry in x:
      code, description = entry
      readable_code = ""
      if code < 128 and chr(code) in printable:
        readable_code = "'%c'" % chr(code)
      while len(readable_code) < 5:
          readable_code = " " + readable_code
      retval.append('%s (%3d): %s' % (readable_code, code, description))
    return '\n'.join(retval)

  def __repr__(self):
    output = ['[']
    for elem in self.code_table.iteritems():
      output.append(repr(elem))
      output.append(', ')
    output.append(']')
    return ''.join(output)

