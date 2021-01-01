from tkinter import *
import tkinter.ttk as ttk
import sys
import ast
import uuid
import os
import io
import pyinotify # type: ignore
import textwrap
import importlib
import traceback

pretty_printer = {}
cell_imports = {}
imported_modules = {}

class OnWriteHandler(pyinotify.ProcessEvent):
    def process_IN_MODIFY(self, event):
        print('==> Modification detected', event.pathname)
        print(cell_imports)
        if event.pathname in cell_imports:
            for c in cell_imports[event.pathname]:
                print('rerunning', c.textbox.get('0.0', 'end'))
                c.run(rerun_imports=True)

watch_manager = pyinotify.WatchManager()
import_file_notifier = pyinotify.ThreadedNotifier(watch_manager, OnWriteHandler())
import_file_notifier.start()

def _get_field(name, context):
    '''Lookup a field in a context using its name, properly traversing
       fields/values (i.e. `some_obj.field` or `some_obj['field']`). Returns
       bool indicating whether the value is defined and the associated
       value if it is.'''
    subfields = name.split('.')
    c = context
    for i, f in enumerate(subfields):
        if type(c) == dict and f in c:
            c = c[f]
        elif hasattr(c, f):
            c = getattr(c, f)
        else:
            return False, None
    return True, c

def selectable_text(frame, text, **kwargs):
    r = Text(frame, borderwidth=0, **kwargs)

    def focus_text(event):
        r.config(state='normal')
        r.focus()
        r.config(state='disabled')

    r.insert(1.0, text)
    r.configure(state='disabled')
    r.bind('<Button-1>', focus_text)
    return r

def object_treeview(frame, obj, root_name='result'):
    tree = ttk.Treeview(frame)

    tree['columns'] = ('value',)
    tree.column('#0', width=90, anchor='c')
    tree.column('value', width=90, anchor='se')

    tree.heading('#0', text='field')
    tree.heading('value', text='value')

    root = tree.insert('', 1, text=root_name, values=(repr(obj),))

    def f(node, obj, visited=set()):
        if id(obj) in visited:
            return
        visited.add(id(obj))

        d = {}
        if isinstance(obj, dict):
            d = obj
        elif isinstance(obj, list):
            d = dict(zip(range(len(obj)), obj))
        elif hasattr(obj, '__dict__'):
            d = obj.__dict__

        for k, v in d.items():
            print(k, v)
            new_node = tree.insert(node, 'end', text=str(k), values=(repr(v),))
            f(new_node, v)

    f(root, obj)
    return tree

class Cell:
    def __init__(self, frame):
        self.textbox = Text(frame, height=10)
        self.textbox.pack()

        def f(event):
            self.run()
            return "break"
        self.textbox.bind('<Control-Return>', f)

        self.output_frame = Frame(frame)
        self.output_frame.pack()

        self._hash = uuid.uuid1()

    def __hash__(self):
        return hash(self._hash)

    @property
    def code(self):
        return self.textbox.get('0.0', 'end')

    def run(self, rerun_imports=False):
        program_text = self.textbox.get('0.0', 'end')
        context_globals = {}
        context_locals = {}

        try:
            tree = ast.parse(program_text, mode='exec')
            v = FindImports()
            v.visit(tree)

            for module_name, module_alias in v.import_statements.items():
                was_imported, module = _get_field(module_alias, imported_modules)

                if was_imported:
                    if hasattr(module, '__file__'):
                        path = module.__file__
                        if rerun_imports:
                            print('reimporting ', module)
                            importlib.reload(module)
                        cell_imports[path].add(self)
                    else:
                        print(f'warning: skipping watch for {module_alias}. It has no file.')
                else:
                    print('importing ', module_name)

                    # FIXME won't work with e.g. `import module.submodule` because of the dot
                    if '.' in module_name:
                        raise Exception("can't import submodules at the moment -- import the module with an alias")

                    imported_modules[module_alias] = importlib.import_module(module_name)

                    was_imported, module = _get_field(module_alias, imported_modules)

                    if hasattr(module, '__file__'):
                        path = module.__file__

                        cell_imports[path] = set([self])
                        # TODO: recursively parse python module dependencies
                        #       so if any files change, the entire thing gets reimported
                        watch_manager.add_watch(os.path.dirname(path), pyinotify.IN_MODIFY)
                    else:
                        print(f'warning: skipping watch for {module_alias}. It has no file.')

            # clear out the previous results from the output frame
            for child in self.output_frame.winfo_children():
                child.destroy()

            result = exec_block(tree, context_globals,
                                # only include the modules that were imported in this cell
                                {**{name: mod for name, mod in imported_modules.items() if mod in v.import_statements.values()},
                                 **context_locals})
        except Exception as e:
            # clear out the previous results from the output frame
            for child in self.output_frame.winfo_children():
                child.destroy()
            selectable_text(self.output_frame, text=traceback.format_exc(), bg='red', height=10).pack()
        else:
            if type(result) in pretty_printer:
                print("Pretty printer available for ", type(result))
                pretty_printer[type(result)](self, result)
            else:
                out_text = selectable_text(self.output_frame, repr(result), height=10)
                out_text.pack()

                object_treeview(self.output_frame, result).pack(fill=X)

def exec_block(block, context_globals, context_locals):
    # assumes last node is an expression
    if isinstance(block.body[-1], ast.Expr):
        last = ast.Expression(block.body.pop().value)

        exec(compile(block, '<string>', mode='exec'), context_globals, context_locals)
        return eval(compile(last, '<string>', mode='eval'), context_globals, context_locals)
    else:
        exec(compile(block, '<string>', mode='exec'), context_globals, context_locals)
        return None

def serialize_cells(stream, cells):
    # TODO: store AST in Cell and serialize that instead. This will come
    #       with challenges since the AST won't include comments, but it's
    #       cleaner.

    cells_node = ast.List(elts=[], ctx=ast.Load())
    result_tree = ast.Module(body=[
        # cells = [...]
        ast.Assign(targets=[ast.Name(id='cells', ctx=ast.Store())], value=cells_node, lineno=1)
        ], type_ignores=[])

    for i, cell in enumerate(cells):
        text = cell.textbox.get('0.0', 'end')
        tree = ast.parse(text, mode='exec')
        result_tree.body.append(ast.FunctionDef(name=f'cell_{i}',
                        decorator_list=[],
                        args=ast.arguments(args=[], posonlyargs=[], defaults=[], kwonlyargs=[]),
                        lineno=i,
                        body=tree.body or [ast.Pass()]))
        cells_node.elts.append(ast.Name(id=f'cell_{i}', ctx=ast.Store()))

    stream.write(
        textwrap.dedent('''\
        # DO NOT EDIT
        # This file is autogenerated by pygoggles
        '''))
    stream.write(ast.unparse(result_tree))

def save_file(filename):
    print('saved', filename)
    with open(filename, 'w') as f:
        serialize_cells(f, cells)

class FindImports(ast.NodeVisitor):
    def __init__(self):
        self.import_statements = {}

    def visit_Import(self, node):
        for x in node.names:
            # use an import alias if there is one
            self.import_statements[x.name] = x.asname if x.asname else x.name

root = Tk()
canvas = Canvas(root, width=650, height=600)
canvas.pack(side=LEFT, expand=YES, fill=BOTH)
scrollbar = Scrollbar(root, command=canvas.yview)
scrollbar.pack(side=LEFT, fill='y')
canvas.configure(yscrollcommand=scrollbar.set)
def update_scroll_region():
    canvas.configure(scrollregion=canvas.bbox('all'))
canvas.bind('<Configure>', lambda _: update_scroll_region())

frame = Frame(canvas)
canvas.create_window((0, 0), window=frame, anchor='nw')
cells = []

def add_cell():
    cells.append(Cell(frame))
    update_scroll_region()

add_cell()
add_cell()

add_cell_button = Button(root, text='Add cell', command = add_cell)
add_cell_button.pack()

save_button = Button(root, text='Save', command = lambda: save_file('cells.py'))
save_button.pack()

## PRETTY PRINTER

try:
    import numpy
except ModuleNotFoundError:
    pass
else:
    def numpy_printer(cell: Cell, arr: numpy.array):
        if len(arr.shape) == 2:
            for row in range(arr.shape[0]):
                for col in range(arr.shape[1]):
                    Label(cell.output_frame, text=str(arr[row, col]), borderwidth=1).grid(row=row, column=col)
        else:
            # hacky fallback
            Label(cell.output_frame, text=repr(arr)).pack()

    pretty_printer[numpy.ndarray] = numpy_printer

sys.path.append(os.getcwd())

root.mainloop()
import_file_notifier.stop()

# TODO: support reloading loaded objects with from mod import *
# TODO: capture stdout
# TODO: try to make it as trivial to add new cases as adding a line in a REPL.
#       basically, make it a REPL that reruns every line in the history on
#       dependency changes.
# TODO: extend so that graphical results can be printed
# TODO: extend so you can inject it into another python script
#       (maybe even attach to a process?) so that you can have cells
#       run before/after/around another function (aspect oriented style)
#       allowing you to debug code more easily
# TODO: add persisting cells/results
# TODO: add performance tracking (with graphs, and historized runs)
# TODO: add ability to convert cell with output into an expect test (serialize output to pickle and save string?)
# TODO: add editor integration so that you can hover on a function and
#       see what's happening live
# TODO: add history functionality so that code with its inputs and outputs can be
#       scrobbled through over time (a lightweight undo/redo source control thing?)
# TODO: build a section() helper, so you can annotate code more easily:
#
#         some code
#         with section('some chunk'):
#           some code
#         some code
