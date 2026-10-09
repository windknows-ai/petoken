"""QR code encoder: known vectors, structure, and a full read-back."""
import unittest

import qr_code

URL = 'https://ntfy.sh/petoken-k3j9x2m4p8q7w5z1'
RAW_CODEWORDS = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242, 9: 292, 10: 346}


def bits_of(value, width):
    return format(value, f'0{width}b')


def read_format(matrix):
    """(ecc letter, mask) from the first format copy; the second copy must agree."""
    size = len(matrix)
    first = [matrix[i][8] if i < 6 else matrix[7][8] if i == 6 else matrix[8][8] if i == 7
             else matrix[8][7] if i == 8 else matrix[8][14 - i] for i in range(15)]
    second = [matrix[8][size - 1 - i] if i < 8 else matrix[size - 15 + i][8] for i in range(15)]
    assert first == second, 'the two format copies differ'
    value = sum(int(bit) << i for i, bit in enumerate(first)) ^ 0x5412
    ecc = {1: 'L', 0: 'M', 3: 'Q', 2: 'H'}[value >> 13]
    return ecc, value >> 10 & 7


def zigzag(size):
    """Module coordinates (x, y) in data order: column pairs right to left, snaking up and down."""
    order = []
    columns = list(range(size - 1, 0, -2))
    for n, right in enumerate(columns):
        right = right - 1 if right <= 6 else right
        ys = range(size - 1, -1, -1) if n % 2 == 0 else range(size)
        for y in ys:
            order += [(right, y), (right - 1, y)]
    return order


def read_codewords(matrix):
    """(ecc, version, interleaved codewords) read back from a matrix."""
    size = len(matrix)
    version = (size - 17) // 4
    ecc, mask = read_format(matrix)
    _, function = qr_code._template(version)
    bits = []
    for x, y in zigzag(size):
        if not function[y][x]:
            bits.append(matrix[y][x] != qr_code._MASKS[mask](x, y))
    codewords = [int(''.join('1' if b else '0' for b in bits[i:i + 8]), 2) for i in range(0, len(bits) - 7, 8)]
    return ecc, version, codewords


def deinterleave(codewords, version, ecc):
    ecc_length, groups = qr_code._BLOCKS[version][ecc]
    sizes = [size for count, size in groups for _ in range(count)]
    data_total = sum(sizes)
    data, check = codewords[:data_total], codewords[data_total:]
    blocks = [[] for _ in sizes]
    position = 0
    for i in range(max(sizes)):
        for b, size in enumerate(sizes):
            if i < size:
                blocks[b].append(data[position])
                position += 1
    checks = [[check[i * len(sizes) + b] for i in range(ecc_length)] for b in range(len(sizes))]
    return blocks, checks


def decode_byte_mode(blocks, version):
    stream = ''.join(bits_of(byte, 8) for block in blocks for byte in block)
    assert stream[:4] == '0100', 'not byte mode'
    count_bits = 8 if version < 10 else 16
    count = int(stream[4:4 + count_bits], 2)
    start = 4 + count_bits
    payload = bytes(int(stream[start + 8 * i:start + 8 * i + 8], 2) for i in range(count))
    return payload.decode('utf-8')


class ReedSolomonTests(unittest.TestCase):
    def test_hello_world_example(self):
        data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
        self.assertEqual(qr_code.reed_solomon(data, 10), [196, 35, 39, 119, 235, 215, 231, 226, 93, 23])

    def test_generator_polynomial_of_degree_seven(self):
        self.assertEqual(qr_code.generator_polynomial(7), [127, 122, 154, 164, 11, 68, 117])

    def test_block_table_adds_up_to_the_raw_capacity(self):
        for version, raw in RAW_CODEWORDS.items():
            for ecc in 'LMQH':
                ecc_length, groups = qr_code._BLOCKS[version][ecc]
                blocks = sum(count for count, _ in groups)
                self.assertEqual(qr_code._capacity(version, ecc) + blocks * ecc_length, raw, (version, ecc))


class InformationBitsTests(unittest.TestCase):
    def test_format_information_matches_the_iso_table(self):
        self.assertEqual(bits_of(qr_code.format_bits('M', 0), 15), '101010000010010')
        self.assertEqual(bits_of(qr_code.format_bits('L', 4), 15), '110011000101111')

    def test_version_information_matches_the_iso_table(self):
        self.assertEqual(bits_of(qr_code.version_bits(7), 18), '000111110010010100')
        self.assertEqual(bits_of(qr_code.version_bits(10), 18), '001010010011010011')


class StructureTests(unittest.TestCase):
    def finder_at(self, matrix, x0, y0):
        for dy in range(7):
            for dx in range(7):
                ring = max(abs(dx - 3), abs(dy - 3))
                if matrix[y0 + dy][x0 + dx] != (ring != 2):
                    return False
        return True

    def test_ntfy_url_is_version_three_at_m(self):
        matrix = qr_code.encode(URL, 'M')
        self.assertEqual(len(matrix), 4 * 3 + 17)
        self.assertTrue(all(len(row) == len(matrix) for row in matrix))
        size = len(matrix)
        self.assertTrue(self.finder_at(matrix, 0, 0))
        self.assertTrue(self.finder_at(matrix, size - 7, 0))
        self.assertTrue(self.finder_at(matrix, 0, size - 7))
        for i in range(8, size - 8):
            self.assertEqual(matrix[6][i], i % 2 == 0)
            self.assertEqual(matrix[i][6], i % 2 == 0)
        self.assertTrue(matrix[4 * 3 + 9][8])
        for i in range(8):                                            # Separators are light.
            self.assertFalse(matrix[7][i])
            self.assertFalse(matrix[i][7])

    def test_alignment_pattern_is_drawn_from_version_two(self):
        matrix = qr_code.encode(URL, 'M')
        size = len(matrix)
        cx = cy = size - 7
        self.assertTrue(matrix[cy][cx])
        self.assertFalse(matrix[cy][cx + 1])
        self.assertTrue(matrix[cy][cx + 2])

    def test_version_grows_with_length_and_level(self):
        self.assertEqual(qr_code.pick_version(17, 'L'), 1)
        self.assertEqual(qr_code.pick_version(18, 'L'), 2)
        self.assertEqual(qr_code.pick_version(len(URL), 'M'), 3)
        self.assertGreater(qr_code.pick_version(len(URL), 'H'), qr_code.pick_version(len(URL), 'L'))
        self.assertEqual(qr_code.pick_version(271, 'L'), 10)

    def test_too_long_or_bad_level_is_refused(self):
        with self.assertRaises(ValueError):
            qr_code.encode('a' * 272, 'L')
        with self.assertRaises(ValueError):
            qr_code.encode('x', 'Z')

    def test_ten_has_two_identical_version_copies(self):
        matrix = qr_code.encode('a' * 250, 'L')
        size = len(matrix)
        self.assertEqual(size, 57)
        bits = qr_code.version_bits(10)
        for i in range(18):
            self.assertEqual(matrix[i // 3][size - 11 + i % 3], bool(bits >> i & 1))
            self.assertEqual(matrix[size - 11 + i % 3][i // 3], bool(bits >> i & 1))

    def test_chosen_mask_has_the_lowest_penalty(self):
        matrix = qr_code.encode(URL, 'M')
        ecc, mask = read_format(matrix)
        version = (len(matrix) - 17) // 4
        modules, function = qr_code._template(version)
        scores = []
        for candidate in range(8):
            copy = [row[:] for row in matrix]
            # Undo the chosen mask, apply the candidate, then compare penalties without format bits.
            for y, row in enumerate(copy):
                for x in range(len(row)):
                    if not function[y][x]:
                        row[x] = row[x] ^ qr_code._MASKS[mask](x, y) ^ qr_code._MASKS[candidate](x, y)
            qr_code._write_format(copy, function, qr_code.format_bits(ecc, candidate), len(copy))
            scores.append(qr_code.penalty(copy))
        self.assertEqual(scores[mask], min(scores))


class RoundTripTests(unittest.TestCase):
    TEXTS = (URL, 'a', 'Petoken 通知', 'https://ntfy.sh/' + 'x' * 100, 'ñandú ✓ ' * 8)

    def test_every_text_and_level_reads_back(self):
        for text in self.TEXTS:
            for ecc in 'LMQH':
                with self.subTest(text=text[:20], ecc=ecc):
                    matrix = qr_code.encode(text, ecc)
                    read_ecc, version, codewords = read_codewords(matrix)
                    self.assertEqual(read_ecc, ecc)
                    self.assertEqual(len(codewords), RAW_CODEWORDS[version])
                    blocks, checks = deinterleave(codewords, version, ecc)
                    for block, check in zip(blocks, checks):
                        self.assertEqual(qr_code.reed_solomon(block, len(check)), check)
                    self.assertEqual(decode_byte_mode(blocks, version), text)

    def test_padding_bytes_alternate(self):
        data = qr_code._data_codewords(b'hi', 1, 'L')
        self.assertEqual(len(data), 19)
        self.assertEqual(data[:4], [0x40, 0x26, 0x86, 0x90])
        self.assertEqual(data[4:8], [0xEC, 0x11, 0xEC, 0x11])

    def test_every_version_is_reached_and_round_trips(self):
        seen = set()
        for length in range(1, 272, 9):
            text = ''.join(chr(97 + (i * 7) % 26) for i in range(length))
            matrix = qr_code.encode(text, 'L')
            _, version, codewords = read_codewords(matrix)
            seen.add(version)
            blocks, checks = deinterleave(codewords, version, 'L')
            self.assertEqual(decode_byte_mode(blocks, version), text)
        self.assertEqual(seen, set(range(1, 11)))


class ImageTests(unittest.TestCase):
    def test_qimage_size_and_colours(self):
        matrix = qr_code.encode(URL, 'M')
        image = qr_code.to_qimage(matrix, scale=5, border=3)
        self.assertEqual(image.width(), (len(matrix) + 6) * 5)
        self.assertEqual(image.height(), image.width())
        self.assertEqual(image.pixelColor(0, 0).name(), '#ffffff')
        self.assertEqual(image.pixelColor(3 * 5 + 2, 3 * 5 + 2).name(), '#000000')   # Finder corner.

    def test_default_size(self):
        matrix = qr_code.encode('hi', 'L')
        image = qr_code.to_qimage(matrix)
        self.assertEqual(image.width(), (21 + 8) * 8)


if __name__ == '__main__':
    unittest.main()
