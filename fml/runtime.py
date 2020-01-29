class LuaState:

    def __init__(self):
        self.loaded = {}
        self._ENV = {}

    def require(self, name, func):
        if name not in self.loaded:
            mod = func(self._ENV)
            self.loaded[name] = mod

    def loadlibs(self):
        from .lib import base
        self.require(b"_G", base.luaopen)

    def load(self, *args):
        return self._ENV[b"load"](*args)

    def loadfile(self, *args):
        return self._ENV[b"loadfile"](*args)
