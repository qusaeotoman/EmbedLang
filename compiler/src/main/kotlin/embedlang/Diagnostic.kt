package embedlang

import embedlang.ast.SourceLocation

enum class DiagnosticKind { SYNTAX, SEMANTIC }
data class Diagnostic(val code: String, val message: String, val location: SourceLocation,
    val kind: DiagnosticKind = DiagnosticKind.SEMANTIC) {
    override fun toString() = "$location: ${kind.name.lowercase()} error [$code]: $message"
}
