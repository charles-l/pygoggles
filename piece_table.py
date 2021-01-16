# based on https://github.com/sparkeditor/piece-table/blob/master/index.js
from typing import *
from dataclasses import dataclass, field

class Piece:
    __slots__ = ('type', 'offset', 'length')
    def __init__(self, ty, offset, length):
        self.type, self.offset, self.length = ty, offset, length

    def __repr__(self):
        return f'Piece<{self.type=} {self.offset=} {self.length=}>'

class PieceTable:
    def __init__(self, original):
        self.original = original
        self._add = ""
        self._table = [Piece('original', 0, len(original))]

    def _piece_index(self, buffer_offset) -> int:
        '''returns piece index and offset into the pieces buffer'''
        if buffer_offset < 0:
            raise ValueError('out of bounds')

        remaining_offset = buffer_offset
        for i, piece in enumerate(self._table):
            if remaining_offset <= piece.length:
                return i, piece.offset + remaining_offset
            remaining_offset -= piece.length

        raise ValueError('out of bounds')

    def insert(self, s, offset):
        if not s:
            return

        add_offset = len(self._add)
        self._add += s

        i, buf_offset = self._piece_index(offset)
        piece = self._table[i]

        if piece.type == 'add' and buf_offset == piece.offset + piece.length and piece.offset + piece.length == add_offset:
            piece.length += len(s)
            return

        new_pieces = [x for x in (
            Piece(piece.type, piece.offset, buf_offset - piece.offset),
            Piece('add', add_offset, len(s)),
            Piece(piece.type, buf_offset, piece.length - (buf_offset - piece.offset))
            ) if x.length > 0]

        self._table = self._table[:i] + new_pieces + self._table[i+1:]

    def delete(self, offset, length):
        if length == 0:
            return

        if offset < 0:
            raise ValueError('out of bounds')

        i, i_buf_offset = self._piece_index(offset)
        j, j_buf_offset = self._piece_index(offset + length)

        if i == j:
            piece = self._table[i]
            if i_buf_offset == piece.offset:
                piece.offset += length
                piece.length -= length
                return

            if j_buf_offset == piece.offset + piece.length:
                piece.length -= length
                return

        delete_pieces = [x for x in (
            Piece(self._table[i].type, self._table[i].offset, i_buf_offset - self._table[i].offset),
            Piece(self._table[j].type, j_buf_offset, self._table[j].length - (j_buf_offset - self._table[j].offset))
            ) if x.length > 0]

        self._table = self._table[:i] + delete_pieces + self._table[j+1:]

        # if the table is empty, put a 0-length piece in there so we have at least one piece.
        if not self._table:
            self._table = [Piece('original', 0, 0)]

    def as_str(self):
        s = ""
        for piece in self._table:
            if piece.type == 'add':
                s += self._add[piece.offset:piece.offset+piece.length]
            elif piece.type == 'original':
                s += self.original[piece.offset:piece.offset+piece.length]
        return s

