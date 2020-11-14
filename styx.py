from tkinter import *
import sys
import ast
import uuid
import os
from dataclasses import dataclass, field
import pyinotify # type: ignore
import importlib

context_globals = {}
context_locals = {}
definitions = {}
references = {}
imports = {}

class OnWriteHandler(pyinotify.ProcessEvent):
    def process_IN_MODIFY(self, event):
        print('==> Modification detected', event.pathname)
        if event.pathname in imports:
            for c in imports[event.pathname]:
                print('rerunning', c.textbox.get('0.0', 'end'))
                c.run(rerun_imports=True)

watch_manager = pyinotify.WatchManager()
# TODO: use pyinotify.Notifier instead
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

@dataclass
class Cell:
    output_text: StringVar
    textbox: Text
    _hash: uuid.UUID = field(default_factory=uuid.uuid1)

    def __hash__(self):
        return hash(self._hash)

    @property
    def code(self):
        return self.textbox.get('0.0', 'end')

    def run(self, rerun_imports=False):
        program_text = self.textbox.get('0.0', 'end')

        tree = ast.parse(program_text, mode='exec')
        v = FindReferencesAndAssignments()
        v.visit(tree)

        for a in v.assigns:
            if a in definitions and definitions[a] != self:
                raise Exception(f'{a} is already defined')
            definitions[a] = self

        for r in v.references:
            if r not in references:
                references[r] = set()
            references[r].add(self)

        for module_name, module_alias in v.import_statements.items():
            was_imported, module = _get_field(module_alias, context_locals)

            if was_imported:
                path = module.__file__
                if rerun_imports:
                    print('reimporting ', module)
                    importlib.reload(module)
                imports[path].add(self)
            else:
                if module_name != module_alias:
                    exec(f'import {module_name} as {module_alias}', context_globals, context_locals)
                else:
                    exec(f'import {module_name}', context_globals, context_locals)

                was_imported, module = _get_field(module_alias, context_locals)
                assert was_imported, "Uh... it should have been imported with the previous exec??"

                path = module.__file__

                imports[path] = set()
                # TODO: recursively parse python module dependencies
                #       so if any files change, the entire thing gets reimported
                watch_manager.add_watch(os.path.dirname(path), pyinotify.IN_MODIFY)

        result = exec_block(tree)
        self.output_text.set(repr(result))

        for ref in v.assigns + list(v.import_statements.values()):
            for cell in references.get(ref, set()):
                if cell != self: # TODO: detect and prevent cycles
                    cell.run()

def exec_block(block):
    # assumes last node is an expression
    if isinstance(block.body[-1], ast.Expr):
        last = ast.Expression(block.body.pop().value)

        exec(compile(block, '<string>', mode='exec'), context_globals, context_locals)
        return eval(compile(last, '<string>', mode='eval'), context_globals, context_locals)
    else:
        exec(compile(block, '<string>', mode='exec'), context_globals, context_locals)
        return None


class FindReferencesAndAssignments(ast.NodeVisitor):
    def __init__(self):
        self.assigns = []
        self.references = []
        self.import_statements = {}

    def visit_Import(self, node):
        for x in node.names:
            # use an import alias if there is one
            self.import_statements[x.name] = x.asname if x.asname else x.name

    def visit_Assign(self, node):
        self.assigns.extend(x.id for x in node.targets)

    def visit_Name(self, node):
        self.references.append(node.id)

root = Tk()
canvas = Canvas(root, width=650, height=600)
canvas.pack(side=LEFT, expand=YES, fill=BOTH)
scrollbar = Scrollbar(root, command=canvas.yview)
scrollbar.pack(side=LEFT, fill='y')
canvas.configure(yscrollcommand=scrollbar.set)
def update_scroll_region():
    canvas.configure(scrollregion=canvas.bbox('all'))
canvas.bind('<Configure>', lambda _: update_scroll_region())

def generate_cell(frame):
    textarea = Text(frame, height=10)
    textarea.pack()
    textvar = StringVar()
    cell = Cell(textvar, textarea)
    l = Label(frame, textvariable=textvar)

    textarea.bind('<Control-Return>', lambda _event: cell.run())
    l.pack()

    return cell

frame = Frame(canvas)
canvas.create_window((0, 0), window=frame, anchor='nw')

generate_cell(frame)
generate_cell(frame)

def add_cell():
    generate_cell(frame)
    update_scroll_region()

add_cell_button = Button(root, text='Add cell', command = add_cell)
add_cell_button.pack()

root.mainloop()

# TODO: throw error/cleanup when a variable gets undefined
# TODO: extend so that graphical results can be printed
# TODO: extend so you can inject it into another python script
#       (maybe even attach to a process?) so that you can have cells
#       run before/after/around another function (aspect oriented style)
#       allowing you to debug code more easily
# TODO: add persisting cells/results
# TODO: add performance tracking (with graphs, and historized runs)
# TODO: add ability to convert cell with output into an expect test
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
