from dataclasses import dataclass
from typing import NamedTuple, List, Union

class MatchDescriptor(dict):

    def __get__(self, instance, owner):
        def wrapper(node, *args, **kwargs):
            return self[type(node)](instance, node, *args, **kwargs)
        return wrapper


class VisitorMetaDict(dict):
    def __setitem__(self, name, value):
        if isinstance(value, MatchDescriptor):
            value.update(self.get(name, {})) 
        super().__setitem__(name, value)

class VisitorMeta(type):

    @classmethod
    def __prepare__(self, name, bases):
        d = VisitorMetaDict()
        def _(*types):
            def decorator(func):
                return MatchDescriptor({t:func for t in types})
            return decorator
        d['_'] = _
        return d

    def __new__(self, name, bases, attrs):
        attrs.pop("_")
        return type.__new__(self, name, bases, attrs)

class Visitor(metaclass=VisitorMeta):
    pass


@dataclass
class Node:
    lineno: int
    index: int

@dataclass
class Statement(Node):
    pass

@dataclass
class Expression(Node):
    pass

@dataclass
class ExpressionList(Node):
    value: List[Expression]

@dataclass
class Var(Expression):
    pass

@dataclass
class FuncName(Var):
    pass

@dataclass
class BinOp(Node):
    pass

@dataclass
class UnaryOp(Node):
    pass

@dataclass
class Name(Var):
    id: str

@dataclass
class Parameters(Node):
    value: List[Name]
    varargs: bool

@dataclass
class File(Node):
    body: List[Statement]

@dataclass
class Assign(Statement):
    value: List[Expression]
    target: List[Var]

@dataclass
class Call(Expression):
    func: Expression
    args: ExpressionList

@dataclass
class CallStatement(Statement):
    body: Call

@dataclass
class Label(Statement):
    name: str

@dataclass
class Goto(Statement):
    target: str

@dataclass
class Block(Statement):
    body: List[Statement]

@dataclass
class While(Statement):
    test: Expression
    body: List[Statement]

@dataclass
class Repeat(Statement):
    body: List[Statement]
    test: Expression

@dataclass
class If(Statement):
    test: Expression
    body: List[Statement]
    orelse: List[Statement]

@dataclass
class For(Statement):
    start: Expression
    stop: Expression
    step: Expression
    target: Name
    body: Statement

@dataclass
class ForEach(Statement):
    iter: List[Expression]
    target: List[Name]
    body: List[Statement]

@dataclass
class Function(Statement):
    name: FuncName
    pars: Parameters
    body: List[Statement]

@dataclass
class FunctionLocal(Statement):
    name: FuncName
    pars: Parameters
    body: List[Statement]

@dataclass
class AssignLocal(Statement):
    value: List[Expression]
    target: List[Name]

@dataclass
class Return(Statement):
    value: List[Expression]

@dataclass
class Break(Statement):
    pass

@dataclass
class Subscript(Var):
    value: Expression
    slice: Expression

@dataclass
class Attribute(FuncName):
    value: Expression
    attr: Name

@dataclass
class Method(FuncName):
    value: Expression
    method: Name

@dataclass
class NIL(Expression):
    pass

@dataclass
class FALSE(Expression):
    pass

@dataclass
class TRUE(Expression):
    pass

@dataclass
class Number(Expression):
    n: str

@dataclass
class String(Expression):
    s: str

@dataclass
class ELLIPSIS(Expression):
    pass

@dataclass
class Field(Node):
    key: Expression
    value: Expression

@dataclass
class Table(Expression):
    fields: List[Union[Field, Expression]]

@dataclass
class Lambda(Expression):
    pars: Parameters
    body: List[Statement]

@dataclass
class BinOp(Expression):
    op: str
    left: Expression
    right: Expression

@dataclass
class UnaryOp(Expression):
    op: str
    operand: Expression
