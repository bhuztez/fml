from . import ast
from .asm import Label
from .symbol import SymbolTable, ForLoopBlockSymbolTable, BlockSymbolTable, Global
from .error import Error
from dataclasses import fields


class ScopeVisitor(Error, ast.Visitor):

    def visit_function(self, node, symtable):
        symtable = SymbolTable(symtable)
        self.visit(node.pars, symtable)
        self.visit(node.body, symtable)
        node.symtable = symtable

    @_(str, bool, int, type(None),
       ast.Break,
       ast.NIL, ast.FALSE, ast.TRUE,
       ast.Number, ast.String)
    def visit(self, node, symtable):
        pass

    @_(ast.Goto)
    def visit(self, node, symtable):
        node._symtable = symtable
        node._nlocals = len(symtable.locals)

    @_(ast.Label)
    def visit(self, node, symtable):
        exist = symtable.labels.get(node.name, None)
        if exist is not None:
            self.error(node, f"label {node.name!r} already defined on line {exist.lineno}")
        symtable.labels[node.name] = node
        node._label = Label()
        node._nlocals = len(symtable.locals)

    @_(ast.ExpressionList, ast.Assign,
       ast.CallStatement, ast.Call, ast.Return, ast.Break,
       ast.Subscript, ast.Attribute, ast.Method, ast.Field)
    def visit(self, node, symtable):
        for field in fields(node):
            self.visit(getattr(node, field.name), symtable)

    @_(list)
    def visit(self, node, symtable):
        for subnode in node:
            self.visit(subnode, symtable)

    @_(ast.File)
    def visit(self, node, symtable):
        symtable = SymbolTable(symtable)
        symtable.table["_ENV"] = symtable.add(Global("_ENV"))
        symtable.declare_local("...")
        self.visit(node.body, symtable)
        node.symtable = symtable

    @_(ast.Parameters)
    def visit(self, node, symtable):
        for subnode in node.value:
            symtable.declare_local(subnode.id)
        symtable.declare_local('...' if node.varargs else '__...__')

    @_(ast.Function)
    def visit(self, node, symtable):
        self.visit(node.name, symtable)
        self.visit_function(node, symtable)

    @_(ast.FunctionLocal)
    def visit(self, node, symtable):
        symtable.declare_local(node.name.id)
        self.visit(node.name, symtable)
        self.visit_function(node, symtable)

    @_(ast.Lambda)
    def visit(self, node, symtable):
        self.visit_function(node, symtable)

    @_(ast.Block)
    def visit(self, node, symtable):
        symtable = BlockSymbolTable(symtable)
        self.visit(node.body, symtable)

    @_(ast.If)
    def visit(self, node, symtable):
        self.visit(node.test, symtable)
        self.visit(node.body, BlockSymbolTable(symtable))
        self.visit(node.orelse, BlockSymbolTable(symtable))

    @_(ast.While)
    def visit(self, node, symtable):
        self.visit(node.test, symtable)
        symtable = BlockSymbolTable(symtable)
        self.visit(node.body, symtable)

    @_(ast.Repeat)
    def visit(self, node, symtable):
        symtable = BlockSymbolTable(symtable)
        self.visit(node.body, symtable)
        self.visit(node.test, symtable)

    @_(ast.For)
    def visit(self, node, symtable):
        node._forprep = symtable.add(Global("forprep"))
        self.visit(node.start, symtable)
        self.visit(node.stop, symtable)
        self.visit(node.step, symtable)
        node._loopvar = symtable.get_loopvar()

        symtable = ForLoopBlockSymbolTable(symtable)
        symtable.declare_local(node.target.id)
        self.visit(node.target, symtable)
        self.visit(node.body, symtable)

    @_(ast.ForEach)
    def visit(self, node, symtable):
        self.visit(node.iter, symtable)
        node._loopvar = symtable.get_loopvar()
        symtable = ForLoopBlockSymbolTable(symtable)
        for subnode in node.target:
            symtable.declare_local(subnode.id)
        self.visit(node.target, symtable)
        self.visit(node.body, symtable)

    @_(ast.AssignLocal)
    def visit(self, node, symtable):
        self.visit(node.value, symtable)
        for subnode in node.target:
            symtable.declare_local(subnode.id)
        self.visit(node.target, symtable)

    @_(ast.Name)
    def visit(self, node, symtable):
        node._env = False
        symbol = symtable.find(node.id)
        if symbol is None:
            node._env = True
            symbol = symtable.find("_ENV")
        node.symbol = symbol

    @_(ast.ELLIPSIS)
    def visit(self, node, symtable):
        symbol = symtable.table.get('...')
        if symbol is None:
            self.error(node, "cannot use '...' outside a vararg function")
        assert symbol is not None
        node.symbol = symbol

    @_(ast.BinOp)
    def visit(self, node, symtable):
        node._op = symtable.add(Global(f".b{node.op}"))
        self.visit(node.left, symtable)
        self.visit(node.right, symtable)

    @_(ast.UnaryOp)
    def visit(self, node, symtable):
        node._op = symtable.add(Global(f".u{node.op}"))
        self.visit(node.operand, symtable)

    @_(ast.Table)
    def visit(self, node, symtable):
        node._luatable = symtable.add(Global("LuaTable"))
        self.visit(node.fields, symtable)

    def __init__(self, filename, text):
        self.filename = filename
        self.text = text


class GotoVisitor(Error, ast.Visitor):

    @_(ast.Goto)
    def visit(self, node):
        label, varname = node._symtable.find_label(node.target, node._nlocals)
        if label is None:
            if varname is None:
                self.error(node, f'no visible label {node.target!r}')
            else:
                self.error(node, f'jumps into the scope of local {varname!r}')

        node._label = label._label

    @_(ast.If)
    def visit(self, node):
        self.visit(node.body)
        self.visit(node.orelse)

    @_(ast.Block, ast.While, ast.Repeat,
       ast.For, ast.ForEach,
       ast.File, ast.Function, ast.FunctionLocal)
    def visit(self, node):
        self.visit(node.body)

    @_(type(None), ast.Label, ast.Assign, ast.AssignLocal,
       ast.CallStatement, ast.Return, ast.Break)
    def visit(self, node):
        pass

    @_(list)
    def visit(self, node):
        for subnode in node:
            self.visit(subnode)

    def __init__(self, filename, text):
        self.filename = filename
        self.text = text
