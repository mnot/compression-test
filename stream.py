#!/usr/bin/env python

from collections import defaultdict
import locale

# pylint: disable=W0311


class Stream(object):
  """
  A one-way stream of sets of HTTP headers.
  """
  def __init__(self, name, messages, msg_type):
    """
    """
    self.name = name # identifier for the stream; e.g., "example.com reqs"
    self.messages = messages
    self.msg_type = msg_type # "req" or "res"
    ## counters for totals
    self.procs = []
    self.lname = 0
    self.sizes = defaultdict(list)
    self.ratios = defaultdict(list)

  def record_result(self, proc_name, size, ratio):
    if proc_name not in self.procs:
      self.procs.append(proc_name) # store order of processors
      if len(proc_name) > self.lname:
        self.lname = len(proc_name)
    self.sizes[proc_name].append(size)
    self.ratios[proc_name].append(ratio)

  def print_header(self, output):
    output("* %s: %i %s messages\n" %
      (self.name, len(self.messages), self.msg_type))

  def print_summary(self, output, baseline):
    lines = []
    baseline_size = sum(self.sizes[baseline])
    for proc in self.procs:
      ttl_size = sum(self.sizes[proc])
      pretty_size = locale.format("%13d", ttl_size, grouping=True)
      ratio = 1.0 * ttl_size / baseline_size
      try:
        std = meanstdv(self.ratios[proc])[1]
      except ZeroDivisionError:
        std = 0
      min_ratio = min(self.ratios[proc])
      max_ratio = max(self.ratios[proc])
      lines.append((proc, pretty_size, ratio, min_ratio, max_ratio, std))
    output('  %%%ds size | ratio min   max   std\n' % (self.lname + 9) % '')
    fmt = '  %%%ds %%s | %%2.2f  %%2.2f  %%2.2f  %%2.2f\n' % self.lname
    for line in sorted(lines):
      output(fmt % line)
    output("\n")

  def print_tsv_header(self, output):
    header = "\t".join(["num"] + self.procs)
    output("%s\n" % header)

  def print_tsv(self, output, count = 0):
    lines = apply(zip, [self.sizes[proc] for proc in self.procs])
    for line in lines:
      count += 1
      output("\t".join([str(count)] + [str(j) for j in line]) + "\n")
    return count

  def __add__(self, other):
    assert self.msg_type == other.msg_type
    self.messages.extend(other.messages) # NB: not great for memory
    self.sizes = merge_dols(self.sizes, other.sizes)
    self.ratios = merge_dols(self.ratios, other.ratios)
    return self
    
  def __radd__(self, other):
    return self


def merge_dols(dol1, dol2):
  """
  Merge two dictionaries of lists.
  """
  result = dict(dol1, **dol2)
  result.update((k, dol1[k] + dol2[k])
                for k in set(dol1).intersection(dol2))
  return result
    
def meanstdv(members):
  """
  Calculate mean and standard deviation of data x[]:
      mean = {\sum_i x_i \over n}
      std = sqrt(\sum_i (x_i - mean)^2 \over n-1)
  """
  from math import sqrt
  num, mean, std = len(members), 0, 0
  for item in members:
    mean = mean + item
  mean = mean / float(num)
  for item in members:
    std = std + (item - mean)**2
  std = sqrt(std / float(num - 1))
  return mean, std