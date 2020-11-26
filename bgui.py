'''
MVP
* can insert records into a SQLite database to create a calculator
* events are inserted into a table to be dealt with by the client application
* client/server GUI design??!! GUIs as a Service??! What the frick am I even doing anymore...

DESIGN IDEAS
* We need an easy way of creating GUIs. Rather than some overly complicated IPC, just add records to a database.
* Widget state is stored in a database table rather than some tree structure
* Semantic and visual properties are split into two locations -- need to ponder more what this means
* GUI just takes the state of the DB and renders it to the screen

IS THIS OVERLY COMPLICATED? LETS IMPLEMENT IT AND FIND OUT
'''

import contextlib, glfw, skia
import traceback
import random
import sqlite_utils
from OpenGL import GL

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

db = sqlite_utils.Database(':memory:')
db['gui_status'].insert_all([{'name': 'scroll_x', 'value': 0},
                             {'name': 'scroll_y', 'value': 0}], pk='name')

db['widget'].create({'text': str, 'x': int, 'y': int, 'width': int, 'height': int})

typeface = skia.Typeface('Arial')
font = skia.Font(typeface, 14, 1, 0)
font.setEdging(skia.Font.Edging.kAntiAlias)

def add_widget(text):
    y = (db.execute('select max(y) from widget').fetchone()[0] or 0) + 30
    x = 10
    db['widget'].insert({'text': text, 'x': x, 'y': y, 'width': 100, 'height': 20})

with glfw_window() as window:
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)

    def scroll_callback(_win, dx, dy):
        new_scroll_x = db['gui_status'].get('scroll_x')['value'] + dx
        db['gui_status'].update('scroll_x', {'value': new_scroll_x})

        new_scroll_y = db['gui_status'].get('scroll_y')['value'] + dy
        db['gui_status'].update('scroll_y', {'value': new_scroll_y})

        render_gui()

    glfw.set_scroll_callback(window, scroll_callback)

    def render_gui():
        try:
            with skia_surface(window) as surface:
                with surface as canvas:
                    canvas.clear(skia.Color(0, 0, 0))
                    scroll = db['gui_status'].get('scroll_x')['value'], db['gui_status'].get('scroll_y')['value']
                    canvas.translate(*scroll)
                    for widget in db['widget'].rows:
                        blob = skia.TextBlob.MakeFromString(widget['text'], font)
                        canvas.save()
                        canvas.drawRect(skia.Rect(widget['x'], widget['y'], widget['x']+widget['width'], widget['y']+widget['height']),
                                        skia.Paint(AntiAlias=True, Style=skia.Paint.kFill_Style, Color=skia.ColorBLUE))
                        canvas.clipRect(skia.Rect(widget['x'], widget['y'], widget['x']+widget['width'], widget['y']+widget['height']))
                        canvas.drawTextBlob(blob, widget['x'], widget['y']+widget['height'], skia.Paint(AntiAlias=True, Color=skia.Color(255, 255, 255)))
                        canvas.restore()
                surface.flushAndSubmit()
                glfw.swap_buffers(window)
        except Exception as e:
            traceback.print_exc()

    db.register_function(render_gui)
    db.execute('''
    create trigger re_render_gui_insert after insert on widget begin
        select render_gui();
    end
    ''')
    db.execute('''
    create trigger re_render_gui_delete after delete on widget begin
        select render_gui();
    end
    ''')
    db.execute('''
    create trigger re_render_gui_update after update on widget begin
        select render_gui();
    end
    ''')

    add_widget('test')
    add_widget('test2')

    while (glfw.get_key(window, glfw.KEY_ESCAPE) != glfw.PRESS
        and not glfw.window_should_close(window)):
        if glfw.get_key(window, glfw.KEY_F) == glfw.PRESS:
            add_widget('hi')
        glfw.wait_events()
