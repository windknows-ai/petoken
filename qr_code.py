"""A small QR Code encoder (ISO/IEC 18004), pure Python (2.2).

Petoken 2.2 can push notifications to the user's phone through ntfy. To
subscribe, the phone only has to scan a QR code of the topic address, for
example `https://ntfy.sh/petoken-k3j9x2m4p8q7w5z1`, so Settings shows one.
No QR library is installed and the address is the only thing that needs
encoding, so this module writes the symbol itself instead of adding a
dependency to the build.

Scope is what that address needs: byte mode (UTF-8), versions 1 to 10, error
correction L/M/Q/H. `encode` picks the smallest version that fits, builds
the data codewords, adds Reed-Solomon error correction block by block,
interleaves them, places the function patterns and the zigzag data, tries the
eight masks with the four standard penalty rules, and writes the format and
version information. It returns a matrix of booleans (True is a dark module,
row first, no quiet zone). `to_qimage` draws that matrix for Qt.
"""
from __future__ import annotations

from itertools import product

MAX_VERSION = 10
ECC_LEVELS = 'LMQH'
_ECC_FORMAT_BITS = dict(L=1, M=0, Q=3, H=2)       # The 2 bits stored in the format information.

# Per version, per level: (ECC codewords per block, ((block count, data codewords per block), ...)).
_BLOCKS = {
    1: dict(L=(7, ((1, 19),)), M=(10, ((1, 16),)), Q=(13, ((1, 13),)), H=(17, ((1, 9),))),
    2: dict(L=(10, ((1, 34),)), M=(16, ((1, 28),)), Q=(22, ((1, 22),)), H=(28, ((1, 16),))),
    3: dict(L=(15, ((1, 55),)), M=(26, ((1, 44),)), Q=(18, ((2, 17),)), H=(22, ((2, 13),))),
    4: dict(L=(20, ((1, 80),)), M=(18, ((2, 32),)), Q=(26, ((2, 24),)), H=(16, ((4, 9),))),
    5: dict(L=(26, ((1, 108),)), M=(24, ((2, 43),)), Q=(18, ((2, 15), (2, 16))), H=(22, ((2, 11), (2, 12)))),
    6: dict(L=(18, ((2, 68),)), M=(16, ((4, 27),)), Q=(24, ((4, 19),)), H=(28, ((4, 15),))),
    7: dict(L=(20, ((2, 78),)), M=(18, ((4, 31),)), Q=(18, ((2, 14), (4, 15))), H=(26, ((4, 13), (1, 14)))),
    8: dict(L=(24, ((2, 97),)), M=(22, ((2, 38), (2, 39))), Q=(22, ((4, 18), (2, 19))), H=(26, ((4, 14), (2, 15)))),
    9: dict(L=(30, ((2, 116),)), M=(22, ((3, 36), (2, 37))), Q=(20, ((4, 16), (4, 17))), H=(24, ((4, 12), (4, 13)))),
    10: dict(L=(18, ((2, 68), (2, 69))), M=(26, ((4, 43), (1, 44))), Q=(24, ((6, 19), (2, 20))),
             H=(28, ((6, 15), (2, 16)))),
}
_ALIGNMENT = {1: (), 2: (6, 18), 3: (6, 22), 4: (6, 26), 5: (6, 30), 6: (6, 34),
              7: (6, 22, 38), 8: (6, 24, 42), 9: (6, 26, 46), 10: (6, 28, 50)}
_PAD_BYTES = (0xEC, 0x11)


# --- Reed-Solomon over GF(256), polynomial x^8+x^4+x^3+x^2+1 ---------------------------------------

def _gf_tables():
    exp, log = [0] * 510, [0] * 256
    value = 1
    for i in range(255):
        exp[i] = exp[i + 255] = value
        log[value] = i
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    return exp, log


_EXP, _LOG = _gf_tables()


def _gf_mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def generator_polynomial(degree):
    """Coefficients (highest power first, leading 1 left out) of prod (x - 2^i) for i < degree."""
    poly = [1]
    for i in range(degree):
        shifted = poly + [0]
        for j, coefficient in enumerate(poly):
            shifted[j + 1] ^= _gf_mul(coefficient, _EXP[i])
        poly = shifted
    return poly[1:]


def reed_solomon(data, degree):
    """The `degree` error correction codewords for the data codewords `data`."""
    generator = generator_polynomial(degree)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder.pop(0)
        remainder.append(0)
        for i, coefficient in enumerate(generator):
            remainder[i] ^= _gf_mul(coefficient, factor)
    return remainder


# --- Format and version information -----------------------------------------------------------------

def format_bits(ecc, mask):
    """The 15 format information bits for an error correction level and a mask (0 to 7)."""
    data = _ECC_FORMAT_BITS[ecc] << 3 | mask
    remainder = data
    for _ in range(10):
        remainder = remainder << 1 ^ (remainder >> 9) * 0x537
    return (data << 10 | remainder) ^ 0x5412


def version_bits(version):
    """The 18 version information bits (versions 7 and up)."""
    remainder = version
    for _ in range(12):
        remainder = remainder << 1 ^ (remainder >> 11) * 0x1F25
    return version << 12 | remainder


# --- Data codewords ---------------------------------------------------------------------------------

def _capacity(version, ecc):
    """Data codewords that fit in a version at an error correction level."""
    return sum(count * size for count, size in _BLOCKS[version][ecc][1])


def pick_version(length, ecc):
    """The smallest version whose data area holds `length` bytes in byte mode."""
    for version in range(1, MAX_VERSION + 1):
        count_bits = 8 if version < 10 else 16
        if 4 + count_bits + 8 * length <= 8 * _capacity(version, ecc) and length < 1 << count_bits:
            return version
    raise ValueError(f'{length} bytes do not fit in a version {MAX_VERSION} QR code at level {ecc}')


def _data_codewords(payload, version, ecc):
    bits = [0, 1, 0, 0]                                               # Byte mode indicator.
    count_bits = 8 if version < 10 else 16
    bits += [(len(payload) >> i) & 1 for i in range(count_bits - 1, -1, -1)]
    for byte in payload:
        bits += [(byte >> i) & 1 for i in range(7, -1, -1)]
    total = 8 * _capacity(version, ecc)
    bits += [0] * min(4, total - len(bits))                           # Terminator.
    bits += [0] * (-len(bits) % 8)
    codewords = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0
    while len(codewords) < total // 8:
        codewords.append(_PAD_BYTES[pad % 2])
        pad += 1
    return codewords


def split_blocks(codewords, version, ecc):
    """The data codewords cut into the blocks the version and level call for."""
    blocks, start = [], 0
    for count, size in _BLOCKS[version][ecc][1]:
        for _ in range(count):
            blocks.append(codewords[start:start + size])
            start += size
    return blocks


def interleave(blocks, version, ecc):
    """Data codewords of all blocks column by column, then their error correction the same way."""
    ecc_length = _BLOCKS[version][ecc][0]
    ecc_blocks = [reed_solomon(block, ecc_length) for block in blocks]
    result = []
    for i in range(max(len(block) for block in blocks)):
        result += [block[i] for block in blocks if i < len(block)]
    for i in range(ecc_length):
        result += [block[i] for block in ecc_blocks]
    return result


# --- The matrix -------------------------------------------------------------------------------------

def _template(version):
    """(modules, function) for a version: the fixed patterns drawn, everything else light.

    `function[y][x]` marks modules that never carry data. Format information is
    reserved (drawn as zeros) and the version information is already final.
    """
    size = 4 * version + 17
    modules = [[False] * size for _ in range(size)]
    function = [[False] * size for _ in range(size)]

    def put(x, y, dark):
        modules[y][x] = dark
        function[y][x] = True

    for i in range(size):                                             # Timing patterns.
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):             # Finders and their separators.
        for dy, dx in product(range(-4, 5), repeat=2):
            if 0 <= cx + dx < size and 0 <= cy + dy < size:
                put(cx + dx, cy + dy, max(abs(dx), abs(dy)) not in (2, 4))
    centers = _ALIGNMENT[version]
    for cx, cy in product(centers, repeat=2):
        if (cx, cy) in ((centers[0], centers[0]), (centers[0], centers[-1]), (centers[-1], centers[0])):
            continue                                                  # Would overlap a finder.
        for dy, dx in product(range(-2, 3), repeat=2):
            put(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
    _write_format(modules, function, 0, size, reserve=True)
    put(8, size - 8, True)                                            # The always-dark module.
    if version >= 7:
        bits = version_bits(version)
        for i in range(18):
            a, b = size - 11 + i % 3, i // 3
            put(a, b, bool(bits >> i & 1))
            put(b, a, bool(bits >> i & 1))
    return modules, function


def _write_format(modules, function, bits, size, reserve=False):
    """Both copies of the 15 format bits (bit 0 first along each copy)."""
    spots = []
    for i in range(15):
        first = (8, i) if i < 6 else (8, 7) if i == 6 else (8, 8) if i == 7 else (7, 8) if i == 8 else (14 - i, 8)
        second = (size - 1 - i, 8) if i < 8 else (8, size - 15 + i)
        spots += [(first, i), (second, i)]
    for (x, y), i in spots:
        modules[y][x] = bool(bits >> i & 1)
        if reserve:
            function[y][x] = True


def _place_data(modules, function, codewords):
    size = len(modules)
    bits = [codeword >> i & 1 for codeword in codewords for i in range(7, -1, -1)]
    index = 0
    for right in range(size - 1, 0, -2):
        if right <= 6:
            right -= 1                                                # Skip the vertical timing column.
        upward = (right + 1) & 2 == 0
        for step in range(size):
            y = size - 1 - step if upward else step
            for x in (right, right - 1):
                if not function[y][x] and index < len(bits):
                    modules[y][x] = bool(bits[index])
                    index += 1


_MASKS = (
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
)


def mask_matrix(modules, function, mask):
    """A copy of `modules` with mask pattern `mask` applied to the data modules."""
    test = _MASKS[mask]
    return [[cell != (not function[y][x] and test(x, y)) for x, cell in enumerate(row)]
            for y, row in enumerate(modules)]


_FINDER_LIKE = ('10111010000', '00001011101')


def penalty(matrix):
    """The four standard mask penalty rules added up (lower is better)."""
    size = len(matrix)
    lines = [''.join('1' if cell else '0' for cell in row) for row in matrix]
    lines += [''.join(lines[y][x] for y in range(size)) for x in range(size)]
    score = 0
    for line in lines:
        run = 1
        for i in range(1, size + 1):
            if i < size and line[i] == line[i - 1]:
                run += 1
                continue
            if run >= 5:
                score += 3 + run - 5                                  # Rule 1: runs of one colour.
            run = 1
        for pattern in _FINDER_LIKE:                                  # Rule 3: finder-like patterns.
            start = line.find(pattern)
            while start != -1:
                score += 40
                start = line.find(pattern, start + 1)
    for y in range(size - 1):                                         # Rule 2: 2x2 blocks.
        for x in range(size - 1):
            if matrix[y][x] == matrix[y][x + 1] == matrix[y + 1][x] == matrix[y + 1][x + 1]:
                score += 3
    dark = sum(row.count(True) for row in matrix)                     # Rule 4: dark/light balance.
    score += abs(dark * 100 - size * size * 50) // (size * size * 5) * 10
    return score


def encode(text, ecc='M'):
    """The QR code for `text` as a square list of rows; True is a dark module (no quiet zone)."""
    if ecc not in ECC_LEVELS or len(ecc) != 1:
        raise ValueError(f'unknown error correction level {ecc!r}')
    payload = text.encode('utf-8')
    version = pick_version(len(payload), ecc)
    codewords = interleave(split_blocks(_data_codewords(payload, version, ecc), version, ecc), version, ecc)
    modules, function = _template(version)
    _place_data(modules, function, codewords)
    size = len(modules)
    best = None
    for mask in range(8):
        candidate = mask_matrix(modules, function, mask)
        _write_format(candidate, function, format_bits(ecc, mask), size)
        score = penalty(candidate)
        if best is None or score < best[0]:
            best = (score, candidate)
    return best[1]


def to_qimage(matrix, scale=8, border=4):
    """A black-on-white QImage of the matrix with `border` light modules around it."""
    from PySide6.QtGui import QColor, QImage, QPainter

    side = (len(matrix) + 2 * border) * scale
    image = QImage(side, side, QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    black = QColor('black')
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                painter.fillRect((x + border) * scale, (y + border) * scale, scale, scale, black)
    painter.end()
    return image
