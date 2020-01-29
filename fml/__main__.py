from .runtime import LuaState
import sys

state = LuaState()
state.loadlibs()
state.loadfile(sys.argv[1])(sys.argv[2:])
