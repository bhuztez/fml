from .parse import LuaLexer, LuaParser
from .scope import ScopeVisitor, GotoVisitor
from .codegen import CodegenVisitor

def compile(text, filename):
    try:
        lexer = LuaLexer(filename)
        parser = LuaParser(filename, text)
        scope = ScopeVisitor(filename, text)
        goto = GotoVisitor(filename, text)
        codegen = CodegenVisitor(filename)
        node = parser.parse(lexer.tokenize(text))
        scope.visit(node, None)
        goto.visit(node)
        return codegen.visit(node)
    except SyntaxError as e:
        raise e.with_traceback(None)
