import unittest
from ..runtime import LuaState


class TestLang(unittest.TestCase):

    def setUp(self):
        self.state = LuaState()
        self.state.loadlibs()

    def test_mod(self):
        mod = self.state.load(b"")
        self.assertEqual(mod(), (True,))

    def test_function(self):
        mod = self.state.load(b"return (function () return 1 end)()")
        self.assertEqual(mod(), (1,))

    def test_return(self):
        mod = self.state.load(b"return 1")
        self.assertEqual(mod(), (1,))
        mod = self.state.load(b"return ...")
        self.assertEqual(mod(1, 2, 3), (1, 2, 3))

    def test_assign(self):
        mod = self.state.load(b"a, b = ...; return b, a")
        self.assertEqual(mod(1, 2), (2, 1))
        self.assertEqual(mod(1), (None, 1))
        self.assertEqual(mod(1, 2, 3), (2, 1))

    def test_if(self):
        mod = self.state.load(b'local a = 1; if a > 0 then return 1 end')
        self.assertEqual(mod(), (1,))
        mod = self.state.load(b'local a = 1; if a > 1 then return 1 else return 2 end')
        self.assertEqual(mod(), (2,))
        mod = self.state.load(b'local a = 1; if a > 1 then return 1 elseif a > 0 then return 2 else return 3 end')
        self.assertEqual(mod(), (2,))

    def test_while(self):
        mod = self.state.load(b'local i = 0; while i < 10 do i = i + 1 end; return i')
        self.assertEqual(mod(), (10,))
        mod = self.state.load(b'local i = 1; while i < 10 do i = i * 2 end; return i')
        self.assertEqual(mod(), (16,))

    def test_repeat(self):
        mod = self.state.load(b'local i = 0; repeat i = i + 1 until i > 10; return i')
        self.assertEqual(mod(), (11,))
        mod = self.state.load(b'local i = 1; repeat i = i * 2 until i > 10; return i')
        self.assertEqual(mod(), (16,))

    def test_for(self):
        mod = self.state.load(b'local a = 0; for i = 0, 10 do a = a + i end; return a')
        self.assertEqual(mod(), (55,))

    def test_foreach(self):
        mod = self.state.load(b'local a = 0; for i in function(s, v) if v < s then return v + 1 end end, 10, 0 do a = a + i end; return a')
        self.assertEqual(mod(), (55,))
