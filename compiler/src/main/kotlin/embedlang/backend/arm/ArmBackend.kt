package embedlang.backend.arm

import embedlang.ast.Type
import embedlang.ast.SourceLocation
import embedlang.ir.*

/** GNU Thumb-2 text emitter. Consumes validated typed IR without modifying it. */
object ArmBackend {
    fun emit(program: IrProgram, debugLines: Boolean = false): String = Emitter(debugLines).emit(program)

    private class Emitter(private val debugLines: Boolean) {
        private val externals = sortedSetOf<String>()
        private val sourceFiles = linkedMapOf<String, Int>()
        private fun sourceFile(file: String) = sourceFiles.getOrPut(file) { sourceFiles.size + 1 }
        private fun quotedFile(file: String) = buildString {
            append('"')
            // ASCII assembly carries exact UTF-8 path bytes, independent of the
            // Java process's console encoding. GAS decodes these C escapes.
            file.toByteArray(Charsets.UTF_8).forEach { byte ->
                val code = byte.toInt() and 255
                when (code) {
                    92 -> append("\\\\")
                    34 -> append("\\\"")
                    10 -> append("\\n")
                    13 -> append("\\r")
                    9 -> append("\\t")
                    else -> if (code < 32 || code >= 127)
                        append("\\%03o".format(code)) else append(code.toChar())
                }
            }
            append('"')
        }
        private var nextLabel = 0
        private fun label(kind: String) = ".L${kind}_${nextLabel++}"
        private fun symbol(function: IrFunctionSymbol) =
            if (function.isBuiltin) "embed_${function.name}" else if (function.name == "main") "main" else "embed_fn_${function.name}"

        fun emit(program: IrProgram): String {
            val bodies = program.functions.map { FunctionEmitter(it).emit() }
            return buildString {
                append(".syntax unified\n.cpu cortex-m4\n.thumb\n.text\n")
                sourceFiles.forEach { (file, number) -> append(".file $number ${quotedFile(file)}\n") }
                externals.forEach { append(".extern $it\n") }
                bodies.forEach { append('\n'); append(it) }
                append("\n.section .note.GNU-stack,\"\",%progbits\n")
            }
        }

        private inner class FunctionEmitter(private val function: IrFunction) {
            private val locals = linkedMapOf<Int, IrLocal>()
            private val body = StringBuilder()
            private var temporaryDepth = 0
            private var peakTemporaries = 0
            private val returnLabel = label("return")

            private fun instruction(text: String) { body.append("    $text\n") }
            private fun mark(name: String) { body.append("$name:\n") }
            private fun location(location: SourceLocation, statement: Boolean = true, flags: String = "") {
                if (!debugLines) return
                val file = sourceFile(location.file)
                body.append(".loc $file ${location.line} ${location.column} is_stmt ${if (statement) 1 else 0}$flags\n")
            }
            private fun reserve(count: Int = 1): Int {
                val first = temporaryDepth
                temporaryDepth += count
                peakTemporaries = maxOf(peakTemporaries, temporaryDepth)
                return first
            }
            private fun release(count: Int = 1) { temporaryDepth -= count; check(temporaryDepth >= 0) }
            private fun tempOffset(index: Int) = (locals.size + index) * 4
            private fun localOffset(local: IrLocal) = locals.keys.indexOf(local.id).also { check(it >= 0) } * 4

            private fun collect(block: IrBlock) {
                block.statements.forEach {
                    when (it) {
                        is IrLocalDeclaration -> { check(locals.put(it.local.id, it.local) == null) }
                        is IrIf -> { collect(it.thenBlock); it.elseBlock?.let { block -> collect(block) } }
                        is IrWhile -> collect(it.body)
                        else -> Unit
                    }
                }
            }

            fun emit(): String {
                function.parameters.forEach { check(locals.put(it.id, it) == null) }
                collect(function.body)
                block(function.body)
                check(temporaryDepth == 0)
                val frameSize = aligned((locals.size + peakTemporaries) * 4)
                val instructions = body.toString()
                body.clear()
                val name = symbol(function.symbol)
                body.append(".balign 2\n.global $name\n.type $name, %function\n.thumb_func\n$name:\n")
                location(function.location, statement = false)
                instruction("push {r7, lr}")
                adjustStack(frameSize, subtract = true)
                instruction("mov r7, sp")
                function.parameters.forEachIndexed { index, parameter ->
                    if (index < 4) store("r$index", localOffset(parameter))
                    else {
                        load("r0", frameSize + 8 + (index - 4) * 4)
                        normalize(parameter.type)
                        store("r0", localOffset(parameter))
                    }
                }
                body.append(instructions)
                mark(returnLabel)
                location(function.location, statement = false, flags = " epilogue_begin")
                instruction("mov sp, r7")
                adjustStack(frameSize, subtract = false)
                instruction("pop {r7, pc}")
                body.append(".size $name, .-$name\n")
                return body.toString()
            }

            private fun aligned(bytes: Int) = Math.addExact(bytes, 7) / 8 * 8
            private fun immediate(register: String, value: Long) {
                val bits = value and 0xffffffffL
                if (bits <= 255) instruction("movs $register, #$bits")
                else {
                    instruction("movw $register, #${bits and 65535}")
                    if (bits ushr 16 != 0L) instruction("movt $register, #${bits ushr 16}")
                }
            }
            private fun adjustStack(bytes: Int, subtract: Boolean) {
                if (bytes == 0) return
                immediate("r12", bytes.toLong())
                instruction("${if (subtract) "sub" else "add"}.w sp, sp, r12")
            }
            private fun memory(operation: String, register: String, offset: Int, base: String = "r7") {
                if (offset <= 4095) instruction("$operation.w $register, [$base, #$offset]")
                else {
                    immediate("r12", offset.toLong())
                    instruction("add.w r12, $base, r12")
                    instruction("$operation.w $register, [r12]")
                }
            }
            private fun load(register: String, offset: Int) = memory("ldr", register, offset)
            private fun store(register: String, offset: Int) = memory("str", register, offset)
            private fun normalize(type: Type) {
                when (type) {
                    Type.U8 -> instruction("uxtb r0, r0")
                    Type.BOOL -> truth("ne")
                    else -> Unit
                }
            }
            private fun truth(condition: String, compare: Boolean = true) {
                if (compare) instruction("cmp r0, #0")
                instruction("mov.w r0, #0")
                instruction("it $condition")
                instruction("mov$condition.w r0, #1")
            }

            private fun block(block: IrBlock) {
                block.statements.forEach { statement ->
                    location(statement.location)
                    when (statement) {
                        is IrLocalDeclaration -> { expression(statement.initializer); store("r0", localOffset(statement.local)) }
                        is IrAssignment -> { expression(statement.value); store("r0", localOffset(statement.local)) }
                        is IrCallStatement -> call(statement.call)
                        is IrReturn -> { statement.value?.let { expression(it) }; instruction("b.w $returnLabel") }
                        is IrIf -> {
                            val otherwise = label("else")
                            val end = label("if_end")
                            expression(statement.condition)
                            instruction("cmp r0, #0")
                            instruction("beq.w $otherwise")
                            block(statement.thenBlock)
                            location(statement.location, statement = false)
                            instruction("b.w $end")
                            mark(otherwise)
                            statement.elseBlock?.let { block(it) }
                            mark(end)
                        }
                        is IrWhile -> {
                            val start = label("while_start")
                            val end = label("while_end")
                            mark(start)
                            expression(statement.condition)
                            instruction("cmp r0, #0")
                            instruction("beq.w $end")
                            block(statement.body)
                            location(statement.location, statement = false)
                            instruction("b.w $start")
                            mark(end)
                        }
                    }
                }
            }

            private fun expression(value: IrExpression) {
                when (value) {
                    is IrIntegerConstant -> immediate("r0", value.value)
                    is IrBooleanConstant -> immediate("r0", if (value.value) 1 else 0)
                    is IrBuiltinConstant -> {
                        when (value.name) {
                            "HIGH" -> immediate("r0", 1)
                            "LOW" -> immediate("r0", 0)
                            else -> {
                                val name = "embed_const_${value.name}"
                                externals += name
                                instruction("movw r0, #:lower16:$name")
                                instruction("movt r0, #:upper16:$name")
                                instruction("ldr r0, [r0]")
                            }
                        }
                    }
                    is IrLocalRead -> { load("r0", localOffset(value.local)); normalize(value.type) }
                    is IrCall -> call(value)
                    is IrUnary -> {
                        expression(value.operand)
                        when (value.operator) {
                            IrUnaryOperator.NEGATE -> instruction("rsb.w r0, r0, #0")
                            IrUnaryOperator.NOT -> truth("eq")
                            IrUnaryOperator.POSITIVE -> Unit
                        }
                        if (value.type == Type.U8) normalize(value.type)
                    }
                    is IrBinary -> binary(value)
                }
            }

            private fun binary(value: IrBinary) {
                if (value.operator == IrBinaryOperator.AND || value.operator == IrBinaryOperator.OR) {
                    val end = label("bool_end")
                    expression(value.left)
                    instruction("cmp r0, #0")
                    instruction("${if (value.operator == IrBinaryOperator.AND) "beq" else "bne"}.w $end")
                    expression(value.right)
                    mark(end)
                    return
                }
                val slot = reserve()
                expression(value.left)
                store("r0", tempOffset(slot))
                expression(value.right)
                load("r1", tempOffset(slot))
                release()
                val signed = value.left.type == Type.I32
                when (value.operator) {
                    IrBinaryOperator.ADD -> instruction("add.w r0, r1, r0")
                    IrBinaryOperator.SUBTRACT -> instruction("sub.w r0, r1, r0")
                    IrBinaryOperator.MULTIPLY -> instruction("mul r0, r1, r0")
                    IrBinaryOperator.DIVIDE -> instruction("${if (signed) "sdiv" else "udiv"} r0, r1, r0")
                    IrBinaryOperator.MODULO -> {
                        instruction("${if (signed) "sdiv" else "udiv"} r2, r1, r0")
                        instruction("mls r0, r2, r0, r1")
                    }
                    else -> {
                        val condition = when (value.operator) {
                            IrBinaryOperator.EQUAL -> "eq"
                            IrBinaryOperator.NOT_EQUAL -> "ne"
                            IrBinaryOperator.LESS -> if (signed) "lt" else "lo"
                            IrBinaryOperator.GREATER -> if (signed) "gt" else "hi"
                            IrBinaryOperator.LESS_EQUAL -> if (signed) "le" else "ls"
                            IrBinaryOperator.GREATER_EQUAL -> if (signed) "ge" else "hs"
                            else -> error("Unexpected binary operator")
                        }
                        instruction("cmp r1, r0")
                        truth(condition, compare = false)
                    }
                }
                if (value.type == Type.U8) normalize(value.type)
            }

            private fun call(value: IrCall) {
                val count = value.arguments.size
                val first = reserve(count)
                value.arguments.forEachIndexed { index, argument ->
                    expression(argument)
                    store("r0", tempOffset(first + index))
                }
                val outgoingBytes = aligned(maxOf(0, count - 4) * 4)
                adjustStack(outgoingBytes, subtract = true)
                for (index in 4 until count) {
                    load("r0", tempOffset(first + index))
                    memory("str", "r0", (index - 4) * 4, base = "sp")
                }
                for (index in 0 until minOf(4, count)) load("r$index", tempOffset(first + index))
                val name = symbol(value.function)
                if (value.function.isBuiltin) externals += name
                instruction("bl $name")
                adjustStack(outgoingBytes, subtract = false)
                release(count)
                normalize(value.type)
            }
        }
    }
}
