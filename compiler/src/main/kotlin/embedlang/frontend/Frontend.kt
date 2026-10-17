package embedlang.frontend

import embedlang.Diagnostic
import embedlang.DiagnosticKind
import embedlang.ast.Program
import embedlang.ast.SourceLocation
import embedlang.parser.EmbedLangLexer
import embedlang.parser.EmbedLangParser
import embedlang.semantic.SemanticAnalyzer
import embedlang.ir.IrLowerer
import embedlang.ir.IrProgram
import org.antlr.v4.runtime.*

data class FrontendResult(val program: Program?, val diagnostics: List<Diagnostic>) {
    val isSuccess: Boolean get() = program != null && diagnostics.isEmpty()
}

data class IrResult(val ir: IrProgram?, val diagnostics: List<Diagnostic>) {
    val isSuccess: Boolean get() = ir != null && diagnostics.isEmpty()
}

object Frontend {
    fun parse(source: String, file: String = "<input>"): FrontendResult {
        val diagnostics = mutableListOf<Diagnostic>()
        val errors = object : BaseErrorListener() {
            override fun syntaxError(recognizer: Recognizer<*, *>?, offendingSymbol: Any?, line: Int,
                charPositionInLine: Int, msg: String?, e: RecognitionException?) {
                diagnostics += Diagnostic("SYNTAX_ERROR", msg ?: "Invalid syntax",
                    SourceLocation(file, line, charPositionInLine + 1), DiagnosticKind.SYNTAX)
            }
        }
        val lexer = EmbedLangLexer(CharStreams.fromString(source, file))
        lexer.removeErrorListeners()
        lexer.addErrorListener(errors)
        val parser = EmbedLangParser(CommonTokenStream(lexer))
        parser.removeErrorListeners()
        parser.addErrorListener(errors)
        val tree = parser.program()
        if (diagnostics.isNotEmpty()) return FrontendResult(null, diagnostics.toList())
        return FrontendResult(AstBuilder(file).visitProgram(tree), emptyList())
    }

    fun analyze(source: String, file: String = "<input>"): FrontendResult {
        val parsed = parse(source, file)
        val program = parsed.program ?: return parsed
        return FrontendResult(program, SemanticAnalyzer().analyze(program))
    }

    fun lower(source: String, file: String = "<input>"): IrResult {
        val parsed = parse(source, file)
        val program = parsed.program ?: return IrResult(null, parsed.diagnostics)
        val analysis = SemanticAnalyzer().analyzeTyped(program)
        if (!analysis.isSuccess) return IrResult(null, analysis.diagnostics)
        return IrResult(IrLowerer.lower(analysis), emptyList())
    }
}
