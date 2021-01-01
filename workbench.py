import contextlib, glfw, skia
import traceback
import random
import math
from dataclasses import dataclass
from OpenGL import GL

font = skia.Font(skia.Typeface('Liberation Mono'), 14)
line_height = font.getSpacing()
col_width = font.getWidths([ord('x')])[0]

def clamp(l, u, v):
    return max(min(v, u), l)

@dataclass
class Buffer:
    _doc: str = ''
    blob: skia.TextBlob = None

    @property
    def doc(self):
        return self._doc

    @doc.setter
    def doc(self, value):
        self._doc = value

        builder = skia.TextBlobBuilder()
        for i, line in enumerate(self._doc.split('\n')):
            builder.allocRun(line, font, 0, line_height * i)

        self.blob = builder.make()

buf = Buffer()
with open('/var/log/Xorg.0.log') as f:
    buf.doc = f.read()

cells = []

target_scroll = [0, 0]

def scroll(x, y):
    lines = buf.doc.count('\n')
    target_scroll[0] = x
    target_scroll[1] = y

    # clamp along y axis
    if target_scroll[1] > 0:
        target_scroll[1] = 0
    if target_scroll[1] - HEIGHT < -(line_height * lines):
        target_scroll[1] = -line_height * lines + HEIGHT

def scroll_to_line(i):
    scroll(target_scroll[0], -line_height * i)

paint = skia.Paint(AntiAlias=True, Color=skia.ColorBLACK)

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
    buf: Buffer
    _pos: int = 0

    @property
    def column(self):
        try:
            last_newline_i = self.buf.doc.rfind('\n', 0, self._pos+1)
        except ValueError:
            last_newline_i = 0
        return self._pos - last_newline_i

    @column.setter
    def column(self, v):
        self._pos = self.buf.doc.rfind('\n', 0, self._pos+1)

        try:
            line_end = self.buf.doc.index('\n', self._pos+1)
        except ValueError:
            line_end = len(self.buf)

        self._pos += clamp(0, line_end - self._pos-1, v)

    @property
    def line(self):
        return self.buf.doc.count('\n', 0, self._pos+1)

    @line.setter
    def line(self, n):
        # FIXME: can't go backwards over blank lines.
        c = self.column
        if n < 0:
            n = 0
        self._pos = 0

        for i, l in enumerate(self.buf.doc.split('\n')):
            if i == n:
                self.column = c
                return
            self._pos += len(l) + 1

    def insert(self, s):
        self.buf.doc = self.buf.doc[:self._pos+1] + s + self.buf.doc[self._pos+1:]

    def backspace(self):
        self.buf.doc = self.buf.doc[:self._pos] + self.buf.doc[self._pos+1:]

cursor = Cursor(buf)

event_pipe = []

with glfw_window() as window:
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)

    def char_callback(_win, c):
        event_pipe.append(('key_press', chr(c)))

    def key_callback(_win, k, scancode, action, mods):
        if k == glfw.KEY_BACKSPACE and action == glfw.PRESS:
            event_pipe.append(('key_press', 'backspace'))
        if k == glfw.KEY_ENTER and action == glfw.PRESS:
            event_pipe.append(('key_press', 'enter'))

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
                        cursor.insert('\n')
                        cursor.line += 1
                        cursor.column = 0
                    elif args[0] == 'j':
                        cursor.line += 1
                    elif args[0] == 'k':
                        cursor.line -= 1
                    elif args[0] == 'l':
                        cursor.column += 1
                    elif args[0] == 'h':
                        cursor.column -= 1
                    elif args[0] == 'backspace':
                        cursor.backspace()
                        cursor.column -= 1
                    else:
                        cursor.insert(args[0])
                        cursor.column += 1

                #scroll_to_line(cursor.line)

            with surface as canvas:
                # ensure cursor is visible
                target_scroll[1] = clamp(cursor.line * -line_height, (cursor.line + 2) * -line_height + HEIGHT, target_scroll[1])

                M = canvas.getTotalMatrix()
                if abs(target_scroll[1] - M.getTranslateY()) > 2:
                    canvas.translate(0, (target_scroll[1] - M.getTranslateY()) * 0.2)
                elif abs(target_scroll[1] - M.getTranslateY()) > 1:
                    canvas.translate(0, target_scroll[1] - M.getTranslateY())

                canvas.clear(skia.Color(255, 255, 255))
                canvas.drawTextBlob(buf.blob, 0, line_height, paint)
                canvas.drawRect(skia.Rect.MakeXYWH(cursor.column * col_width, cursor.line * line_height + 4, 2, line_height), paint)
            surface.flushAndSubmit()
            glfw.swap_buffers(window)

