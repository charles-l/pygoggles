from piece_table import PieceTable
import bisect


class Buffer:
    def __init__(self, s):
        self._buf = PieceTable(s)
        self._update_line_starts(s)

    def _update_line_starts(self, s):
        self._linestarts = [0] + [i+1 for i,
                                  c in enumerate(s) if c == '\n']

    def as_str(self): return self._buf.as_str()

    def nlines(self):
        return len(self._linestarts)

    # TODO: add selection for substring
    # TODO: add iterlines

    def line(self, pos):
        return bisect.bisect_right(self._linestarts, pos) - 1

    def pos_for_line(self, n):
        assert 0 <= n < len(self._linestarts), n
        return self._linestarts[n]

    def col(self, pos):
        return pos - self._linestarts[bisect.bisect_right(self._linestarts, pos) - 1]

    def line_length(self, n):
        if n+1 < len(self._linestarts):
            return self._linestarts[n+1] - self._linestarts[n]
        else:
            # FIXME: once substr is added, get the length of the last line directly
            return len(self.as_str()) - self._linestarts[n]

    def insert(self, val, pos):
        self._buf.insert(val, pos)
        self._update_line_starts(self.as_str())

    def delete(self, pos, length):
        self._buf.delete(pos, length)
        self._update_line_starts(self.as_str())
