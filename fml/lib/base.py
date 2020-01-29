from ..compile import compile
from types import FunctionType
from ctypes.util import find_library
from ctypes import CDLL, CFUNCTYPE, c_int, c_longlong, c_double, c_char_p, c_void_p, POINTER, byref, cast, get_errno

libc = CDLL(find_library("c"))

_strtod = libc.strtod
_strtod.restype = c_double
_strtod.argtypes = [c_char_p, POINTER(c_void_p)]

_strtoll = libc.strtoll
_strtoll.restype = c_longlong
_strtoll.argtypes = [c_char_p, POINTER(c_void_p), c_int]

def strtod(bytes):
    ptr = c_void_p()
    d = _strtod(bytes, byref(ptr))
    if ptr.value is None:
        return
    remain = bytes[ptr.value - cast(c_char_p(bytes), c_void_p).value:]
    if not remain.strip():
        return d

def strtoll(bytes, base=0):
    ptr = c_void_p()
    ll = _strtoll(bytes, byref(ptr), base)
    if ptr.value is None:
        return
    remain = bytes[ptr.value - cast(c_char_p(bytes), c_void_p).value:]
    if not remain.strip():
        return ll


class LuaTable:
    pass

def lt_event(a, b):
    if type(a) in (float, int) and type(b) in (float, int):
        return a < b

def le_event(a, b):
    if type(a) in (float, int) and type(b) in (float, int):
        return a <= b

def eq_event(a, b):
    pass

def gt_event(a, b):
    return lt_event(b, a)

def ge_event(a, b):
    return le_event(b, a)

def ne_event(a, b):
    return not eq_event(a, b)

def add_event(a, b):
    if type(a) is int and type(b) is int:
        return a + b

def mul_event(a, b):
    if type(a) is int and type(b) is int:
        return a * b

def forloop(sl, var):
    step, limit = sl
    var += step
    if (step >= 0 and var > limit) or (step < 0 and var < limit):
        return (None,)
    else:
        return (var,)

def forprep(var, limit, step=1):
    if type(var) is int and type(limit) is int and type(step) is int:
        return forloop, (step, limit), var - step


BUILTINS = {
    'LuaTable': LuaTable,
    'forprep': forprep,

    '.b+': add_event,
    '.b*': mul_event,

    '.b<':   lt_event,
    '.b<=':  le_event,
    '.b>':   gt_event,
    '.b>=':  ge_event,
    '.b==':  eq_event,
    '.b~=':  ne_event,
}

def tonumber(_ENV, e, base=None):
    if isinstance(e, int) or isinstance(e, float):
        return e
    elif isinstance(e, bytes):
        ll = strtoll(e, base or 0)
        if ll is not None:
            return ll
        if base is None:
            return strtod(e)

def load(_ENV, chunk, filename=None, mode=b't', env=None):
    if env is None:
        env = _ENV
    if filename is None:
        filename = b'<string>'
    if mode == b't':
        code = compile(chunk.decode(), filename.decode())
    return FunctionType(code, {"__builtins__": BUILTINS, "_ENV": env})

def loadfile(_ENV, filename=None, mode=b't', env=None):
    with open(filename, 'rb') as f:
        source = f.read()
    return load(_ENV, source, filename, mode, env)


def wraps(func, env):
    def wrapper(*args):
        return func(env, *args)
    return wrapper


def luaopen(env):
    env[b"_G"] = env
    env[b"load"] = wraps(load, env)
    env[b"loadfile"] = wraps(loadfile, env)
    env[b"tonumber"] = wraps(tonumber, env)
    return env
