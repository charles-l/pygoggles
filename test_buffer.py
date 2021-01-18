from buffer import Buffer
import unittest

class TestBuffer(unittest.TestCase):
    def test_line_and_col_with_one_char_line(self):
        b = Buffer('a\nb\nc')
        lines =    '00 11 2'.replace(' ', '')
        col   =    '01 01 0'.replace(' ', '')
        for i in range(len(lines)):
            self.assertEqual(int(lines[i]), b.line(i))
            self.assertEqual(int(col[i]), b.col(i))

    def test_line_and_col_with_variable_line_length(self):
        b = Buffer('abc\ndefgh\nij\n')
        lines =    '0000 111111 222'.replace(' ', '')
        col   =    '0123 012345 012'.replace(' ', '')
        for i in range(len(lines)):
            self.assertEqual(int(lines[i]), b.line(i))
            self.assertEqual(int(col[i]), b.col(i))

    def test_line_and_col_with_empty_line(self):
        b = Buffer('abc\n\ndefgh\n')
        lines =    '0000 1 222222'.replace(' ', '')
        col   =    '0123 0 012345'.replace(' ', '')
        for i in range(len(lines)):
            self.assertEqual(int(lines[i]), b.line(i))
            self.assertEqual(int(col[i]), b.col(i))
