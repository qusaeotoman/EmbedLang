package embedlang.semantic

import embedlang.Diagnostic
import embedlang.ast.Expression
import embedlang.ast.Program
import embedlang.ast.Type
import java.util.Collections
import java.util.IdentityHashMap

/** Type facts belong to this exact AST, not to structurally equal expressions. */
class TypedAnalysisResult internal constructor(
    val program: Program,
    val diagnostics: List<Diagnostic>,
    expressionTypes: Map<Expression, Type>,
) {
    private val types = Collections.unmodifiableMap(IdentityHashMap(expressionTypes))
    val isSuccess: Boolean get() = diagnostics.isEmpty()

    /** Signed literal chains are recorded as a whole, just as they are checked. */
    fun typeOf(expression: Expression): Type = checkNotNull(types[expression]) {
        "No analyzed type for expression at ${expression.location}"
    }
}
