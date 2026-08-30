#!/bin/sh
# Fixed-format COBOL: nothing may extend past column 72.
rc=0
for f in "$@"; do
  awk -v F="$f" 'length > 72 { printf "%s:%d: col %d exceeds 72\n", F, NR, length; c++ }
                 END { exit (c>0) }' "$f" || rc=1
done
exit $rc
