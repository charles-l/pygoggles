from typing import *
from dataclasses import dataclass, field

class Piece:
    __slots__ = ('type', 'offset', 'length')
    def __init__(self, ty, offset, length):
        self.type, self.offset, self.length = ty, offset, length

class PieceTable:
    def __init__(self, original):
        self.original = original
        self._add = ""
        self._table = [Piece('original', 0, len(original))]

    def _piece_index(self, buffer_offset) -> int:
        '''returns piece index and buffer offset'''
        if buffer_offset < 0:
            raise ValueError('out of bounds')

        remaining_offset = buffer_offset
        for i, piece in enumerate(self._table):
            if remaining_offset <= piece.length:
                return i
            remaining_offset -= piece.length

        raise ValueError('out of bounds')

    def insert(self, s, offset):
        if not s:
            return

        add_offset = len(self._add)
        self._add += s

        i = self._piece_index(offset)
        piece = self._table[i]

        if piece.type == 'add' and offset == piece.offset + piece.length and piece.offset + piece.length == add_offset:
            piece.length += len(s)
            return

        new_pieces = [x for x in (
            Piece(piece.type, piece.offset, offset - piece.offset),
            Piece('add', add_offset, len(s)),
            Piece(piece.type, offset, piece.length - (offset - piece.offset))
            ) if x.length > 0]

        self._table = self._table[:i] + new_pieces + self._table[i+1:]

    def delete(self, offset, length):
        if length == 0:
            return

        if offset < 0:
            raise ValueError('out of bounds')

        i = _piece_index(offset)
        j = _piece_index(offset + length)

        if i == j:
            piece = self._table[i]
            if offset == piece.offset:
                piece.offset += length
                piece.length -= length
                return

            if offset + length == piece.offset + piece.length:
                piece.length -= length
                return

        delete_pieces = [x for x in (
            Piece(self._table[i].type, self._table[i].offset, offset - self._table[i].offset),
            Piece(self._table[j].type, offset + length, self._table[j].length - (offset + length - self._table[j].offset))
            ) if x.length > 0]

        self._table = self._table[:i] + delete_pieces + self._table[j+1:]

    def as_str(self):
        s = ""
        for piece in self._table:
            if piece.type == 'add':
                s += self._add[piece.offset:piece.offset+piece.length]
            elif piece.type == 'original':
                s += self.original[piece.offset:piece.offset+piece.length]
        return s

