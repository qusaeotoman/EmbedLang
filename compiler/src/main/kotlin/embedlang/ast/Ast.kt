package embedlang.ast

/** Lines and columns are one-based, including diagnostics from ANTLR. */
data class SourceLocation(val file: String, val line: Int, val column: Int) {
    override fun toString() = "$file:$line:$column"
}

enum class Type(val spelling: String) {
    I32("i32"), U32("u32"), U8("u8"), BOOL("bool"), VOID("void");
    val isInteger: Boolean get() = this == I32 || this == U32 || this == U8
    companion object {
        fun fromSpelling(text: String): Type = entries.first { it.spelling == text }
    }
}

sealed interface Node { val location: SourceLocation }
data class Program(val functions: List<Function>, override val location: SourceLocation) : Node
data class Function(
    val name: String, val parameters: List<Parameter>, val returnType: Type,
    val body: Block, override val location: SourceLocation,
) : Node
data class Parameter(val name: String, val type: Type, override val location: SourceLocation) : Node
data class Block(val statements: List<Statement>, override val location: SourceLocation) : Node

sealed interface Statement : Node
data class VariableDeclaration(val name: String, val type: Type, val initializer: Expression,
    override val location: SourceLocation) : Statement
data class Assignment(val name: String, val value: Expression, override val location: SourceLocation) : Statement
data class IfStatement(val condition: Expression, val thenBlock: Block, val elseBlock: Block?,
    override val location: SourceLocation) : Statement
data class WhileStatement(val condition: Expression, val body: Block,
    override val location: SourceLocation) : Statement
data class ReturnStatement(val value: Expression?, override val location: SourceLocation) : Statement
data class CallStatement(val call: CallExpression, override val location: SourceLocation) : Statement

sealed interface Expression : Node
data class IntegerLiteral(val digits: String, override val location: SourceLocation) : Expression
data class BooleanLiteral(val value: Boolean, override val location: SourceLocation) : Expression
data class VariableReference(val name: String, override val location: SourceLocation) : Expression
data class CallExpression(val name: String, val arguments: List<Expression>,
    override val location: SourceLocation) : Expression
enum class UnaryOperator(val symbol: String) { NEGATE("-"), POSITIVE("+"), NOT("!") }
enum class BinaryOperator(val symbol: String) {
    ADD("+"), SUBTRACT("-"), MULTIPLY("*"), DIVIDE("/"), MODULO("%"),
    EQUAL("=="), NOT_EQUAL("!="), LESS("<"), GREATER(">"), LESS_EQUAL("<="), GREATER_EQUAL(">="),
    AND("&&"), OR("||");
}
data class UnaryExpression(val operator: UnaryOperator, val operand: Expression,
    override val location: SourceLocation) : Expression
data class BinaryExpression(val left: Expression, val operator: BinaryOperator, val right: Expression,
    override val location: SourceLocation) : Expression
