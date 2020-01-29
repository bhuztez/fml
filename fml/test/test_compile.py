import unittest
from ..compile import compile


class TestLexer(unittest.TestCase):

    def test_bad_character(self):
        with self.assertRaisesRegex(SyntaxError, 'Bad character'):
            compile('!', 'stdin')


class TestParser(unittest.TestCase):

    def test_invalid_token(self):
        with self.assertRaisesRegex(SyntaxError, 'Invalid token'):
            compile(')', 'stdin')


class TestScope(unittest.TestCase):

    def test_label_already_defined(self):
        with self.assertRaisesRegex(SyntaxError, "label 'a' already defined on line 1"):
            compile("::a::\n::a::", 'stdin')


    def test_ellipsis_outside_vararg_function(self):
        with self.assertRaisesRegex(SyntaxError, "cannot use '...' outside a vararg function"):
            compile("function a() return ... end", 'stdin')


class TestGoto(unittest.TestCase):

    def test_no_visible_label(self):
        with self.assertRaisesRegex(SyntaxError, "no visible label"):
            compile("goto a", 'stdin')

    def test_jumps_into_the_scope_of_local(self):
        with self.assertRaisesRegex(SyntaxError, "jumps into the scope of local"):
            compile("goto b; local x = 1; :: b ::", 'stdin')
