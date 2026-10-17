package embedlang

import embedlang.ast.*
import embedlang.frontend.Frontend
import org.junit.jupiter.api.Test
import kotlin.test.*

class FrontendTest {
    private fun body(source: String) = "fn main() -> void {\n$source\n}"
    private fun valid(source: String) {
        val result = Frontend.analyze(source, "test.emb")
        assertTrue(result.isSuccess, result.diagnostics.joinToString("\n"))
    }
    private fun invalid(source: String, code: String): List<Diagnostic> {
        val result = Frontend.analyze(source, "test.emb")
        assertFalse(result.isSuccess)
        assertTrue(result.diagnostics.any { it.code == code }, result.diagnostics.joinToString("\n"))
        return result.diagnostics
    }

    @Test fun `valid variable declaration`() = valid(body("let x: i32 = 10"))
    @Test fun `type mismatch`() { invalid(body("let x: bool = 10"), "TYPE_MISMATCH") }
    @Test fun `undefined variable`() { invalid(body("let x: i32 = missing"), "UNDEFINED_VARIABLE") }
    @Test fun `undefined function`() { invalid(body("missing()"), "UNDEFINED_FUNCTION") }
    @Test fun `invalid function argument type`() { invalid(body("delay_ms(true)"), "TYPE_MISMATCH") }
    @Test fun `missing return value`() {
        invalid("fn f() -> i32 { return }\nfn main() -> void {}", "MISSING_RETURN_VALUE")
    }
    @Test fun `if condition must be bool`() { invalid(body("if 1 {}"), "TYPE_MISMATCH") }
    @Test fun `while condition must be bool`() { invalid(body("while 1 {}"), "TYPE_MISMATCH") }
    @Test fun `valid function call`() = valid("""
        fn main() -> void { let sum: i32 = add(1, 2) }
        fn add(a: i32, b: i32) -> i32 { return a + b }
    """.trimIndent())
    @Test fun `valid main function`() = valid("fn main() -> void {}")

    @Test fun `all builtin signatures and constants`() = valid(body("""
        gpio_mode(LED_GREEN, OUTPUT)
        gpio_mode(BUTTON_1, INPUT)
        gpio_write(LED_YELLOW, HIGH)
        gpio_write(LED_RED, LOW)
        let pressed: bool = gpio_read(BUTTON_1)
        gpio_toggle(LED_GREEN)
        delay_ms(500)
        let now: u32 = millis()
    """.trimIndent()))

    @Test fun `examples pass frontend`() {
        for (name in listOf("basic.emb", "blink.emb")) {
            val source = javaClass.getResource("/$name")!!.readText()
            valid(source)
        }
    }

    @Test fun `missing and invalid entry point`() {
        invalid("fn f() -> void {}", "MISSING_MAIN")
        invalid("fn main(x: i32) -> void {}", "INVALID_MAIN")
        invalid("fn main() -> i32 { return 1 }", "INVALID_MAIN")
    }
    @Test fun `argument count checked for builtin and user function`() {
        invalid(body("gpio_toggle()"), "ARGUMENT_COUNT")
        invalid("fn f(x: i32) -> void {}\n" + body("f(1, 2)"), "ARGUMENT_COUNT")
    }
    @Test fun `assignment checked`() {
        valid(body("let x: i32 = 10\nx = 20"))
        invalid(body("let x: i32 = 10\nx = false"), "TYPE_MISMATCH")
        invalid(body("missing = 1"), "UNDEFINED_VARIABLE")
        invalid(body("HIGH = false"), "ASSIGN_CONSTANT")
    }
    @Test fun `block scopes and shadowing`() {
        valid(body("let x: i32 = 1\nif true { let x: bool = false }\nx = 2"))
        invalid(body("if true { let x: i32 = 1 }\nx = 2"), "UNDEFINED_VARIABLE")
        invalid(body("let x: i32 = x"), "UNDEFINED_VARIABLE")
    }
    @Test fun `duplicates and reserved names`() {
        invalid(body("let x: i32 = 1\nlet x: i32 = 2"), "DUPLICATE_VARIABLE")
        invalid(body("let LED_GREEN: u32 = 1"), "DUPLICATE_VARIABLE")
        invalid("fn gpio_read() -> void {}\n" + body(""), "DUPLICATE_FUNCTION")
        invalid("fn f() -> void {}\nfn f() -> void {}\n" + body(""), "DUPLICATE_FUNCTION")
        invalid("fn f(x: i32, x: i32) -> void {}\n" + body(""), "DUPLICATE_VARIABLE")
    }
    @Test fun `void prohibited in values`() {
        invalid(body("let x: void = delay_ms(1)"), "INVALID_TYPE")
        invalid("fn f(x: void) -> void {}\n" + body(""), "INVALID_TYPE")
        invalid(body("let x: i32 = delay_ms(1)"), "TYPE_MISMATCH")
        invalid(body("let x: bool = delay_ms(1) == delay_ms(2)"), "INVALID_OPERAND")
    }
    @Test fun `return values and all paths checked`() {
        invalid("fn f() -> bool { return 1 }\n" + body(""), "TYPE_MISMATCH")
        invalid(body("return 1"), "UNEXPECTED_RETURN_VALUE")
        invalid("fn f() -> i32 {}\n" + body(""), "MISSING_RETURN")
        invalid("fn f(x: bool) -> i32 { if x { return 1 } }\n" + body(""), "MISSING_RETURN")
        valid("fn f(x: bool) -> i32 { if x { return 1 } else { return 2 } }\n" + body(""))
        valid("fn f() -> i32 { while true {} }\n" + body(""))
        invalid("fn f(x: bool) -> i32 { while x { return 1 } }\n" + body(""), "MISSING_RETURN")
    }
    @Test fun `recursive function`() = valid("""
        fn factorial(n: i32) -> i32 {
            if n <= 1 { return 1 }
            return n * factorial(n - 1)
        }
        fn main() -> void { factorial(5) }
    """.trimIndent())
    @Test fun `integer boundaries and contextual literals`() {
        valid(body("""
            let min: i32 = -2147483648
            let max: i32 = 2147483647
            let byte: u8 = 255
            let word: u32 = 4294967295
            let smaller: u32 = word - 1
            let equal: bool = 4294967295 == word
            let expression: u8 = 1 + 2 * 3
        """.trimIndent()))
        for (declaration in listOf("let x: i32 = 2147483648", "let x: i32 = -2147483649",
            "let x: u8 = 256", "let x: u8 = -1", "let x: u32 = 4294967296",
            "let x: u32 = -1", "let x: i32 = 99999999999999999999999999999999")) {
            invalid(body(declaration), "INTEGER_OUT_OF_RANGE")
        }
    }
    @Test fun `numeric types never implicitly converted`() {
        invalid(body("let x: u32 = 1\nlet y: i32 = x"), "TYPE_MISMATCH")
        invalid(body("let x: u32 = 1\nlet y: i32 = 2\nlet z: bool = x < y"), "TYPE_MISMATCH")
        invalid(body("let x: u32 = 1\nlet y: u32 = -x"), "INVALID_OPERAND")
    }
    @Test fun `operators checked`() {
        valid(body("let x: i32 = (10 + 2) * 3 / 2 % 5 - 1\nlet b: bool = x != 0 || x < 1 && !false"))
        invalid(body("let x: bool = true + false"), "INVALID_OPERAND")
        invalid(body("let x: bool = true < false"), "INVALID_OPERAND")
        invalid(body("let x: bool = 1 && true"), "TYPE_MISMATCH")
        invalid(body("let x: bool = !1"), "TYPE_MISMATCH")
    }
    @Test fun `AST preserves precedence associativity and locations`() {
        val result = Frontend.parse(body("let x: i32 = 10 - 2 - 3 * 4"), "ast.emb")
        assertTrue(result.isSuccess, result.diagnostics.toString())
        val declaration = result.program!!.functions.single().body.statements.single() as VariableDeclaration
        val subtract = declaration.initializer as BinaryExpression
        assertEquals(BinaryOperator.SUBTRACT, subtract.operator)
        assertEquals(BinaryOperator.SUBTRACT, (subtract.left as BinaryExpression).operator)
        assertEquals(BinaryOperator.MULTIPLY, (subtract.right as BinaryExpression).operator)
        assertEquals(SourceLocation("ast.emb", 2, 1), declaration.location)
    }
    @Test fun `unary and boolean precedence in AST`() {
        val result = Frontend.parse(body("let b: bool = !true || false && 1 + 2 * 3 == 7"))
        assertTrue(result.isSuccess)
        val initializer = (result.program!!.functions.single().body.statements.single() as VariableDeclaration).initializer as BinaryExpression
        assertEquals(BinaryOperator.OR, initializer.operator)
        assertIs<UnaryExpression>(initializer.left)
        assertEquals(BinaryOperator.AND, (initializer.right as BinaryExpression).operator)
    }
    @Test fun `syntax errors stop before AST and have source location`() {
        val result = Frontend.analyze(body("let x: i32 = @"), "broken.emb")
        assertNull(result.program)
        assertTrue(result.diagnostics.isNotEmpty())
        assertTrue(result.diagnostics.all { it.kind == DiagnosticKind.SYNTAX && it.location.file == "broken.emb" })
    }
    @Test fun `semantic error location`() {
        val diagnostics = invalid(body("let x: i32 = missing"), "UNDEFINED_VARIABLE")
        assertEquals(SourceLocation("test.emb", 2, 14), diagnostics.single().location)
    }
    @Test fun `simple statements require separator`() {
        invalid(body("let x: i32 = 1 let y: i32 = 2"), "SYNTAX_ERROR")
        valid(body("let x: i32 = 1; let y: i32 = 2;"))
    }
    @Test fun `else on next line comments and CRLF`() {
        valid(body("if true { // comment\nreturn\n}\nelse { return }").replace("\n", "\r\n"))
        valid(body("if true {}\nlet x: i32 = 1"))
    }
    @Test fun `unsupported constructs are syntax errors`() {
        for (source in listOf("let x: i32 = 1.5", "let x: i32 = \"text\"", "class C {}",
            "fn nested() -> void {}", "let x: float = 1")) invalid(body(source), "SYNTAX_ERROR")
    }
    @Test fun `analysis state isolated between runs`() {
        valid("fn f() -> void {}\n" + body("f()"))
        invalid(body("f()"), "UNDEFINED_FUNCTION")
    }
    @Test fun `nested contextual arithmetic and boolean builtin value`() = valid(body("""
        let now: u32 = millis()
        let newer: u32 = (1 + 2) * now
        let test: bool = (1 + 2 * 3) < now
        delay_ms((10 + 20) * 2)
        gpio_write(LED_GREEN, gpio_read(BUTTON_1) && HIGH)
    """.trimIndent()))
    @Test fun `errors in unreachable statements remain visible`() {
        invalid(body("return\nmissing()"), "UNDEFINED_FUNCTION")
    }
    @Test fun `empty source still requires main`() { invalid("", "MISSING_MAIN") }
}
