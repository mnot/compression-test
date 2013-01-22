#!/usr/bin/env python

import sys
import os

def main():
  while True:
    headers = []
    name = ""
    if len(sys.argv) >= 2:
      name = sys.argv[1]
    else:
      name = "%d" % os.getpid()
    while True:
      line = sys.stdin.readline()
      if line.strip() == "":
        break
      headers.append(line)

    sys.stdout.write(''.join(headers))
    sys.stdout.write("\n")
    try:
      sys.stdout.flush()
    except IOError: # done
      break

main()
