"""Flip the packed sign nibble of EIN 990000007's deposit to negative.

BLDFIX reads unsigned text so a negative TRN-AMT cannot be expressed as a
fixture line; the branch it guards (PENACC's negative-base path) is only
reachable by constructing the packed record directly.
"""
import sys


def main(path):
    with open(path, "rb") as handle:
        data = bytearray(handle.read())
    patched = 0
    for offset in range(0, len(data), 80):
        record = data[offset:offset + 80]
        if record[0:9] == b"990000007" and record[17:20] == b"650":
            data[offset + 33] = (data[offset + 33] & 0xF0) | 0x0D
            patched += 1
    with open(path, "wb") as handle:
        handle.write(bytes(data))
    print("patched %d record(s)" % patched)


if __name__ == "__main__":
    main(sys.argv[1])
