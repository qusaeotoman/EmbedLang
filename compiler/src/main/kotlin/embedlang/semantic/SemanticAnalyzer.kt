package embedlang.semantic

import embedlang.Diagnostic
import embedlang.ast.*
import embedlang.ast.Function
import java.math.BigInteger
import java.util.IdentityHashMap

/** One analysis owns its symbol tables; no state survives between compilations. */
class SemanticAnalyzer {
    fun analyze(program: Program): List<Diagnostic> = analyzeTyped(program).diagnostics

    fun analyzeTyped(program: Program): TypedAnalysisResult {
        val analysis = Analysis(program)
        val diagnostics = analysis.run()
        return TypedAnalysisResult(program, diagnostics, analysis.expressionTypes)
    }

    private class Scope(val parent: Scope? = null) {
        val variables = mutableMapOf<String, Type>()
        fun lookup(name: String): Type? = variables[name] ?: parent?.lookup(name)
    }

    private class Analysis(private val program: Program) {
        val expressionTypes = IdentityHashMap<Expression, Type>()
        private val diagnostics = mutableListOf<Diagnostic>()
        private val functions = Builtins.functions.toMutableMap()

        private fun error(code: String, message: String, node: Node) {
            diagnostics += Diagnostic(code, message, node.location)
        }

        fun run(): List<Diagnostic> {
            // Register every signature first, allowing recursion and forward calls.
            for (function in program.functions) {
                if (function.name in functions || function.name in Builtins.constants) {
                    error("DUPLICATE_FUNCTION", "Function '${function.name}' is already defined or reserved", function)
                } else {
                    functions[function.name] = FunctionSignature(function.parameters.map { it.type }, function.returnType)
                }
            }
            val main = program.functions.firstOrNull { it.name == "main" }
            if (main == null) error("MISSING_MAIN", "Program requires fn main() -> void", program)
            else if (main.parameters.isNotEmpty() || main.returnType != Type.VOID) {
                error("INVALID_MAIN", "Entry point must have signature fn main() -> void", main)
            }
            for (function in program.functions) analyzeFunction(function)
            return diagnostics.toList()
        }

        private fun analyzeFunction(function: Function) {
            val scope = Scope()
            scope.variables.putAll(Builtins.constants)
            val locals = Scope(scope)
            for (parameter in function.parameters) {
                if (parameter.type == Type.VOID) error("INVALID_TYPE", "Parameters cannot have type void", parameter)
                declare(parameter.name, parameter.type, parameter, locals)
            }
            val terminates = block(function.body, locals, function.returnType, nested = false)
            if (function.returnType != Type.VOID && !terminates) {
                error("MISSING_RETURN", "Function '${function.name}' can finish without returning ${function.returnType.spelling}", function)
            }
        }

        private fun declare(name: String, type: Type, node: Node, scope: Scope) {
            if (name in scope.variables || name in Builtins.constants || name in functions) {
                error("DUPLICATE_VARIABLE", "Name '$name' is already declared in this scope or reserved", node)
            } else scope.variables[name] = type
        }

        /** True means there is no path reaching the end (return or a literal true loop). */
        private fun block(block: Block, parent: Scope, returnType: Type, nested: Boolean = true): Boolean {
            val scope = if (nested) Scope(parent) else parent
            var terminates = false
            for (statement in block.statements) {
                val statementTerminates = when (statement) {
                    is VariableDeclaration -> {
                        if (statement.type == Type.VOID) error("INVALID_TYPE", "Variables cannot have type void", statement)
                        requireType(statement.initializer, statement.type, scope)
                        // Initializers cannot refer to the variable being declared.
                        declare(statement.name, statement.type, statement, scope)
                        false
                    }
                    is Assignment -> {
                        val type = scope.lookup(statement.name)
                        if (statement.name in Builtins.constants) error("ASSIGN_CONSTANT", "Cannot assign to constant '${statement.name}'", statement)
                        if (type == null) {
                            error("UNDEFINED_VARIABLE", "Undefined variable '${statement.name}'", statement)
                            expressionType(statement.value, scope)
                        } else requireType(statement.value, type, scope)
                        false
                    }
                    is CallStatement -> { expressionType(statement.call, scope); false }
                    is ReturnStatement -> {
                        if (statement.value == null) {
                            if (returnType != Type.VOID) error("MISSING_RETURN_VALUE", "Return requires a ${returnType.spelling} value", statement)
                        } else if (returnType == Type.VOID) {
                            error("UNEXPECTED_RETURN_VALUE", "A void function cannot return a value", statement)
                            expressionType(statement.value, scope)
                        } else requireType(statement.value, returnType, scope)
                        true
                    }
                    is IfStatement -> {
                        requireType(statement.condition, Type.BOOL, scope)
                        val thenTerminates = block(statement.thenBlock, scope, returnType)
                        val elseTerminates = statement.elseBlock?.let { block(it, scope, returnType) } ?: false
                        thenTerminates && elseTerminates
                    }
                    is WhileStatement -> {
                        requireType(statement.condition, Type.BOOL, scope)
                        block(statement.body, scope, returnType)
                        statement.condition is BooleanLiteral && statement.condition.value
                    }
                }
                // Keep checking unreachable code so invalid names/types are never hidden.
                terminates = terminates || statementTerminates
            }
            return terminates
        }

        private fun requireType(expression: Expression, expected: Type, scope: Scope) {
            val actual = expressionType(expression, scope, expected)
            if (actual != null && actual != expected) {
                error("TYPE_MISMATCH", "Expected ${expected.spelling}, found ${actual.spelling}", expression)
            }
        }

        private fun expressionType(expression: Expression, scope: Scope, expected: Type? = null): Type? {
            val type = inferExpressionType(expression, scope, expected)
            if (type != null) expressionTypes[expression] = type
            return type
        }

        private fun inferExpressionType(expression: Expression, scope: Scope, expected: Type?): Type? {
            // Signed literal handling includes i32's asymmetric minimum (-2147483648).
            val literal = literalValue(expression)
            if (literal != null) return checkLiteral(literal, expression, expected)
            return when (expression) {
                is IntegerLiteral -> error("INTERNAL_LITERAL", "Invalid integer literal", expression).let { null }
                is BooleanLiteral -> Type.BOOL
                is VariableReference -> scope.lookup(expression.name).also {
                    if (it == null) error("UNDEFINED_VARIABLE", "Undefined variable '${expression.name}'", expression)
                }
                is CallExpression -> {
                    val signature = functions[expression.name]
                    if (signature == null) {
                        error("UNDEFINED_FUNCTION", "Undefined function '${expression.name}'", expression)
                        expression.arguments.forEach { expressionType(it, scope) }
                        null
                    } else {
                        if (expression.arguments.size != signature.parameterTypes.size) {
                            error("ARGUMENT_COUNT", "Function '${expression.name}' expects ${signature.parameterTypes.size} arguments, found ${expression.arguments.size}", expression)
                        }
                        expression.arguments.forEachIndexed { index, argument ->
                            val parameterType = signature.parameterTypes.getOrNull(index)
                            if (parameterType == null) expressionType(argument, scope)
                            else requireType(argument, parameterType, scope)
                        }
                        signature.returnType
                    }
                }
                is UnaryExpression -> {
                    if (expression.operator == UnaryOperator.NOT) {
                        requireType(expression.operand, Type.BOOL, scope)
                        Type.BOOL
                    } else {
                        val type = expressionType(expression.operand, scope, expected?.takeIf { it.isInteger })
                        if (type != null && !type.isInteger) error("INVALID_OPERAND", "Unary '${expression.operator.symbol}' requires an integer", expression)
                        if (expression.operator == UnaryOperator.NEGATE && type != null && type != Type.I32 && type.isInteger) {
                            error("INVALID_OPERAND", "Cannot negate an unsigned value", expression)
                        }
                        type
                    }
                }
                is BinaryExpression -> binaryType(expression, scope, expected)
            }
        }

        private fun binaryType(expression: BinaryExpression, scope: Scope, expected: Type?): Type? {
            val operator = expression.operator
            if (operator == BinaryOperator.AND || operator == BinaryOperator.OR) {
                requireType(expression.left, Type.BOOL, scope)
                requireType(expression.right, Type.BOOL, scope)
                return Type.BOOL
            }
            val equality = operator == BinaryOperator.EQUAL || operator == BinaryOperator.NOT_EQUAL
            val comparison = equality || operator in setOf(BinaryOperator.LESS, BinaryOperator.GREATER,
                BinaryOperator.LESS_EQUAL, BinaryOperator.GREATER_EQUAL)
            // A typed leaf determines the integer type before contextual/default literal typing.
            val hint = concreteType(expression.left, scope) ?: concreteType(expression.right, scope)
                ?: if (comparison) null else expected?.takeIf { it.isInteger }
            val left = expressionType(expression.left, scope, hint)
            val right = expressionType(expression.right, scope, hint ?: left)
            if (left != null && right != null && left != right) {
                error("TYPE_MISMATCH", "Operator '${operator.symbol}' requires matching types, found ${left.spelling} and ${right.spelling}", expression)
            }
            for (type in listOfNotNull(left, right).distinct()) {
                if (!type.isInteger && !(equality && type == Type.BOOL)) {
                    error("INVALID_OPERAND", "Operator '${operator.symbol}' ${if (equality) "requires integers or bool" else "requires integers"}", expression)
                }
            }
            return if (comparison) Type.BOOL else left ?: right
        }

        /** Peek at declared types without issuing diagnostics or prematurely typing literals. */
        private fun concreteType(expression: Expression, scope: Scope): Type? = when (expression) {
            is IntegerLiteral -> null
            is BooleanLiteral -> Type.BOOL
            is VariableReference -> scope.lookup(expression.name)
            is CallExpression -> functions[expression.name]?.returnType
            is UnaryExpression -> if (expression.operator == UnaryOperator.NOT) Type.BOOL else concreteType(expression.operand, scope)
            is BinaryExpression -> when (expression.operator) {
                BinaryOperator.ADD, BinaryOperator.SUBTRACT, BinaryOperator.MULTIPLY,
                BinaryOperator.DIVIDE, BinaryOperator.MODULO -> concreteType(expression.left, scope) ?: concreteType(expression.right, scope)
                else -> Type.BOOL
            }
        }

        private fun literalValue(expression: Expression): BigInteger? = when (expression) {
            is IntegerLiteral -> expression.digits.toBigInteger()
            is UnaryExpression -> when (expression.operator) {
                UnaryOperator.NEGATE -> literalValue(expression.operand)?.negate()
                UnaryOperator.POSITIVE -> literalValue(expression.operand)
                UnaryOperator.NOT -> null
            }
            else -> null
        }

        private fun checkLiteral(value: BigInteger, node: Expression, expected: Type?): Type {
            val type = expected?.takeIf { it.isInteger } ?: Type.I32
            val (min, max) = when (type) {
                Type.I32 -> BigInteger.valueOf(Int.MIN_VALUE.toLong()) to BigInteger.valueOf(Int.MAX_VALUE.toLong())
                Type.U32 -> BigInteger.ZERO to BigInteger("4294967295")
                Type.U8 -> BigInteger.ZERO to BigInteger("255")
                else -> error("Noninteger literal type")
            }
            if (value < min || value > max) error("INTEGER_OUT_OF_RANGE", "Integer $value is outside the ${type.spelling} range ($min..$max)", node)
            return type
        }
    }
}
