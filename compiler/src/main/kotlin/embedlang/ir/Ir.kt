package embedlang.ir

import embedlang.ast.SourceLocation
import embedlang.ast.Type

/** Target-independent, structured IR. All value expressions have resolved types. */
sealed interface IrNode { val location: SourceLocation }
data class IrProgram(val functions: List<IrFunction>, override val location: SourceLocation) : IrNode
data class IrFunctionSymbol(
    val name: String, val parameterTypes: List<Type>, val returnType: Type, val isBuiltin: Boolean = false,
)
data class IrFunction(
    val symbol: IrFunctionSymbol, val parameters: List<IrLocal>, val body: IrBlock,
    override val location: SourceLocation,
) : IrNode

/** IDs are unique within a function, including parameters and shadowed locals. */
data class IrLocal(val id: Int, val name: String, val type: Type,
    override val location: SourceLocation) : IrNode
data class IrBlock(val statements: List<IrStatement>, override val location: SourceLocation) : IrNode

sealed interface IrStatement : IrNode
data class IrLocalDeclaration(val local: IrLocal, val initializer: IrExpression,
    override val location: SourceLocation) : IrStatement
data class IrAssignment(val local: IrLocal, val value: IrExpression,
    override val location: SourceLocation) : IrStatement
data class IrCallStatement(val call: IrCall, override val location: SourceLocation) : IrStatement
data class IrReturn(val value: IrExpression?, override val location: SourceLocation) : IrStatement
data class IrIf(val condition: IrExpression, val thenBlock: IrBlock, val elseBlock: IrBlock?,
    override val location: SourceLocation) : IrStatement
data class IrWhile(val condition: IrExpression, val body: IrBlock,
    override val location: SourceLocation) : IrStatement

sealed interface IrExpression : IrNode { val type: Type }
// Long represents every supported integer literal exactly, including u32's maximum.
data class IrIntegerConstant(val value: Long, override val type: Type,
    override val location: SourceLocation) : IrExpression
data class IrBooleanConstant(val value: Boolean, override val location: SourceLocation) : IrExpression {
    override val type = Type.BOOL
}
/** Board pin and mode values remain unresolved; no hardware values are invented. */
data class IrBuiltinConstant(val name: String, override val type: Type,
    override val location: SourceLocation) : IrExpression
data class IrLocalRead(val local: IrLocal, override val location: SourceLocation) : IrExpression {
    override val type: Type get() = local.type
}
data class IrCall(val function: IrFunctionSymbol, val arguments: List<IrExpression>,
    override val location: SourceLocation) : IrExpression {
    override val type: Type get() = function.returnType
}
enum class IrUnaryOperator(val mnemonic: String) { NEGATE("neg"), POSITIVE("pos"), NOT("not") }
enum class IrBinaryOperator(val mnemonic: String) {
    ADD("add"), SUBTRACT("sub"), MULTIPLY("mul"), DIVIDE("div"), MODULO("mod"),
    EQUAL("eq"), NOT_EQUAL("ne"), LESS("lt"), GREATER("gt"), LESS_EQUAL("le"), GREATER_EQUAL("ge"),
    AND("and"), OR("or");
}
data class IrUnary(val operator: IrUnaryOperator, val operand: IrExpression, override val type: Type,
    override val location: SourceLocation) : IrExpression
data class IrBinary(val left: IrExpression, val operator: IrBinaryOperator, val right: IrExpression,
    override val type: Type, override val location: SourceLocation) : IrExpression
