from antlr4 import *
from antlr_yal import *
from pprint import pprint

def parseStmt(stmt: yalParser.StmtContext, parent) -> ParserRuleContext:
    from compiler.HIR.CodeScope import While, If
    child = stmt.children[0]
    if isinstance(child, yalParser.While_yalContext):
        return While(child, parent)
    elif isinstance(child, yalParser.If_yalContext):
        return If(child, parent)
    elif isinstance(child, yalParser.AssignContext):
        return Assign(child)
    elif isinstance(child, yalParser.CallContext):
        return Call(child.children[0], child.children[1])
    else:
        print("Oh damn boie")
        return None

class Call:
    def __init__(self, calls: str, args_node: yalParser.Arg_listContext):
        self.calls = calls.split('.')
        self.args = args_node.children

class ExprTest:
    def __init__(self, node: yalParser.ExprtestContext):
        self.op = node.children[1]
        self.left = LeftOP(node.children[0])
        self.right = RightOP(node.children[2])

class LeftOP:
    def __init__(self, node: yalParser.Left_opContext):
        child = node.children[0]
        if (isinstance(child, yalParser.Array_accessContext)):
            self.operator = ArrayAccess(child)
        elif (isinstance(child, yalParser.Scalar_accessContext)):
            self.operator = ScalarAccess(child)
        else:
            print("WUUUUUUUUUUUTTTTTT??????!!!!!!!");

class RightOP:
    def __init__(self, node: yalParser.Right_opContext):
        self.value = {}
        if isinstance(node.children[0], yalParser.Array_sizeContext):
            self.value[0] = ArraySize(node.children[0])
            self.needs_op = False
        elif node.getChildCount() is 1: #Only term
            self.value[0] = Term(node.children[0])
            self.needs_op = False
        else:
            self.value[0] = Term(node.children[0])
            self.operator = node.children[1]
            self.value[1] = Term(node.children[0])
            self.needs_op = True

class Assign:
    def __init__(self, node: yalParser.AssignContext):
        self.left = LeftOP(node.children[0])
        self.right = RightOP(node.children[1])

class ArrayAccess:
    def __init__(self, node: yalParser.Array_accessContext):
        self.var = node.children[0]
        self.index = str(node.children[1])

class ScalarAccess:
    def __init__(self, node: yalParser.Scalar_accessContext):
        self.var = node.children[0]
        self.size = (len(node.children) is 2)

class ArraySize:
    def __init__(self, node: yalParser.Array_sizeContext):
        child = node.children[0]
        if child.isdigit():
            self.value = int(child)
            self.access = False
        else: #Scalar access
            self.value = ScalarAccess(child)
            self.access = True

class Term:
    def __init__(self, node: yalParser.TermContext):
        base = 0
        if str(node.children[0]) == '+' or str(node.children[0]) == '-':
            base = 1

        self.positive = (str(node.children[0]) is not "-")
        child = node.children[base]


        if isinstance(child, yalParser.CallContext):
            self.value = Call(child.children[0], child.children[1])
        elif isinstance(child, yalParser.Array_accessContext):
            self.value = ArrayAccess(child)
        elif isinstance(child, yalParser.Scalar_accessContext):
            self.value = ScalarAccess(child)
        elif isinstance(child, tree.Tree.TerminalNodeImpl):
            self.value = int(str(child))
        else:
            print("HMMMMMMMMMMMMM?!!?!")
