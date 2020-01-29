class Symbol:
    pass

class Attribute(Symbol):

    def __init__(self, name):
        self.name = name

class Global(Symbol):

    def __init__(self, name):
        self.name = name

class Free(Symbol):

    def __init__(self, parent):
        self.parent = parent
        self.name = self.parent.name

class Local(Symbol):
    is_referenced = False

    def __init__(self, name):
        self.name = name


class BaseSymbolTable:

    def __init__(self, parent):
        self.parent = parent
        self._nlocals = 0 if parent is None else len(parent.locals)
        self.table = {}
        self._loopvars = []
        self.labels = {}
        self.locals = []

    def find_label(self, name, nlocals):
        label = self.labels.get(name, None)
        if label is not None:
            if label._nlocals > nlocals:
                return None, self.locals[nlocals]
        return label, None

    def find(self, name):
        symbol = self.table.get(name, None)
        if symbol is None:
            if self.parent is not None:
                symbol = self.parent.find(name)
                if symbol is None:
                    symbol = Global(name)
                self.table[name] = self.reference(symbol)
        return symbol

    def reference(self, symbol):
        return symbol

    def declare_local(self, name):
        self.locals.append(name)
        symbol = self.add(Local(name))
        self.table[name] = symbol
        return symbol

    def get_loopvar(self, n=0):
        if n >= len(self._loopvars):
            loopvar = (
                self.add(Local(f".{n:d}f")),
                self.add(Local(f".{n:d}s")),
                self.add(Local(f".{n:d}v")))
            self._loopvars.append(loopvar)
        return self._loopvars[n]


class SymbolTable(BaseSymbolTable):
    def __init__(self, parent):
        super().__init__(parent)
        self.symbols = []

    def add(self, symbol):
        self.symbols.append(symbol)
        return symbol

    def reference(self, symbol):
        if isinstance(symbol, Global):
            symbol = Global(symbol.name)
        else:
            if isinstance(symbol, Local):
                symbol.is_referenced = True
            symbol = Free(symbol)

        return self.add(symbol)

    def get_slots(self):
        names = []
        varnames = []
        freenames = []
        cellnames = []
        freevars = []

        for symbol in self.symbols:
            if isinstance(symbol, Global) or isinstance(symbol, Attribute):
                if symbol.name not in names:
                    names.append(symbol.name)
                symbol.slot = names.index(symbol.name)
            elif isinstance(symbol, Local):
                if symbol.is_referenced:
                    symbol.slot = len(cellnames)
                    cellnames.append(symbol.name)
                else:
                    symbol.slot = len(varnames)
                    varnames.append(symbol.name)

        for symbol in self.symbols:
            if not isinstance(symbol, Free):
                continue
            if symbol.name not in freenames:
                freenames.append(symbol.name)
                freevars.append(symbol)
            symbol.slot = len(cellnames) + freenames.index(symbol.name)

        return tuple(names), tuple(varnames), tuple(freenames), tuple(cellnames), tuple(freevars)


class BlockSymbolTable(BaseSymbolTable):

    def add(self, symbol):
        return self.parent.add(symbol)

    def get_loopvar(self, n=0):
        return self.parent.get_loopvar(n)


class ForLoopBlockSymbolTable(BlockSymbolTable):

    def get_loopvar(self, n=0):
        return self.parent.get_loopvar(n+1)
