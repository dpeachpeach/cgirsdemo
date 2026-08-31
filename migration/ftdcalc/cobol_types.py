"""COBOL data representation helpers shared by the FTDCALC port.

Packed-decimal (COMP-3), binary (COMP) and edited-picture behaviour are
reproduced here because the port has to agree with the legacy program byte for
byte, including silent high-order truncation.
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


def comp3_size(digits):
    """Bytes occupied by a PIC 9(digits) COMP-3 field."""
    return digits // 2 + 1


def unpack_comp3(raw, scale):
    """Decode a COMP-3 field. Returns a Decimal scaled by `scale` decimals."""
    nibbles = []
    for byte in raw:
        nibbles.append(byte >> 4)
        nibbles.append(byte & 0x0F)
    sign_nibble = nibbles.pop()
    text = "".join(str(n) for n in nibbles)
    value = Decimal(text).scaleb(-scale)
    if sign_nibble == 0x0D:
        value = -value
    return value


def pack_comp3(value, digits, scale, signed=True):
    """Encode a Decimal into a COMP-3 field, truncating high-order digits."""
    value = truncate(value, digits, scale, signed)
    negative = value < 0
    unscaled = int(abs(value).scaleb(scale).to_integral_value(rounding=ROUND_DOWN))
    text = str(unscaled).rjust(digits, "0")[-digits:]
    if len(text) % 2 == 0:
        text = "0" + text
    sign_nibble = 0x0F
    if signed:
        sign_nibble = 0x0D if negative else 0x0C
    out = bytearray()
    for i in range(0, len(text) - 1, 2):
        out.append(int(text[i]) << 4 | int(text[i + 1]))
    out.append(int(text[-1]) << 4 | sign_nibble)
    return bytes(out)


def truncate(value, digits, scale, signed=True):
    """Apply COBOL field capacity: truncate to `scale` decimals then drop
    high-order digits that do not fit in `digits` digits."""
    value = Decimal(value).quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    limit = Decimal(10) ** (digits - scale)
    negative = value < 0
    magnitude = abs(value) % limit
    result = -magnitude if (negative and signed) else magnitude
    return result.quantize(Decimal(1).scaleb(-scale))


def round_half_up(value, scale):
    return Decimal(value).quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)


def truncate_binary(value, digits):
    """PIC S9(digits) COMP under -std=ibm: value wraps at the digit capacity."""
    limit = 10 ** digits
    negative = value < 0
    magnitude = abs(int(value)) % limit
    return -magnitude if negative else magnitude


def edited_zzz9_sign(value):
    """PIC ZZZ9- : four digit positions, trailing sign position."""
    magnitude = abs(int(value)) % 10000
    text = str(magnitude).rjust(4)
    if magnitude == 0:
        text = "   0"
    return text + ("-" if value < 0 else " ")


def edited_amount(value):
    """PIC ZZZZZZZ9.99 : eight integer positions (leading seven suppressed)."""
    value = truncate(value, 10, 2)
    magnitude = abs(value) % Decimal(100000000)
    cents = int((magnitude * 100).to_integral_value(rounding=ROUND_DOWN))
    integer_part, frac = divmod(cents, 100)
    return "%8d.%02d" % (integer_part, frac)
