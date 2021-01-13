import unittest
from piece_table import PieceTable
from hypothesis import given, example
import hypothesis.strategies as st

@st.composite
def substr_insert_input(draw, s):
    sub = draw(st.text())
    i = draw(st.integers(min_value=0, max_value=len(s)))
    return (s, sub, i)

@st.composite
def substr_delete_input(draw, s):
    start_i = draw(st.integers(min_value=0, max_value=len(s)))
    len_i = draw(st.integers(min_value=0, max_value=len(s) - start_i))
    return (s, start_i, len_i)

def insert_str(s, i, u):
    return s[:i] + u + s[i:]

def delete_str(s, start, length):
    return s[:start] + s[start+length:]

class TestPieceTable(unittest.TestCase):
    @given(st.text().flatmap(lambda x: substr_insert_input(x)))
    @example(('abc', 'hi', 1)) # => ahibc
    def test_insert(self, inputs):
        s, sub, i = inputs
        new_s = insert_str(s, i, sub)
        p = PieceTable(s)
        p.insert(sub, i)
        self.assertEqual(new_s, p.as_str())

    @given(st.text().flatmap(lambda x: substr_delete_input(x)))
    @example(('abc', 1, 2)) # => a
    def test_delete(self, inputs):
        s, start, length = inputs
        new_s = delete_str(s, start, length)
        p = PieceTable(s)

    # TODO: test inserts and deletes

if __name__ == '__main__':
    unittest.main()
