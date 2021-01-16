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
        p.delete(start, length)
        self.assertEqual(new_s, p.as_str(), f'{p._table=} {p.original=} {p._add=}')

    def test_delete_2(self):
        s = 'aa'
        p = PieceTable(s)
        p.delete(0, 1)
        p.delete(0, 1)
        self.assertEqual('', p.as_str(), f'{p._table=} {p.original=} {p._add=}')

    @given(st.data())
    def test_series_of_inserts_and_deletes(self, data):
        nsteps = data.draw(st.integers(min_value=0, max_value=100), label='number of operations to perform')
        t = data.draw(st.text(), label='initial buffer')
        p = PieceTable(t)
        for step in range(nsteps):
            command = data.draw(st.sampled_from(['insert', 'delete']))
            if command == 'insert':
                _, sub, i = data.draw(substr_insert_input(t))
                t = insert_str(t, i, sub)
                p.insert(sub, i)
                self.assertEqual(t, p.as_str(), f'{step=} {p._table=} {p.original=} {p._add=}')
            elif command == 'delete':
                _, start, length = data.draw(substr_delete_input(t))
                t = delete_str(t, start, length)
                p.delete(start, length)
                self.assertEqual(t, p.as_str(), f'{step=} {p._table=} {p.original=} {p._add=}')
            else:
                assert False

if __name__ == '__main__':
    unittest.main()
