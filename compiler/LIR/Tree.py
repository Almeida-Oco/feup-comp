from ..HIR import CodeScope, Stmt
from ..HIR.Variable import NumberVariable, ArrayVariable
from . import Instruction

STRING = 'Ljava/lang/String'
INT = 'I'
VOID = 'V'
NL = '\n'

ret_to_str = {
'ARR': '[I',
'NUM': 'I',
'???': 'V'
}

def matchIOCall(func_name, args_list) -> list:
    io_functions = {
    'read': [[], INT],
    'print': [[[STRING, INT], VOID], [[STRING], VOID], [[INT], VOID]],
    'println': [[[STRING, INT], VOID], [[STRING], VOID], [[INT], VOID], [[], VOID]]
    }

    func_infos = io_functions[func_name]
    for func_info in func_infos:
        args = func_info[0]
        arg_number = len(args_list)
        if arg_number is len(args):
            if arg_number is 0:
                return func_info

            for i in range(arg_number):
                if isinstance(args_list[i], str) and args[i] == STRING:
                    return func_info
                elif isinstance(args_list[i], NumberVariable) and args[i] == INT:
                    return func_info

    return (None, None)

def getVar(var_name, node) -> str:
    current_node = node
    found = False

    while current_node is not None:
        var = current_node.varHere(var_name)
        if var is not None:
            return (var.toLIR(), var)

        current_node = current_node.parent

    raise AssertionError("Variable '" + var_name + "' not found!")


class LowLevelTree:
    def __init__(self, high_tree):
        self.functions = {}

        for (func_name, func_info) in high_tree.code.items():
            self.functions[func_name] = FunctionEntry(func_info, func_name)

    def __str__(self) -> str:
        final_str = ''
        for (func_name, func_info) in self.functions.items():
            final_str += str(func_info)
            final_str += NL + NL

        return final_str

class Entry:
    max_locals = 0
    def __init__(self):
        self.code_lines = []

    def _processStmtList(self, stmts, var_stack) -> (int, list):
        lines = []
        for stmt in stmts:
            stack_size = len(var_stack)
            if stack_size > self.max_locals:
                self.max_locals = stack_size

            if isinstance(stmt, CodeScope.If):
                lines.append(IfEntry(stmt, var_stack))
            elif isinstance(stmt, CodeScope.While):
                lines.append(WhileEntry(stmt, var_stack))
            elif isinstance(stmt, Stmt.Assign):
                lines.append(AssignEntry(stmt, var_stack))
            else: # Call
                lines.append(CallEntry(stmt, var_stack))

        return lines

    # Handles accessing the left_op value, for assignments need to overload this
    def _processLeft(self, left_node, var_stack):
        access = left_node.access
        if isinstance(access, Stmt.ArrayAccess):
            self.left = [Instruction.ArrAccess(access.var, True, var_stack, access.index)]
        else:
            self.left = [Instruction.Load(access.var, var_stack, True, access.size)]

    def _processRight(self, right_node, var_stack):
        self.right = []
        if right_node.arr_size:
            arr_size = right_node.value[0]
            self.left = Instruction.NewArr(arr_size.getVarName(), var_stack, arr_size.value.size)

        elif right_node.needs_op:
            (left_term, right_term) = (right_node.value[0], right_node.value[1])

            self.right.append(Instruction.Operator(self.__processTerm(left_term, var_stack), self.__processTerm(right_term, var_stack), right_node.operator))

        else:
            self.right.append(self.__processTerm(right_node.value[0], var_stack))

    def __processTerm(self, term_node, var_stack):
        (value, positive) = (term_node.value, term_node.positive)
        if isinstance(value, Stmt.Call):
            return CallEntry(value, var_stack)
        elif isinstance(value, Stmt.ArrayAccess):
            return Instruction.ArrAccess(value.var, positive, var_stack, value.index)
        elif isinstance(value, Stmt.ScalarAccess):
            return Instruction.Load(value.var, var_stack, positive, value.size)
        else:
            return Instruction.Load(str(value))

    def _getMaxLocals(self) -> int:
        return self.max_locals

    def _updateStack(self, var_stack, node):
        latest_var = var_stack[-1]
        if isinstance(latest_var, str):
            (type, var) = getVar(latest_var, node)
            var_stack[-1] = var

    def countStackLimit(self, code_lines) -> int:
        max_limit = 0
        curr = 0
        for line in code_lines:
            (new_curr, new_max) = line.stackCount(curr)
            curr = new_curr
            if new_max > max_limit:
                max_limit = new_max


        return max_limit
    # Returns (new_count, maximum_count_inside_instruction)
    def stackCount(self, curr) -> (int, int):
        raise NotImplementedError("Entry::stackCount() not implemented!")

class FunctionEntry(Entry):
    def __init__(self, func_node, func_name):
        super(FunctionEntry, self).__init__()
        self.func_info = func_node
        self.name = func_name

        self.stack = func_node.vars[0][:]
        self.code_lines = self._processStmtList(func_node.code, self.stack)
        self.max_locals = self._getMaxLocals()
        self.max_stack = self.countStackLimit(self.code_lines)

    def __str__(self) -> str:
        final_str = ''
        final_str += self.__functionHeader() + NL
        for line in self.code_lines:
            final_str += str(line) + NL

        final_str += self.__returnString()
        return final_str

    def _getMaxLocals(self) -> int:
        max = self.max_locals
        for line in self.code_lines:
            max_n = line._getMaxLocals()
            if max_n > max:
                max = max_n

        return max

    def __functionHeader(self) -> str:
        final_str = '.method static ' + self.name
        final_str += (self.__argsString(self.func_info.vars[0]) + NL)
        final_str += '.limit locals ' + str(self.max_locals) + NL
        final_str += '.limit stack ' + str(self.max_stack) + NL

        return final_str

    def __argsString(self, arg_list) -> str:
        if self.name == 'main':
            return '([Ljava/lang/String;)V'
        else:
            final_str = '('
            for arg in arg_list:
                final_str += ret_to_str[arg.type]

            final_str += ')' + ret_to_str[self.func_info.ret_str]
            return final_str

    def __returnString(self) -> str:
        final_str = ''
        if self.func_info.ret_var is not None:
            final_str += str(Instruction.Load(self.func_info.ret_var, self.stack))


        if self.func_info.ret_str == 'ARR':
            final_str += 'areturn' + NL
        elif self.func_info.ret_str == 'NUM':
            final_str += 'ireturn' + NL
        else:
            final_str += 'return' + NL

        return (final_str + '.end method' + NL)

class CallEntry(Entry):
    def __init__(self, call_node, var_stack):
        self.args_load = []
        self.args_type = []
        print("ARGS = " + str(call_node.args))
        for arg in call_node.args:
            if isinstance(arg, str):
                self.args_load.append(Instruction.Load(arg))
                type = 'Ljava/lang/String'
                if arg.isdigit():
                    type = 'I'
                self.args_type.append(type)
            else:
                (type, var) = getVar(arg.name, call_node.parent)
                self.args_load.append(Instruction.Load(arg.name, var_stack, True))
                self.args_type.append(type)

        self.calls = call_node.calls

        if len(self.calls) is 1:
            self.calls.insert(0, call_node.parent.modName())

            functions = CodeScope.Scope.getFunctions(call_node.parent)
            function = functions[self.calls[-1]]
            self.ret_type = ret_to_str[function.ret_str]
        elif len(self.calls) is 2 and self.calls[0] == 'io':
            (args, self.ret_type) = matchIOCall(self.calls[1], self.args_type)
        else:
            raise AssertionError("Unkonwn module '" + self.calls[0] + "'")

    def __str__(self) -> str:
        final_str = ""
        for load in self.args_load:
            final_str += str(load)

        final_str += 'invokestatic '
        for call in self.calls:
            final_str += call + '/'
        final_str = final_str[:-1]

        final_str += '('
        for type in self.args_type:
            final_str += type + ';'

        final_str = final_str[:-1]
        final_str += ')' + self.ret_type

        return final_str + NL

    # Returns (new_count, maximum_count_inside_instruction)
    def stackCount(self, curr) -> (int, int):
        return (curr, curr + len(self.args_load))

class AssignEntry(Entry):
    def __init__(self, assign_node, var_stack):
        store_name = assign_node.left.access.var
        in_array = isinstance(assign_node.left.access, Stmt.ArrayAccess)
        self.pre_code = []

        if in_array: # Need to pyt arrayref and index before value
            self.pre_code.append(Instruction.Load(store_name, var_stack, True))
            self.pre_code.append(Instruction.Load(assign_node.left.access.index, var_stack, True))

        self.left = Instruction.Store(store_name, var_stack, in_array)
        self._updateStack(var_stack, assign_node.parent)
        self._processRight(assign_node.right, var_stack)

    def __str__(self) -> str:
        final_str = ''
        for pre in self.pre_code:
            final_str += str(pre)

        for right_op in self.right:
            final_str += str(right_op)


        final_str += str(self.left)

        return final_str

    def stackCount(self, curr) -> (int, bool):
        max_limit = curr
        for code in (self.pre_code + self.right + [self.left]):
            (new_curr, new_max) = code.stackCount(curr)
            curr = new_curr
            if new_max > max_limit:
                max_limit = new_max

        return (curr, max_limit)

class ComparisonEntry(Entry):
    def __init__(self, node, stack, labels):
        super(ComparisonEntry, self).__init__()

        test = node.test
        self._processLeft(test.left, stack)
        self._processRight(test.right, stack)

    def __str__(self) -> str:
        return str(self.code)


class WhileEntry(ComparisonEntry):
    label_id = 0
    label_start = 'while_start#'
    label_end = 'while_end#'

    def __init__(self, while_node, stack):
        labels = [(self.label_end + str(self.label_id)), (self.label_start + str(self.label_id))]
        self.label_id += 1

        super(WhileEntry, self).__init__(while_node, stack, labels)
        self.stmts = self._processStmtList(while_node.code, stack)
        self.code = Instruction.WhileBranching(self.left, self.right, while_node.test.op, self.stmts, labels)

    def stackCount(self, curr) -> (int, bool):
        return self.code.stackCount(curr)

    def _getMaxLocals(self) -> int:
        max = self.max_locals
        for line in (self.left + self.right + self.stmts):
            if isinstance(line, Entry):
                max_n = line._getMaxLocals()
                if max_n > max:
                    max = max_n

        return max

class IfEntry(ComparisonEntry):
    label_id = 0
    label_start = 'else_start#'
    label_end = 'if_end#'

    def __init__(self, if_node, stack):
        labels = [(self.label_start + str(self.label_id)), (self.label_end + str(self.label_id))]
        self.label_id += 1

        super(IfEntry, self).__init__(if_node, stack, labels)

        stack_copy = stack[:]
        code = [self._processStmtList(if_node.code, stack), self._processStmtList(if_node.else_code, stack_copy)]
        self.code = Instruction.IfBranching(self.left, self.right, if_node.test.op, code, labels)

    def stackCount(self, curr) -> (int, bool):
        return self.code.stackCount(curr)

    def _getMaxLocals(self) -> int:
        max = self.max_locals
        for line in (self.left + self.right + [self.code]):
            if isinstance(line, Entry):
                max_n = line._getMaxLocals()
                if max_n > max:
                    max = max_n

        return max
