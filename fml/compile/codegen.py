from . import ast
from .symbol import Local, Global, Free
from .asm import Assembler, Label
from enum import Enum, auto

class Context(Enum):
    Load = auto()
    Store = auto()

Load = Context.Load
Store = Context.Store


class CodegenVisitor(ast.Visitor):

    def visit_symbol(self, symbol, asm, context):
        context = {
            Context.Load: 'LOAD',
            Context.Store: 'STORE'}[context]

        if isinstance(symbol, Local):
            scope = {True: 'DEREF', False: 'FAST'}[symbol.is_referenced]
        else:
            scope = {Global: 'GLOBAL', Free: 'DEREF'}[type(symbol)]

        getattr(asm, f'{context}_{scope}')(symbol.slot)

    def visit_exp(self, node, asm):
        self.visit(node, asm, context=Load)
        if type(node) in (ast.ELLIPSIS, ast.Call):
            # TOS = TOS or (None,)
            label = Label()
            asm.JUMP_IF_TRUE_OR_POP(label)
            asm.LOAD_CONST(None)
            asm.BUILD_TUPLE(1)
            asm.emit(label)
            # TOS = TOS[0]
            asm.LOAD_CONST(0)
            asm.BINARY_SUBSCR()

    def visit_explist(self, explist, asm):
        if not explist or type(explist[-1]) not in (ast.ELLIPSIS, ast.Call):
            for subnode in explist:
                self.visit_exp(subnode, asm)
            asm.BUILD_TUPLE(len(explist))
        else:
            for subnode in explist[:-1]:
                self.visit_exp(subnode, asm)
            asm.BUILD_TUPLE(len(explist) - 1)
            self.visit(explist[-1], asm, context=Load)
            asm.BUILD_TUPLE_UNPACK(2)

    def visit_assign(self, target, asm):
        asm.LOAD_CONST(None)
        asm.BUILD_TUPLE(1)
        asm.LOAD_CONST(len(target))
        asm.BINARY_MULTIPLY()
        asm.BUILD_TUPLE_UNPACK(2)
        for subnode in target:
            asm.UNPACK_EX(1)
            self.visit(subnode, asm, context=Store)
        asm.POP_TOP()

    def visit_forloop(self, loopvar, target, body, asm):
        f, s, var = loopvar
        # local f, s, var = explist
        asm.LOAD_CONST(None)
        asm.BUILD_TUPLE(1)
        asm.LOAD_CONST(3)
        asm.BINARY_MULTIPLY()
        asm.BUILD_TUPLE_UNPACK(2)
        for symbol in loopvar:
            asm.UNPACK_EX(1)
            self.visit_symbol(symbol, asm, context=Store)
        asm.POP_TOP()

        # while true
        l_before, l_after = Label(), Label()
        asm.emit(l_before)
        # local var_1, ···, var_n = f(s,var)
        for symbol in loopvar:
            self.visit_symbol(symbol, asm, context=Load)
        asm.CALL_FUNCTION(2)
        self.visit_assign(target, asm)

        # if var_1 == nil then break
        self.visit(target[0], asm, context=Load)
        asm.LOAD_CONST(None)
        asm.COMPARE_OP(8)
        asm.POP_JUMP_IF_TRUE(l_after)

        # var = var_1
        self.visit(target[0], asm, context=Load)
        self.visit_symbol(var, asm, context=Store)
        self.visit(body, asm, break_target=l_after)
        asm.JUMP_ABSOLUTE(l_before)
        asm.emit(l_after)

    def visit_function(self, node, name, asm):
        argcount = len(node.pars.value)
        names, varnames, freenames, cellnames, freevars = node.symtable.get_slots()

        sub = Assembler()
        self.visit(node.body, sub, break_target=None)
        sub.LOAD_CONST(None)
        sub.BUILD_TUPLE(1)
        sub.RETURN_VALUE()

        code = sub.build(
            argcount,
            names, varnames,
            self.filename, name,
            node.lineno, freenames, cellnames)

        if freevars:
            for freevar in freevars:
                asm.LOAD_CLOSURE(freevar.parent.slot)
            asm.BUILD_TUPLE(len(freevars))
            asm.LOAD_CONST(code)
            asm.LOAD_CONST(name)
            asm.MAKE_FUNCTION(8)
        else:
            asm.LOAD_CONST(code)
            asm.LOAD_CONST(name)
            asm.MAKE_FUNCTION(0)

    @_(list)
    def visit(self, node, asm, break_target):
        for subnode in node:
            self.visit(subnode, asm, break_target=break_target)

    def to_boolean(self, asm):
        l1, l2 = Label(), Label()
        # if TOS is None: TOS = False
        asm.DUP_TOP()
        asm.LOAD_CONST(None)
        asm.COMPARE_OP(8)
        asm.POP_JUMP_IF_FALSE(l1)
        asm.POP_TOP()
        asm.LOAD_CONST(False)
        asm.emit(l1)
        # if TOS is not False: TOS = True
        asm.DUP_TOP()
        asm.LOAD_CONST(False)
        asm.COMPARE_OP(8)
        asm.POP_JUMP_IF_TRUE(l2)
        asm.POP_TOP()
        asm.LOAD_CONST(True)
        asm.emit(l2)

    @_(ast.File)
    def visit(self, node):
        names, varnames, freenames, cellnames, _ = node.symtable.get_slots()
        asm = Assembler()
        self.visit(node.body, asm, break_target=None)
        asm.LOAD_CONST(True)
        asm.BUILD_TUPLE(1)
        asm.RETURN_VALUE()
        return asm.build(
            0, names, varnames,
            self.filename, 'main chunk',
            node.lineno, freenames, cellnames)

    @_(ast.Function)
    def visit(self, node, asm, break_target):
        name = node.name
        if isinstance(name, ast.Attribute):
            name = name.attr
        elif isinstance(name, ast.Method):
            name = name.method

        self.visit_function(node, node.name.id, node)
        self.visit(node.name, asm, context=Store)

    @_(ast.FunctionLocal)
    def visit(self, node, asm, break_target):
        self.visit_function(node, node.name.id, node)
        self.visit(node.name, asm, context=Store)

    @_(ast.Lambda)
    def visit(self, node, asm, context):
        self.visit_function(node, '<lambda>', asm)

    @_(ast.Block)
    def visit(self, node, asm, break_target):
        self.visit(node.body, asm, break_target=break_target)

    @_(ast.If)
    def visit(self, node, asm, break_target):
        self.visit(node.test, asm)
        self.to_boolean(asm)
        l_before, l_after = Label(), Label()
        asm.POP_JUMP_IF_FALSE(l_before)
        self.visit(node.body, asm, break_target=break_target)
        asm.JUMP_ABSOLUTE(l_after)
        asm.emit(l_before)
        self.visit(node.orelse, asm, break_target=break_target)
        asm.emit(l_after)

    @_(ast.While)
    def visit(self, node, asm, break_target):
        l_before, l_after = Label(), Label()
        asm.emit(l_before)
        self.visit(node.test, asm)
        self.to_boolean(asm)
        asm.POP_JUMP_IF_FALSE(l_after)
        self.visit(node.body, asm, break_target=l_after)
        asm.JUMP_ABSOLUTE(l_before)
        asm.emit(l_after)

    @_(ast.Repeat)
    def visit(self, node, asm, break_target):
        l_before, l_after = Label(), Label()
        asm.emit(l_before)
        self.visit(node.body, asm, break_target=l_after)
        self.visit(node.test, asm)
        self.to_boolean(asm)
        asm.POP_JUMP_IF_FALSE(l_before)
        asm.emit(l_after)

    @_(ast.For)
    def visit(self, node, asm, break_target):
        self.visit_symbol(node._forprep, asm, context=Load)
        self.visit_exp(node.start, asm)
        self.visit_exp(node.stop, asm)
        self.visit_exp(node.step, asm)
        asm.CALL_FUNCTION(3)
        self.visit_forloop(node._loopvar, [node.target], node.body, asm)

    @_(ast.ForEach)
    def visit(self, node, asm, break_target):
        self.visit_explist(node.iter, asm)
        self.visit_forloop(node._loopvar, node.target, node.body, asm)

    @_(ast.Goto)
    def visit(self, node, asm, break_target):
        asm.JUMP_ABSOLUTE(node._label)

    @_(ast.Label)
    def visit(self, node, asm, break_target):
        asm.emit(node._label)

    @_(ast.Assign)
    def visit(self, node, asm, break_target):
        self.visit_explist(node.value, asm)
        self.visit_assign(node.target, asm)

    @_(ast.AssignLocal)
    def visit(self, node, asm, break_target):
        self.visit_explist(node.value, asm)
        self.visit_assign(node.target, asm)

    @_(ast.Return)
    def visit(self, node, asm, break_target):
        self.visit_explist(node.value, asm)
        asm.RETURN_VALUE()

    @_(ast.Break)
    def visit(self, node, asm, break_target):
        asm.JUMP_ABSOLUTE(break_target)

    @_(ast.CallStatement)
    def visit(self, node, asm, break_target):
        self.visit(node.body, asm)
        asm.POP_TOP()

    @_(ast.Call)
    def visit(self, node, asm, context=None):
        self.visit_exp(node.func, asm)
        extra_args = 0
        if isinstance(node.func, ast.Method):
            extra_args = 1
        # FIXME for extra_arg
        self.visit_explist(node.args.value, asm)
        asm.CALL_FUNCTION_EX(0)

    @_(ast.BinOp)
    def visit(self, node, asm, context=None):
        self.visit_symbol(node._op, asm, context=Load)
        self.visit_exp(node.left, asm)
        self.visit_exp(node.right, asm)
        asm.CALL_FUNCTION(2)

    @_(ast.UnaryOp)
    def visit(self, node, asm, context=None):
        self.visit_symbol(node._op, asm, context=Load)
        self.visit_exp(node.operand, asm)
        asm.CALL_FUNCTION(1)

    @_(ast.Name)
    def visit(self, node, asm, context):
        asm.set_lineno(node)
        if not node._env:
            self.visit_symbol(node.symbol, asm, context)
            return
        self.visit_symbol(node.symbol, asm, context=Load)
        asm.LOAD_CONST(node.id)
        if context is Load:
            asm.BINARY_SUBSCR()
        elif context is Store:
            asm.STORE_SUBSCR()

    @_(ast.ELLIPSIS)
    def visit(self, node, asm, context):
        self.visit_symbol(node.symbol, asm, context)

    @_(ast.NIL)
    def visit(self, node, asm, context):
        asm.LOAD_CONST(None)

    @_(ast.FALSE)
    def visit(self, node, asm, context):
        asm.LOAD_CONST(False)

    @_(ast.TRUE)
    def visit(self, node, asm, context):
        asm.LOAD_CONST(True)

    @_(ast.Number)
    def visit(self, node, asm, context):
        asm.set_lineno(node)
        from ..lib.base import tonumber
        asm.LOAD_CONST(tonumber(None, node.n.encode()))

    @_(ast.String)
    def visit(self, node, asm, context):
        asm.set_lineno(node)
        asm.LOAD_CONST(node.s)

    def visit_fields(self, fields, asm):
        next = 1
        for field in fields:
            if isinstance(field, ast.Field):
                self.visit_exp(node.key, asm)
                self.visit_exp(node.value, asm)
                asm.ROT_TWO()
            else:
                self.visit_exp(field, asm, context=Load)
                asm.LOAD_CONST(next)
                next += 1
        asm.BUILD_MAP(len(fields))
        return next

    @_(ast.Table)
    def visit(self, node, asm, context):
        self.visit_symbol(node._luatable, asm, context=Load)
        if not node.fields or type(node.fields[-1]) not in (ast.Call, ast.ELLIPSIS):
            next = self.visit_fields(node.fields, asm)
            asm.LOAD_CONST(next)
            asm.CALL_FUNCTION(2)
            return

        l_before, l_after = Label(), Label()
        next = self.visit_fields(node.fields[:-1], asm)
        asm.LOAD_CONST(next)
        self.visit(node.fields[-1], asm)
        asm.GET_ITER()
        asm.emit(l_before)
        # iter -> next -> map
        asm.FOR_ITER(l_after)
        # item -> iter -> next -> map
        asm.ROT_THREE()
        # iter -> next -> item -> map
        asm.ROT_THREE()
        # next -> item -> iter -> map
        asm.DUP_TOP()
        # next -> next -> item -> iter -> map
        asm.LOAD_CONST(1)
        # 1 -> next -> next -> item -> iter -> map
        asm.BINARY_ADD()
        # next+1 -> next -> item -> iter -> map
        asm.ROT_FOUR()
        # next -> item -> iter -> next+1 -> map
        asm.ROT_TWO()
        # item -> next -> iter -> next+1 -> map
        asm.MAP_ADD(3)
        # iter -> next+1 -> map
        asm.JUMP_ABSOLUTE(l_before)
        asm.emit(l_after)
        # next -> map
        asm.CALL_FUNCTION(2)

    @_(type(None))
    def visit(self, node, asm, break_target):
        pass

    def __init__(self, filename):
        self.filename = filename
