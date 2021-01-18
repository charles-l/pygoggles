import contextlib
import glfw # type: ignore
import skia # type: ignore
import traceback
import random
import math
from dataclasses import dataclass
from OpenGL import GL # type: ignore
from typing import *
from functools import lru_cache
from buffer import Buffer

font = skia.Font(skia.Typeface('Liberation Mono'), 14)
line_height = font.getSpacing()
col_width = font.getWidths([ord('x')])[0]


def clamp(l, u, v):
    return max(min(v, u), l)


@dataclass
class Cell:
    input: Buffer
    output: str


target_scroll = [0, 0]


def scroll(x, y):
    lines = 100  # FIXME
    target_scroll[0] = x
    target_scroll[1] = y

    # clamp along y axis
    if target_scroll[1] > 0:
        target_scroll[1] = 0
    if target_scroll[1] - HEIGHT < -(line_height * lines):
        target_scroll[1] = -line_height * lines + HEIGHT


def scroll_to_line(i):
    scroll(target_scroll[0], -line_height * i)


input_paint = skia.Paint(AntiAlias=True, Color=skia.ColorBLACK)
output_paint = skia.Paint(AntiAlias=True, Color=skia.ColorGRAY)

WIDTH, HEIGHT = 640, 480


@contextlib.contextmanager
def glfw_window():
    if not glfw.init():
        raise RuntimeError('glfw.init() failed')
    glfw.window_hint(glfw.STENCIL_BITS, 8)
    window = glfw.create_window(WIDTH, HEIGHT, '', None, None)
    glfw.make_context_current(window)
    yield window
    glfw.terminate()


@contextlib.contextmanager
def skia_surface(window):
    context = skia.GrDirectContext.MakeGL()
    backend_render_target = skia.GrBackendRenderTarget(
        WIDTH,
        HEIGHT,
        0,  # sampleCnt
        0,  # stencilBits
        skia.GrGLFramebufferInfo(0, GL.GL_RGBA8))
    surface = skia.Surface.MakeFromBackendRenderTarget(
        context, backend_render_target, skia.kBottomLeft_GrSurfaceOrigin,
        skia.kRGBA_8888_ColorType, skia.ColorSpace.MakeSRGB())
    assert surface is not None
    yield surface
    context.abandonContext()


@dataclass
class Cursor:
    _buf: Buffer
    _pos: int = 0

    @property
    def column(self):
        return self._buf.col(self._pos)

    @column.setter
    def column(self, v):
        line_start = self._buf.pos_for_line(self.line)
        line_len = self._buf.line_length(self.line) - 1
        self._pos = clamp(line_start, line_start + line_len, line_start + v)

    @property
    def line(self):
        return self._buf.line(self._pos)

    @line.setter
    def line(self, n):
        if 0 <= n < self._buf.nlines():
            c = self.column
            self._pos = self._buf.pos_for_line(n)
            self.column = c


cells: List[Cell] = []
cells.append(Cell(Buffer('some\ninput\nhere\n'), 'some output'))
cells.append(Cell(Buffer('some\nmore\ninput\nhere'), 'some output'))

cur_cell = 0
cursor = Cursor(cells[cur_cell].input)

event_pipe = []

with glfw_window() as window:
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)

    def char_callback(_win, c):
        event_pipe.append(('key_press', chr(c)))

    def key_callback(_win, k, scancode, action, mods):
        if k == glfw.KEY_BACKSPACE and action == glfw.PRESS:
            event_pipe.append(('key_press', 'backspace'))
        elif k == glfw.KEY_ENTER and action == glfw.PRESS:
            event_pipe.append(('key_press', 'enter'))
        elif k == glfw.KEY_UP and action == glfw.PRESS:
            event_pipe.append(('key_press', 'up'))
        elif k == glfw.KEY_DOWN and action == glfw.PRESS:
            event_pipe.append(('key_press', 'down'))
        elif k == glfw.KEY_LEFT and action == glfw.PRESS:
            event_pipe.append(('key_press', 'left'))
        elif k == glfw.KEY_RIGHT and action == glfw.PRESS:
            event_pipe.append(('key_press', 'right'))

    def scroll_callback(_win, dx, dy):
        target_scroll[0] += dx * line_height * 2
        target_scroll[1] += dy * line_height * 2
        scroll(target_scroll[0] + dx * 20, target_scroll[1] + dy * 20)

    glfw.set_scroll_callback(window, scroll_callback)
    glfw.set_char_callback(window, char_callback)
    glfw.set_key_callback(window, key_callback)

    last_frame = 0
    with skia_surface(window) as surface:
        while (glfw.get_key(window, glfw.KEY_ESCAPE) != glfw.PRESS
               and not glfw.window_should_close(window)):

            current_frame = glfw.get_time()
            dt = current_frame - last_frame
            last_frame = current_frame

            glfw.poll_events()

            while event_pipe:
                event_type, *args = event_pipe.pop(0)
                if event_type == 'key_press':
                    if args[0] == 'enter':
                        cells[cur_cell].input.insert('\n', cursor._pos)
                        cursor._pos += 1
                    elif args[0] == 'down':
                        cursor.line += 1
                    elif args[0] == 'up':
                        cursor.line -= 1
                    elif args[0] == 'right':
                        cursor.column += 1
                    elif args[0] == 'left':
                        cursor.column -= 1
                    elif args[0] == 'backspace':
                        if cursor._pos - 1 >= 0:
                            cells[cur_cell].input.delete(cursor._pos-1, 1)
                            cursor._pos -= 1
                    else:
                        cells[cur_cell].input.insert(args[0], cursor._pos)
                        cursor._pos += 1

            with surface as canvas:
                # ensure cursor is visible
                target_scroll[1] = clamp(
                    cursor.line * -line_height, (cursor.line + 2) * -line_height + HEIGHT, target_scroll[1])

                M = canvas.getTotalMatrix()
                if abs(target_scroll[1] - M.getTranslateY()) > 2:
                    canvas.translate(
                        0, (target_scroll[1] - M.getTranslateY()) * 0.2)
                elif abs(target_scroll[1] - M.getTranslateY()) > 1:  # snap
                    canvas.translate(0, target_scroll[1] - M.getTranslateY())

                canvas.clear(skia.Color(255, 255, 255))
                line = 1
                for c in cells:
                    for l in c.input.as_str().split('\n'):
                        canvas.drawString(
                            l, 0, line_height * line, font, input_paint)
                        line += 1
                    for l in c.output.split('\n'):
                        canvas.drawString(
                            l, 0, line_height * line, font, output_paint)
                        line += 1
                # draw cursor
                canvas.drawRect(skia.Rect.MakeXYWH(
                    cursor.column * col_width, cursor.line * line_height + 4, 2, line_height), input_paint)
            surface.flushAndSubmit()
            glfw.swap_buffers(window)
