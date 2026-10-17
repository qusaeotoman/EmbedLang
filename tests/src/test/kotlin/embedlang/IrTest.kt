package embedlang

import embedlang.ast.SourceLocation
import embedlang.ast.Type
import embedlang.frontend.Frontend
import embedlang.ir.*
import embedlang.semantic.SemanticAnalyzer
import org.junit.jupiter.api.Test
import kotlin.test.*

class IrTest {
    private fun body(source: String) = "fn main() -> void {\n$source\n}"
    private fun lower(source: String): IrProgram {
        val result = Frontend.lower(source, "ir.emb")
        assertTrue(result.isSuccess, result.diagnostics.joinToString("\n"))
        return result.ir!!
    }
    private fun statements(source: String) = lower(body(source)).functions.single().body.statements

    @Test fun `constants carry exact contextual types and boundary values`() {
        val declarations = statements("""
            let min: i32 = -2147483648
            let max: u32 = 4294967295
            let byte: u8 = +255
            let flag: bool = false
        """.trimIndent()).map { it as IrLocalDeclaration }
        val integers = declarations.take(3).map { it.initializer as IrIntegerConstant }
        assertEquals(listOf(-2147483648L, 4294967295L, 255L), integers.map { it.value })
        assertEquals(listOf(Type.I32, Type.U32, Type.U8), integers.map { it.type })
        assertEquals(false, (declarations.last().initializer as IrBooleanConstant).value)
        assertEquals(Type.BOOL, declarations.last().initializer.type)
    }
    @Test fun `nested arithmetic uses semantic types without defaulting unsigned literals`() {
        val declarations = statements("""
            let now: u32 = millis()
            let newer: u32 = (1 + 2) * now
            let small: u8 = 1 + 2 * 3
            let test: bool = (1 + 2) < now
        """.trimIndent()).map { it as IrLocalDeclaration }
        val product = declarations[1].initializer as IrBinary
        assertEquals(Type.U32, product.type)
        assertEquals(Type.U32, product.left.type)
        assertEquals(Type.U32, (product.left as IrBinary).left.type)
        val small = declarations[2].initializer as IrBinary
        assertEquals(Type.U8, small.type)
        assertEquals(Type.U8, (small.right as IrBinary).left.type)
        val comparison = declarations[3].initializer as IrBinary
        assertEquals(Type.BOOL, comparison.type)
        assertEquals(Type.U32, (comparison.left as IrBinary).right.type)
    }
    @Test fun `all arithmetic operators preserved with types`() {
        val expression = (statements("let x: i32 = (10 + 2) * 3 / 2 % 5 - 1").single() as IrLocalDeclaration).initializer as IrBinary
        val modulo = expression.left as IrBinary
        val divide = modulo.left as IrBinary
        val multiply = divide.left as IrBinary
        val add = multiply.left as IrBinary
        assertEquals(listOf(IrBinaryOperator.SUBTRACT, IrBinaryOperator.MODULO, IrBinaryOperator.DIVIDE,
            IrBinaryOperator.MULTIPLY, IrBinaryOperator.ADD), listOf(expression, modulo, divide, multiply, add).map { it.operator })
        assertTrue(listOf(expression, modulo, divide, multiply, add).all { it.type == Type.I32 })
    }
    @Test fun `all comparison operators produce bool with integer operands`() {
        val symbols = listOf("==", "!=", "<", ">", "<=", ">=")
        val expected = listOf(IrBinaryOperator.EQUAL, IrBinaryOperator.NOT_EQUAL, IrBinaryOperator.LESS,
            IrBinaryOperator.GREATER, IrBinaryOperator.LESS_EQUAL, IrBinaryOperator.GREATER_EQUAL)
        symbols.zip(expected).forEach { (symbol, operator) ->
            val binary = (statements("let x: bool = 1 $symbol 2").single() as IrLocalDeclaration).initializer as IrBinary
            assertEquals(operator, binary.operator)
            assertEquals(Type.BOOL, binary.type)
            assertEquals(Type.I32, binary.left.type)
            assertEquals(Type.I32, binary.right.type)
        }
        val boolEquality = (statements("let x: bool = true == false").single() as IrLocalDeclaration).initializer as IrBinary
        assertEquals(Type.BOOL, boolEquality.left.type)
        assertEquals(Type.BOOL, boolEquality.right.type)
    }
    @Test fun `boolean operators preserve call operands and grouping`() {
        val expression = (statements("let b: bool = !gpio_read(BUTTON_1) || false && true").single() as IrLocalDeclaration).initializer as IrBinary
        assertEquals(IrBinaryOperator.OR, expression.operator)
        val not = expression.left as IrUnary
        assertEquals(IrUnaryOperator.NOT, not.operator)
        assertIs<IrCall>(not.operand)
        assertEquals(Type.BOOL, not.operand.type)
        assertEquals(IrBinaryOperator.AND, (expression.right as IrBinary).operator)
    }
    @Test fun `nonliteral unary signs stay operations`() {
        val declarations = statements("let x: i32 = 1\nlet n: i32 = -x\nlet p: i32 = +x").map { it as IrLocalDeclaration }
        val negative = declarations[1].initializer as IrUnary
        val positive = declarations[2].initializer as IrUnary
        assertEquals(IrUnaryOperator.NEGATE, negative.operator)
        assertEquals(IrUnaryOperator.POSITIVE, positive.operator)
        assertEquals(Type.I32, negative.type)
        assertSame(declarations[0].local, (negative.operand as IrLocalRead).local)
    }
    @Test fun `assignments and reads resolve to the original local`() {
        val nodes = statements("let x: i32 = 1\nx = x + 2")
        val local = (nodes[0] as IrLocalDeclaration).local
        val assignment = nodes[1] as IrAssignment
        assertSame(local, assignment.local)
        assertSame(local, ((assignment.value as IrBinary).left as IrLocalRead).local)
    }
    @Test fun `shadowed initializer reads outer local and assignments bind correct scope`() {
        val nodes = statements("let x: i32 = 10\nif true { let x: i32 = x + 1; x = 2 }\nx = 3")
        val outer = (nodes[0] as IrLocalDeclaration).local
        val innerNodes = (nodes[1] as IrIf).thenBlock.statements
        val declaration = innerNodes[0] as IrLocalDeclaration
        val inner = declaration.local
        assertEquals(0, outer.id)
        assertEquals(1, inner.id)
        assertSame(outer, ((declaration.initializer as IrBinary).left as IrLocalRead).local)
        assertSame(inner, (innerNodes[1] as IrAssignment).local)
        assertSame(outer, (nodes[2] as IrAssignment).local)
    }
    @Test fun `shadowed parameter with different type gets unique identity`() {
        val function = lower("fn f(x: u32) -> u32 { if true { let x: bool = true } return x }\n" + body("")).functions.first()
        val parameter = function.parameters.single()
        val inner = (((function.body.statements[0] as IrIf).thenBlock.statements.single()) as IrLocalDeclaration).local
        assertEquals(Type.U32, parameter.type)
        assertEquals(Type.BOOL, inner.type)
        assertNotEquals(parameter.id, inner.id)
        assertSame(parameter, ((function.body.statements[1] as IrReturn).value as IrLocalRead).local)
    }
    @Test fun `forward and recursive calls resolve function symbols and return types`() {
        val ir = lower("""
            fn main() -> void { f(5) }
            fn f(x: i32) -> i32 {
                if x <= 0 { return 0 }
                return f(x - 1)
            }
        """.trimIndent())
        val function = ir.functions[1]
        val forward = (ir.functions[0].body.statements.single() as IrCallStatement).call
        val recursive = (function.body.statements.last() as IrReturn).value as IrCall
        assertSame(function.symbol, forward.function)
        assertSame(function.symbol, recursive.function)
        assertFalse(function.symbol.isBuiltin)
        assertEquals(Type.I32, recursive.type)
        assertEquals(listOf(Type.I32), function.symbol.parameterTypes)
    }
    @Test fun `if else and returns are represented as nested blocks`() {
        val function = lower("fn choose(b: bool) -> u8 { if b { return 1 } else { return 2 } }\n" + body("")).functions.first()
        val branch = function.body.statements.single() as IrIf
        assertEquals(Type.BOOL, branch.condition.type)
        assertEquals(Type.U8, (branch.thenBlock.statements.single() as IrReturn).value!!.type)
        assertEquals(2L, ((branch.elseBlock!!.statements.single() as IrReturn).value as IrIntegerConstant).value)
        assertNull((statements("if true {}").single() as IrIf).elseBlock)
    }
    @Test fun `while condition retains calls instead of hoisting them`() {
        val loop = statements("while millis() < 1000 { delay_ms(1) }").single() as IrWhile
        val condition = loop.condition as IrBinary
        assertEquals(Type.BOOL, condition.type)
        assertEquals("millis", (condition.left as IrCall).function.name)
        assertEquals(Type.U32, condition.right.type)
        assertIs<IrCallStatement>(loop.body.statements.single())
    }
    @Test fun `void returns fallthrough and discarded results stay distinct`() {
        val nodes = statements("millis()\nreturn")
        assertEquals(Type.U32, (nodes.first() as IrCallStatement).call.type)
        assertNull((nodes.last() as IrReturn).value)
        assertTrue(statements("").isEmpty())
    }
    @Test fun `builtin calls and constants remain typed symbolic references`() {
        val nodes = statements("gpio_mode(LED_GREEN, OUTPUT)\ngpio_write(LED_GREEN, HIGH)\ndelay_ms(500)")
        val mode = (nodes[0] as IrCallStatement).call
        assertTrue(mode.function.isBuiltin)
        assertEquals(Type.VOID, mode.type)
        assertEquals(listOf(Type.U32, Type.U32), mode.arguments.map { it.type })
        assertEquals("LED_GREEN", (mode.arguments[0] as IrBuiltinConstant).name)
        val write = (nodes[1] as IrCallStatement).call
        assertEquals(Type.BOOL, write.arguments[1].type)
        assertEquals("HIGH", (write.arguments[1] as IrBuiltinConstant).name)
        assertEquals(Type.U32, (nodes[2] as IrCallStatement).call.arguments.single().type)
    }
    @Test fun `semantic and syntax errors never produce IR`() {
        for (source in listOf(body("let x: i32 = true"), body("missing()"), body("let x: i32 = @"))) {
            val ir = Frontend.lower(source, "bad.emb")
            assertNull(ir.ir)
            assertFalse(ir.isSuccess)
            assertEquals(Frontend.analyze(source, "bad.emb").diagnostics, ir.diagnostics)
        }
    }
    @Test fun `direct lowering rejects unsuccessful analysis`() {
        val program = Frontend.parse(body("missing()" )).program!!
        val analysis = SemanticAnalyzer().analyzeTyped(program)
        assertFalse(analysis.isSuccess)
        assertFailsWith<IllegalArgumentException> { IrLowerer.lower(analysis) }
    }
    @Test fun `IR preserves source locations`() {
        val declaration = statements("let x: i32 = 10").single() as IrLocalDeclaration
        assertEquals(SourceLocation("ir.emb", 2, 1), declaration.location)
        assertEquals(declaration.location, declaration.local.location)
        assertEquals(SourceLocation("ir.emb", 2, 14), declaration.initializer.location)
    }
    @Test fun `printer matches both shipped example snapshots`() {
        for (name in listOf("basic", "blink")) {
            val program = lower(javaClass.getResource("/$name.emb")!!.readText())
            val expected = javaClass.getResource("/ir/$name.ir")!!.readText().replace("\r\n", "\n")
            assertEquals(expected, IrPrinter.print(program))
        }
    }
    @Test fun `printer shows shadowed ids and lowering is deterministic across runs`() {
        val source = body("let x: i32 = 1\nif true { let x: bool = false }")
        val first = IrPrinter.print(lower(source))
        assertContains(first, "%x.0:i32")
        assertContains(first, "%x.1:bool")
        assertEquals(first, IrPrinter.print(lower(source)))
    }
}
