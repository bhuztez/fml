from enum import Enum
from dis import opmap, opname, COMPILER_FLAG_NAMES, hasconst, hasjabs, hasjrel, HAVE_ARGUMENT, stack_effect
from types import CodeType

COMPILER_FLAGS = {f"CO_{v}":k for k, v in COMPILER_FLAG_NAMES.items()}

class Instruction:
    offset = 0

    def __init__(self, opcode, arg):
        self.opcode = opcode
        self.arg = arg

    def __repr__(self):
        return '{}({})'.format(opname[self.opcode], self.arg)

class Label:
    offset = 0
    stacksize = None

class LineNumber:
    offset = 0

    def __init__(self, n):
        self.n = n


def get_constants(insts):
    constants = []
    for inst in insts:
        if not isinstance(inst, Instruction):
            continue
        if inst.opcode not in hasconst:
            continue
        for i, c in enumerate(constants):
            if inst.arg is c:
                inst.slot = i
                break
        else:
            inst.slot = len(constants)
            constants.append(inst.arg)

    return tuple(constants)

def extended_length(n):
    count = 0
    while n > 0:
        n >>= 8
        count += 1
    return count

def get_arg(inst, offset):
    if inst.opcode in hasjabs:
        return inst.arg.offset
    elif inst.opcode in hasjrel:
        arg = inst.arg.offset - offset
        if arg < 0:
            return 0
        length = 2 * (extended_length(arg >> 8) + 1)
        arg -= length
        return 0 if arg < 0 else arg
    elif inst.opcode in hasconst:
        return inst.slot
    else:
        return inst.arg

def length_of_inst(inst, offset):
    if not isinstance(inst, Instruction):
        return 0
    arg = get_arg(inst, offset)
    return 2 * (extended_length(arg >> 8) + 1)

def validate_offset(insts):
    offset = 0
    for inst in insts:
        if inst.offset != offset:
            return False
        # assert validate_arg(inst)
        offset += length_of_inst(inst, offset)
    return True

def assign_offset(insts):
    offset = 0
    for inst in insts:
        inst.offset = offset
        offset += length_of_inst(inst, offset)

def extend_arg(insts):
    for inst in insts:
        if not isinstance(inst, Instruction):
            continue
        arg = get_arg(inst, inst.offset)
        length = length_of_inst(inst, inst.offset)//2
        if length == 0:
            continue
        for i in range(length, 1, -1):
            yield Instruction(opmap["EXTENDED_ARG"], (arg >> 8 * i) & 0xFF)
        yield Instruction(inst.opcode, (arg & 0xFF))

def resolve_offsets(insts):
    while not validate_offset(insts):
        assign_offset(insts)

def assemble_code(insts):
    return b''.join(
        bytes([inst.opcode, inst.arg if inst.opcode >= HAVE_ARGUMENT else 0])
        for inst in extend_arg(insts))

def iter_lnotab(insts, firstlineno):
    last = firstlineno
    current = last

    for inst in insts:
        if isinstance(inst, LineNumber):
            current = inst.n
        else:
            if current != last:
                yield inst.offset, current
            last = current

def iter_line_incr(line_incr):
    if line_incr > 0:
        while line_incr > 127:
            line_incr -= 127
            yield 127
        yield line_incr
    else:
        while line_incr < -128:
            line_incr += 128
            yield 128
        yield 256 + line_incr

def encode_lnotab(lnotab, firstlineno):
    lastoffset = 0
    lastlineno = firstlineno

    for offset, lineno in lnotab:
        line_incr = lineno - lastlineno
        if line_incr == 0:
            continue
        byte_incr = offset - lastoffset

        while byte_incr > 255:
            byte_incr -= 255
            yield 255
            yield 0

        it = iter_line_incr(line_incr)
        yield byte_incr
        yield next(it)
        for i in it:
            yield 0
            yield i

        lastoffset = offset
        lastlineno = lineno

def assemble_lnotab(insts, firstlineno):
    return bytes(encode_lnotab(iter_lnotab(insts, firstlineno), firstlineno))

_stack_effect = {
    "JUMP_IF_TRUE_OR_POP": (-1, 0),
    "POP_JUMP_IF_FALSE": (-1, -1),
    "POP_JUMP_IF_TRUE": (-1, -1)
}

def resolve_stacksize(insts):
    max_stacksize = 0
    pending = [(0,0)]

    while pending:
        (i, stacksize), *pending = pending
        inst = insts[i]        
        if isinstance(inst, Label):
            if inst.stacksize is None:
                inst.stacksize = stacksize
            else:
                assert stacksize == inst.stacksize
                continue
            i += 1
        else:
            assert i == 0

        while True:
            inst = insts[i]
            if isinstance(inst, Label):
                if inst.stacksize is None:
                    inst.stacksize = stacksize
                assert inst.stacksize == stacksize
            elif isinstance(inst, Instruction):
                if inst.opcode == opmap["RETURN_VALUE"]:
                    assert stacksize == 1
                    break
                if inst.opcode == opmap["JUMP_ABSOLUTE"]:
                    pending.append((insts.index(inst.arg), stacksize))
                    break

                if inst.opcode in hasconst:
                    stacksize += stack_effect(inst.opcode, inst.slot)
                elif inst.opcode < HAVE_ARGUMENT:
                    stacksize += stack_effect(inst.opcode)
                elif inst.opcode not in hasjrel and inst.opcode not in hasjabs:
                    stacksize += stack_effect(inst.opcode, inst.arg)
                else:
                    notjump, jump = _stack_effect[opname[inst.opcode]]
                    jump += stacksize
                    pending.append((insts.index(inst.arg), jump))
                    max_stacksize = max(jump, max_stacksize)
                    stacksize += notjump

            i += 1
            max_stacksize = max(stacksize, max_stacksize)

    return max_stacksize

class Assembler:

    def __init__(self):
        self.insts = []

    def build(self, argcount, names, varnames, filename, name, firstlineno, freevars, cellvars):
        flags = self.CO_VARARGS | self.CO_OPTIMIZED | self.CO_NEWLOCALS
        if not freevars and not cellvars:
            flags |= self.CO_NOFREE
        elif freevars:
            flags |= self.CO_NESTED

        constants = get_constants(self.insts)
        resolve_offsets(self.insts)

        stacksize = resolve_stacksize(self.insts)
        lnotab = assemble_lnotab(self.insts, firstlineno)
        code = assemble_code(self.insts)

        return CodeType(
            argcount,
            0,
            len(varnames) + len(cellvars),
            stacksize,
            flags,
            code,
            constants,
            names,
            varnames,
            filename,
            name,
            firstlineno,
            lnotab,
            freevars,
            cellvars)

    def emit(self, inst):
        self.insts.append(inst)

    def set_lineno(self, node):
        self.emit(LineNumber(node.lineno))

    def __getattribute__(self, name):
        if name in opmap:
            def emit(arg=0):
                self.emit(Instruction(opmap[name], arg))
            return emit
        if name in COMPILER_FLAGS:
            return COMPILER_FLAGS[name]
        return object.__getattribute__(self, name)
