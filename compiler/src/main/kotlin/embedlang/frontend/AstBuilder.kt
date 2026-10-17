package embedlang.frontend

import embedlang.ast.*
import embedlang.parser.EmbedLangBaseVisitor
import embedlang.parser.EmbedLangParser
import org.antlr.v4.runtime.ParserRuleContext
import org.antlr.v4.runtime.Token

/** The only layer that knows about ANTLR parse-tree classes. */
internal class AstBuilder(private val file: String) : EmbedLangBaseVisitor<Node>() {
    private fun location(token: Token) = SourceLocation(file, token.line, token.charPositionInLine + 1)
    private fun location(ctx: ParserRuleContext) = location(ctx.start)
    private fun expression(ctx: ParserRuleContext) = visit(ctx) as Expression

    override fun visitProgram(ctx: EmbedLangParser.ProgramContext) =
        Program(ctx.functionDecl().map { visitFunctionDecl(it) }, location(ctx))

    override fun visitFunctionDecl(ctx: EmbedLangParser.FunctionDeclContext) = Function(
        ctx.IDENT().text,
        ctx.parameterList()?.parameter()?.map {
            Parameter(it.IDENT().text, Type.fromSpelling(it.type().text), location(it))
        } ?: emptyList(),
        Type.fromSpelling(ctx.type().text), visitBlock(ctx.block()), location(ctx),
    )

    override fun visitBlock(ctx: EmbedLangParser.BlockContext) =
        Block(ctx.statement().map { visit(it) as Statement }, location(ctx))

    override fun visitLetStatement(ctx: EmbedLangParser.LetStatementContext) = VariableDeclaration(
        ctx.IDENT().text, Type.fromSpelling(ctx.type().text), expression(ctx.expression()), location(ctx),
    )
    override fun visitAssignmentStatement(ctx: EmbedLangParser.AssignmentStatementContext) =
        Assignment(ctx.IDENT().text, expression(ctx.expression()), location(ctx))
    override fun visitIfStatement(ctx: EmbedLangParser.IfStatementContext) = IfStatement(
        expression(ctx.expression()), visitBlock(ctx.block(0)),
        ctx.block().getOrNull(1)?.let { visitBlock(it) }, location(ctx),
    )
    override fun visitWhileStatement(ctx: EmbedLangParser.WhileStatementContext) =
        WhileStatement(expression(ctx.expression()), visitBlock(ctx.block()), location(ctx))
    override fun visitReturnStatement(ctx: EmbedLangParser.ReturnStatementContext) =
        ReturnStatement(ctx.expression()?.let { expression(it) }, location(ctx))
    override fun visitCallStatement(ctx: EmbedLangParser.CallStatementContext) =
        CallStatement(visitCall(ctx.call()), location(ctx))
    override fun visitCall(ctx: EmbedLangParser.CallContext) = CallExpression(
        ctx.IDENT().text, ctx.argumentList()?.expression()?.map { expression(it) } ?: emptyList(), location(ctx),
    )

    override fun visitExpression(ctx: EmbedLangParser.ExpressionContext) = expression(ctx.logicalOr())
    override fun visitLogicalOr(ctx: EmbedLangParser.LogicalOrContext) = fold(ctx)
    override fun visitLogicalAnd(ctx: EmbedLangParser.LogicalAndContext) = fold(ctx)
    override fun visitEquality(ctx: EmbedLangParser.EqualityContext) = fold(ctx)
    override fun visitComparison(ctx: EmbedLangParser.ComparisonContext) = fold(ctx)
    override fun visitAdditive(ctx: EmbedLangParser.AdditiveContext) = fold(ctx)
    override fun visitMultiplicative(ctx: EmbedLangParser.MultiplicativeContext) = fold(ctx)

    private fun fold(ctx: ParserRuleContext): Expression {
        var left = expression(ctx.getChild(0) as ParserRuleContext)
        for (index in 1 until ctx.childCount step 2) {
            val symbol = ctx.getChild(index).text
            val operator = BinaryOperator.entries.first { it.symbol == symbol }
            val right = expression(ctx.getChild(index + 1) as ParserRuleContext)
            left = BinaryExpression(left, operator, right, location(ctx))
        }
        return left
    }

    override fun visitUnary(ctx: EmbedLangParser.UnaryContext): Expression =
        if (ctx.primary() != null) expression(ctx.primary())
        else UnaryExpression(UnaryOperator.entries.first { it.symbol == ctx.getChild(0).text },
            expression(ctx.unary()), location(ctx))

    override fun visitPrimary(ctx: EmbedLangParser.PrimaryContext): Expression = when {
        ctx.INTEGER() != null -> IntegerLiteral(ctx.INTEGER().text, location(ctx))
        ctx.TRUE() != null -> BooleanLiteral(true, location(ctx))
        ctx.FALSE() != null -> BooleanLiteral(false, location(ctx))
        ctx.call() != null -> visitCall(ctx.call())
        ctx.IDENT() != null -> VariableReference(ctx.IDENT().text, location(ctx))
        else -> expression(ctx.expression())
    }
}
