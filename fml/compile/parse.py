import re
from sly import Lexer, Parser
from sly.yacc import YaccSymbol, YaccProduction
from . import ast
from .error import Error

ESCAPE_RE = re.compile(r"\\[abfnrtv\\\"']|\\z\s*|\\x[0-9a-fA-F]{2}|\\\d{1,3}|\\u{[0-9a-fA-F]+}")
ESCAPE_CHARS = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}

def escape(string):
    def replace(match):
        s = match.group(0)
        c = s[1]

        if c in "\"'\\":
            return c
        elif c in "abfnrtv":
            return ESCAPE_CHARS[c]
        elif c == 'z':
            return ''
        elif c == 'x':
            return chr(int(s[2:], 16))
        elif c == 'u':
            return chr(int(s[3:-1], 16))
        else:
            o = int(s[1:])
            if o > 255:
                raise Exception("decimal escape too large near '%s'"%(s))

            return chr(o)

    return ESCAPE_RE.sub(replace, string)


class LuaLexer(Error, Lexer):
    tokens = {
        NAME,

        AND, BREAK, DO, ELSE, ELSEIF, END,
        FALSE, FOR, GOTO, FUNCTION, IF, IN,
        LOCAL, NIL, NOT, OR, REPEAT, RETURN,
        THEN, TRUE, UNTIL, WHILE,

        SHL, SHR, IDIV,
        EQ, NE, LE, GE,
        LABEL, CONCAT, ELLIPSIS,

        STRING, LONGSTRING, NUMBER,
        SHEBANG}

    literals = {
        '+', '-', '*', '/', '^', '%', '#',
        '&', '~', '|', '<', '>', '=',
        '(', ')', '{', '}', '[', ']',
        ';', ':', ',', '.'}

    SHEBANG = r'^\#[^\n]*'
    NUMBER = r'0[xX](?:[0-9A-Fa-f]+(?:\.[0-9A-Fa-f]*)?|\.[0-9A-Fa-f]+)(?:[pP][+-]?\d+)?|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'

    SHL = r'<<'
    SHR = r'>>'
    IDIV = r'//'
    EQ = r'=='
    NE = r'~='
    LE = r'<='
    GE = r'>='

    LABEL = r'::'
    ELLIPSIS = r'\.\.\.'
    CONCAT = r'\.\.'

    NAME = r'[a-zA-Z_][a-zA-Z_0-9]*'
    NAME['and'] = AND
    NAME['break'] = BREAK
    NAME['do'] = DO
    NAME['else'] = ELSE
    NAME['elseif'] = ELSEIF
    NAME['end'] = END
    NAME['false'] = FALSE
    NAME['for'] = FOR
    NAME['goto'] = GOTO
    NAME['function'] = FUNCTION
    NAME['if'] = IF
    NAME['in'] = IN
    NAME['local'] = LOCAL
    NAME['nil'] = NIL
    NAME['not'] = NOT
    NAME['or'] = OR
    NAME['repeat'] = REPEAT
    NAME['return'] = RETURN
    NAME['then'] = THEN
    NAME['true'] = TRUE
    NAME['until'] = UNTIL
    NAME['while'] = WHILE

    @_(r'"(?:[^"\n\\]|\\[abfnrtv\\"\'\n]|\\z\s*|\\x[0-9a-fA-F]{2}|\\\d{1,3}|\\u{[0-9a-fA-F]+})*"',
       r"'(?:[^'\n\\]|\\[abfnrtv\\'\"\n]|\\z\s*|\\x[0-9a-fA-F]{2}|\\\d{1,3}|\\u{[0-9a-fA-F]+})*'")
    def STRING(self, t):
        self.lineno += t.value.count('\n')
        t.value = escape(t.value[1:-1])
        return t

    @_(r'\[(?P<b>=*)\[(?:(?!\](?P=b)\]).|\n)*\](?P=b)\]')
    def LONGSTRING(self, t):
        self.lineno += t.value.count('\n')

        i = t.value.find('[', 1)+1
        t.value = t.value[i:-i]

        if t.value.startswith("\n"):
            t.value = t.value[1:]

        return t

    ignore = ' \t'

    @_(r'--\[(?P<c>=*)\[(?:(?!\](?P=c)\]).|\n)*\](?P=c)\]')
    def ignore_long_comment(self, t):
        self.lineno += t.value.count('\n')

    ignore_comment = r'--[^\n]*(?=\n|$)'

    @_(r'\n+')
    def ignore_NEWLINE(self, t):
        self.lineno += len(t.value)

    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def error(self, t):
        super().error(t, f"Bad character {t.value[0]!r}")


CONSTANTS = {
    'true': ast.TRUE,
    'false': ast.FALSE,
    'nil': ast.NIL}

class LuaParser(Error, Parser):
    tokens = LuaLexer.tokens

    precedence = (
        ('left', OR),
        ('left', AND),
        ('left', "<", ">", LE, GE, NE, EQ),
        ('left', "|"),
        ('left', "~"),
        ('left', "&"),
        ('left', "SHL", "SHR"),
        ('right', CONCAT),
        ('left', "+", "-"),
        ('left', "*", "/", IDIV, "%"),
        ('right', NOT, '#', UMINUS, UNOT),
        ('right', "^")
    )

    def _position(self, p):
        if isinstance(p, YaccSymbol):
            return self._position(p.value)
        elif isinstance(p, YaccProduction):
            return self._position(p._slice[0])
        elif isinstance(p, list):
            return self._position(p[0])
        return {"lineno": p.lineno, "index": p.index}

    def position(self, p, i=None):
        if i is None:
            return self._position(p)
        return self._position(p._slice[i])

    @_('SHEBANG block')
    def file(self, p):
        return ast.File(body=p[1], lineno=1, index=0)

    @_('block')
    def file(self, p):
        return ast.File(body=p[0], lineno=1, index=0)

    @_('stat block')
    def block(self, p):
        return [p[0]] + p[1]

    @_('retstat')
    def block(self, p):
        return [p[0]]

    @_('')
    def block(self, p):
        return []

    @_('";"')
    def stat(self, p):
        pass

    @_('varlist "=" explist')
    def stat(self, p):
        return ast.Assign(
            target=p[0],
            value=p[2],
            **self.position(p))

    @_('functioncall')
    def stat(self, p):
        return ast.CallStatement(
            body=p[0],
            **self.position(p))

    @_('label')
    def stat(self, p):
        return p[0]

    @_('BREAK')
    def stat(self, p):
        return ast.Break(**self.position(p))

    @_('GOTO name')
    def stat(self, p):
        return ast.Goto(target=p[1].id, **self.position(p))

    @_('DO block END')
    def stat(self, p):
        return ast.Block(
            body=p[1],
            **self.position(p))

    @_('WHILE exp DO block END')
    def stat(self, p):
        return ast.While(
            test=p[1],
            body=p[3],
            **self.position(p))

    @_('REPEAT block UNTIL exp')
    def stat(self, p):
        return ast.Repeat(
            body=p[1],
            test=p[3],
            **self.position(p))

    @_('IF exp THEN block ifstat')
    def stat(self, p):
        return ast.If(
            test=p[1],
            body=p[3],
            orelse=p[4],
            **self.position(p))

    @_('ELSEIF exp THEN block ifstat')
    def ifstat(self, p):
        return ast.If(
            test=p[1],
            body=p[3],
            orelse=p[4],
            **self.position(p))

    @_('ELSE block END')
    def ifstat(self, p):
        return p[1]

    @_('END')
    def ifstat(self, p):
        """ifstat : END"""
        return []

    @_('FOR name "=" exp "," exp DO block END')
    def stat(self, p):
        return ast.For(
            target = p[1],
            start = p[3],
            stop = p[5],
            step = ast.Number(n="1", **self.position(p, 6)),
            body = p[7],
            **self.position(p))

    @_('FOR name "=" exp "," exp "," exp DO block END')
    def stat(self, p):
        return ast.For(
            target=p[1],
            start=p[3],
            stop=p[5],
            step=p[7],
            body=p[9],
            **self.position(p))

    @_('FOR namelist IN explist DO block END')
    def stat(self, p):
        return ast.ForEach(
            target=p[1],
            iter=p[3],
            body=p[5], **self.position(p))

    @_('FUNCTION funcname parlist block END')
    def stat(self, p):
        args = p[2]

        if isinstance(p[1], ast.Method):
            args.value = [ast.Name(id='self', **self.position(p,2))] + args.value

        return ast.Function(
            name=p[1],
            pars=args,
            body=p[3],
            **self.position(p))


    @_('LOCAL FUNCTION name parlist block END')
    def stat(self, p):
        return ast.FunctionLocal(
            name=p[2],
            pars=p[3],
            body=p[4],
            **self.position(p))

    @_('LOCAL namelist')
    def stat(self, p):
        return ast.AssignLocal(
            target=p[1],
            value=[],
            **self.position(p))

    @_('LOCAL namelist "=" explist')
    def stat(self, p):
        return ast.AssignLocal(
            target=p[1],
            value=p[3],
            **self.position(p))

    @_('RETURN explist', 'RETURN explist ";"')
    def retstat(self, p):
        return ast.Return(
            value=p[1],
            **self.position(p))

    @_('RETURN', 'RETURN ";"')
    def retstat(self, p):
        return ast.Return(
            value=[],
            **self.position(p))

    @_('LABEL name LABEL')
    def label(self, p):
        return ast.Label(
            name = p[1].id,
            **self.position(p))

    @_('funcname ":" name')
    def funcname(self, p):
        return ast.Method(
            value = p[0],
            method = p[2],
            **self.position(p))

    @_('funcname "." name')
    def funcname(self, p):
        return ast.Attribute(
            value = p[0],
            attr = p[2],
            **self.position(p))

    @_('name')
    def funcname(self, p):
        return p[0]

    @_('varlist "," var')
    def varlist(self, p):
        return p[0] + [p[2]]

    @_('var')
    def varlist(self, p):
        return [p[0]]

    @_('name')
    def var(self, p):
        return p[0]

    @_('prefixexp "[" exp "]"')
    def var(self, p):
        return ast.Subscript(
            value=p[0],
            slice=p[2],
            **self.position(p))

    @_('prefixexp "." name')
    def var(self, p):
        return ast.Attribute(
            value=p[0],
            attr=p[2],
            **self.position(p))

    @_('namelist "," name')
    def namelist(self, p):
        return p[0] + [p[2]]

    @_('name')
    def namelist(self, p):
        return [p[0]]

    @_('explist "," exp')
    def explist(self, p):
        return p[0] + [p[2]]

    @_('exp')
    def explist(self, p):
        return [p[0]]

    @_('NIL', 'TRUE', 'FALSE')
    def exp(self, p):
        return CONSTANTS[p[0]](**self.position(p))

    @_('NUMBER')
    def exp(self, p):
        return ast.Number(n=p[0], **self.position(p))

    @_('string',
       'ellipsis',
       'functiondef',
       'prefixexp',
       'tableconstructor')
    def exp(self, p):
        return p[0]

    @_('exp OR exp',
       'exp AND exp',
       'exp "<" exp',
       'exp ">" exp',
       'exp LE exp',
       'exp GE exp',
       'exp NE exp',
       'exp EQ exp',
       'exp "|" exp',
       'exp "~" exp',
       'exp "&" exp',
       'exp SHL exp',
       'exp SHR exp',
       'exp CONCAT exp',
       'exp "+" exp',
       'exp "-" exp',
       'exp "*" exp',
       'exp "/" exp',
       'exp IDIV exp',
       'exp "%" exp',
       'exp "^" exp')
    def exp(self, p):
        return ast.BinOp(
            left = p[0],
            op = p[1],
            right = p[2],
            **self.position(p))

    @_('NOT exp',
       '"#" exp',
       '"-" exp %prec UMINUS',
       '"~" exp %prec UNOT')
    def exp(self, p):
        return ast.UnaryOp(
            op = p[0],
            operand = p[1],
            **self.position(p))

    @_('prefixcall', 'functioncall')
    def prefixexp(self, p):
        return p[0]

    @_('var')
    def prefixcall(self, p):
        return p[0]

    @_('"(" exp ")"')
    def prefixcall(self, p):
        return p[1]

    @_('prefixcall args',
       'functioncall args')
    def functioncall(self, p):
        return ast.Call(
            func=p[0],
            args=p[1],
            **self.position(p))

    @_('prefixcall ":" name args',
       'functioncall ":" name args')
    def functioncall(self, p):
        return ast.Call(
            func = ast.Method(
                value = p[0],
                method = p[2],
                **self.position(p)),
            args = p[3],
            **self.position(p))

    @_('"(" explist ")"', '"(" emptylist ")"')
    def args(self, p):
        return ast.ExpressionList(value=p[1], **self.position(p))

    @_('tableconstructor', 'string')
    def args(self, p):
        return ast.ExpressionList(value=[p[0]], **self.position(p, 0))

    @_('FUNCTION parlist block END')
    def functiondef(self, p):
        return ast.Lambda(
            pars = p[1],
            body = p[2],
            **self.position(p))

    @_('"(" namelist ")"',
       '"(" emptylist ")"')
    def parlist(self, p):
        return ast.Parameters(value=p[1], varargs=False, **self.position(p))

    @_('"(" namelist "," ellipsis ")"')
    def parlist(self, p):
        return ast.Parameters(value=p[1], varargs=True, **self.position(p))

    @_('"(" ellipsis ")"')
    def parlist(self, p):
        return ast.Parameters(value=[], varargs=True, **self.position(p))

    @_('ELLIPSIS')
    def ellipsis(self, p):
        return ast.ELLIPSIS(**self.position(p))

    @_('"{" fieldlist "}"', '"{" emptylist "}"')
    def tableconstructor(self, p):
        # assert all(
        #     isinstance(f, ast.Field) or
        #     isinstance(f, ast.Expression)
        #     for f in p[1])
        return ast.Table(fields=p[1], **self.position(p))

    @_('fieldlisthead', 'fieldlisthead fieldsep')
    def fieldlist(self, p):
        return p[0]

    @_('fieldlisthead fieldsep field')
    def fieldlisthead(self, p):
        return p[0] + [p[2]]

    @_('field')
    def fieldlisthead(self, p):
        return [p[0]]

    @_('"[" exp "]" "=" exp')
    def field(self, p):
        return ast.Field(
            key = p[1],
            value = p[4],
            **self.position(p))

    @_('name "=" exp')
    def field(self, p):
        return ast.Field(
            key = ast.String(
                s=p[0].id,
                **self.position(p)),
            value = p[2],
            **self.position(p))

    @_('exp')
    def field(self, p):
        return p[0]

    @_('","', '";"')
    def fieldsep(self, p):
        pass

    @_('NAME')
    def name(self, p):
        return ast.Name(id=p[0], **self.position(p))

    @_('')
    def emptylist(self, p):
        return []

    @_('STRING', 'LONGSTRING')
    def string(self, p):
        return ast.String(s=p[0], **self.position(p))

    def __init__(self, filename, text):
        super().__init__()
        self.filename = filename
        self.text = text

    def line_of(self, t):
        last_cr = self.text.rfind('\n', 0, t.index)
        next_cr = self.text.find('\n', t.index)
        if next_cr < 0:
            next_cr = None
        return self.text[last_cr+1: next_cr]

    def col_offset(self, t):
        last_cr = self.text.rfind('\n', 0, t.index)
        if last_cr < 0:
            last_cr = 0
        return t.index - last_cr

    def error(self, t):
        if t is None:
            raise EOFError()
        super().error(t, f"Invalid token {t.value!r}")
