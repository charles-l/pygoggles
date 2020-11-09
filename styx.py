from tkinter import *
from tkinter import ttk
import sys
import ast
import uuid
from dataclasses import dataclass, field

context_globals = {}
context_locals = {}
definitions = {}
references = {}

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

    def run(self):
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

        #print(definitions, references)

        result = exec_then_eval(tree)
        self.output_text.set(repr(result))

        for a in v.assigns:
            for c in references.get(a, set()):
                if c != self: # TODO: detect and prevent cycles
                    c.run()

def exec_then_eval(block):
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

# TODO: extend so that graphical results can be printed
# TODO: extend so you can inject it into another python script
#       (maybe even attach to a process?) so that you can have cells
#       run before/after/around another function (aspect oriented style)
#       allowing you to debug code more easily
# TODO: build a section() helper, so you can annotate code more easily:
#
#         some code
#         with section('some chunk'):
#           some code
#         some code
