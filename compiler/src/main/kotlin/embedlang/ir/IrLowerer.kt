package embedlang.ir

import embedlang.ast.*
import embedlang.ast.Function
import embedlang.semantic.Builtins
import embedlang.semantic.TypedAnalysisResult
import java.math.BigInteger

/** Resolves bindings and copies type facts; never repeats semantic type inference. */
object IrLowerer {
    fun lower(analysis: TypedAnalysisResult): IrProgram {
        require(analysis.isSuccess) { "Cannot lower a program with semantic errors" }
        return Lowering(analysis).lower()
    }

    private class Scope(val parent: Scope? = null) {
        val locals = mutableMapOf<String, IrLocal>()
        fun lookup(name: String): IrLocal? = locals[name] ?: parent?.lookup(name)
    }

    private class Lowering(private val analysis: TypedAnalysisResult) {
        private val functions = Builtins.functions.mapValues { (name, signature) ->
            IrFunctionSymbol(name, signature.parameterTypes, signature.returnType, isBuiltin = true)
        }.toMutableMap()
        private var nextLocalId = 0

        fun lower(): IrProgram {
            for (function in analysis.program.functions) {
                functions[function.name] = IrFunctionSymbol(function.name,
                    function.parameters.map { it.type }, function.returnType)
            }
            return IrProgram(analysis.program.functions.map { lowerFunction(it) }, analysis.program.location)
        }

        private fun newLocal(name: String, type: Type, location: SourceLocation) =
            IrLocal(nextLocalId++, name, type, location)

        private fun lowerFunction(function: Function): IrFunction {
            nextLocalId = 0
            val scope = Scope()
            val parameters = function.parameters.map {
                newLocal(it.name, it.type, it.location).also { local -> scope.locals[it.name] = local }
            }
            return IrFunction(functions.getValue(function.name), parameters,
                lowerBlock(function.body, scope, nested = false), function.location)
        }

        private fun lowerBlock(block: Block, parent: Scope, nested: Boolean = true): IrBlock {
            val scope = if (nested) Scope(parent) else parent
            val statements = block.statements.map { statement ->
                when (statement) {
                    is VariableDeclaration -> {
                        // Lower before introducing the new binding, preserving shadowing rules.
                        val initializer = lowerExpression(statement.initializer, scope)
                        val local = newLocal(statement.name, statement.type, statement.location)
                        scope.locals[statement.name] = local
                        IrLocalDeclaration(local, initializer, statement.location)
                    }
                    is Assignment -> IrAssignment(checkNotNull(scope.lookup(statement.name)),
                        lowerExpression(statement.value, scope), statement.location)
                    is CallStatement -> IrCallStatement(lowerCall(statement.call, scope), statement.location)
                    is ReturnStatement -> IrReturn(statement.value?.let { lowerExpression(it, scope) }, statement.location)
                    is IfStatement -> IrIf(lowerExpression(statement.condition, scope),
                        lowerBlock(statement.thenBlock, scope), statement.elseBlock?.let { lowerBlock(it, scope) },
                        statement.location)
                    is WhileStatement -> IrWhile(lowerExpression(statement.condition, scope),
                        lowerBlock(statement.body, scope), statement.location)
                }
            }
            return IrBlock(statements, block.location)
        }

        private fun lowerExpression(expression: Expression, scope: Scope): IrExpression {
            val type = analysis.typeOf(expression)
            val literal = signedLiteral(expression)
            if (literal != null) return IrIntegerConstant(literal.longValueExact(), type, expression.location)
            return when (expression) {
                is IntegerLiteral -> error("Integer literal was not normalized at ${expression.location}")
                is BooleanLiteral -> IrBooleanConstant(expression.value, expression.location)
                is VariableReference -> scope.lookup(expression.name)?.let { IrLocalRead(it, expression.location) }
                    ?: IrBuiltinConstant(expression.name, Builtins.constants.getValue(expression.name), expression.location)
                is CallExpression -> lowerCall(expression, scope)
                is UnaryExpression -> IrUnary(IrUnaryOperator.valueOf(expression.operator.name),
                    lowerExpression(expression.operand, scope), type, expression.location)
                is BinaryExpression -> IrBinary(lowerExpression(expression.left, scope),
                    IrBinaryOperator.valueOf(expression.operator.name), lowerExpression(expression.right, scope),
                    type, expression.location)
            }
        }

        private fun lowerCall(call: CallExpression, scope: Scope) = IrCall(functions.getValue(call.name),
            call.arguments.map { lowerExpression(it, scope) }, call.location)

        // Normalize exactly the signed literal chains recognized by semantic analysis.
        // Arithmetic expressions are retained; this is not a constant-folding pass.
        private fun signedLiteral(expression: Expression): BigInteger? = when (expression) {
            is IntegerLiteral -> expression.digits.toBigInteger()
            is UnaryExpression -> when (expression.operator) {
                UnaryOperator.NEGATE -> signedLiteral(expression.operand)?.negate()
                UnaryOperator.POSITIVE -> signedLiteral(expression.operand)
                UnaryOperator.NOT -> null
            }
            else -> null
        }
    }
}
