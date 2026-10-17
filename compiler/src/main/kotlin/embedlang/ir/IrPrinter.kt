package embedlang.ir

/** Deterministic debug format, independent of host newline conventions. */
object IrPrinter {
    fun print(program: IrProgram): String = program.functions.joinToString("\n\n", postfix = "\n") { function ->
        buildString {
            append("func @${function.symbol.name}(")
            append(function.parameters.joinToString(", ") { local(it) })
            append(") -> ${function.symbol.returnType.spelling} {\n")
            appendBlock(function.body, 1)
            append('}')
        }
    }

    private fun local(local: IrLocal) = "%${local.name}.${local.id}:${local.type.spelling}"

    private fun StringBuilder.appendBlock(block: IrBlock, depth: Int) {
        val indent = "  ".repeat(depth)
        for (statement in block.statements) {
            append(indent)
            when (statement) {
                is IrLocalDeclaration -> append("local ${local(statement.local)} = ${expression(statement.initializer)}\n")
                is IrAssignment -> append("store ${local(statement.local)} <- ${expression(statement.value)}\n")
                is IrCallStatement -> append("${expression(statement.call)}\n")
                is IrReturn -> append("return${statement.value?.let { " ${expression(it)}" } ?: ""}\n")
                is IrIf -> {
                    append("if ${expression(statement.condition)} {\n")
                    appendBlock(statement.thenBlock, depth + 1)
                    append("$indent}")
                    if (statement.elseBlock != null) {
                        append(" else {\n")
                        appendBlock(statement.elseBlock, depth + 1)
                        append("$indent}")
                    }
                    append('\n')
                }
                is IrWhile -> {
                    append("while ${expression(statement.condition)} {\n")
                    appendBlock(statement.body, depth + 1)
                    append("$indent}\n")
                }
            }
        }
    }

    private fun expression(expression: IrExpression): String = when (expression) {
        is IrIntegerConstant -> "${expression.value}:${expression.type.spelling}"
        is IrBooleanConstant -> "${expression.value}:bool"
        is IrBuiltinConstant -> "$${expression.name}:${expression.type.spelling}"
        is IrLocalRead -> local(expression.local)
        is IrCall -> "call ${if (expression.function.isBuiltin) "builtin " else ""}@${expression.function.name}" +
            "(${expression.arguments.joinToString(", ") { expression(it) }}):${expression.type.spelling}"
        is IrUnary -> "${expression.operator.mnemonic}(${expression(expression.operand)}):${expression.type.spelling}"
        is IrBinary -> "${expression.operator.mnemonic}(${expression(expression.left)}, " +
            "${expression(expression.right)}):${expression.type.spelling}"
    }
}
