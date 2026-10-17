package embedlang

import embedlang.backend.arm.ArmBackend
import embedlang.frontend.Frontend
import org.junit.jupiter.api.Test
import kotlin.test.*

class ArmBackendTest {
    private fun main(body: String) = "fn main() -> void {\n$body\n}"
    private fun emit(source: String): String {
        val result = Frontend.lower(source)
        assertTrue(result.isSuccess, result.diagnostics.toString())
        return ArmBackend.emit(result.ir!!)
    }

    @Test fun `GNU target directives and function metadata`() {
        val asm = emit(main(""))
        assertTrue(asm.startsWith(".syntax unified\n.cpu cortex-m4\n.thumb\n.text\n"))
        assertContains(asm, ".global main\n.type main, %function\n.thumb_func\nmain:")
        assertContains(asm, "push {r7, lr}")
        assertContains(asm, "pop {r7, pc}")
        assertContains(asm, ".size main, .-main")
    }
    @Test fun `full width signed and unsigned constants use exact bit patterns`() {
        val asm = emit(main("let x: i32 = -2147483648\nlet y: u32 = 4294967295\nlet b: bool = true"))
        assertContains(asm, "movw r0, #0\n    movt r0, #32768")
        assertContains(asm, "movw r0, #65535\n    movt r0, #65535")
        assertContains(asm, "movs r0, #1")
    }
    @Test fun `locals and shadowing use distinct stable stack slots`() {
        val asm = emit(main("let x: i32 = 1\nif true { let x: i32 = 2; x = 3 }\nx = 4"))
        assertContains(asm, "movs r0, #3\n    str.w r0, [r7, #4]")
        assertContains(asm, "movs r0, #4\n    str.w r0, [r7, #0]")
    }
    @Test fun `arithmetic and typed division remainder`() {
        val signed = emit(main("let x: i32 = (10 + 2) * 3 / 2 % 5 - 1"))
        listOf("add.w r0, r1, r0", "sub.w r0, r1, r0", "mul r0, r1, r0",
            "sdiv r0, r1, r0", "sdiv r2, r1, r0", "mls r0, r2, r0, r1").forEach { assertContains(signed, it) }
        val unsigned = emit(main("let x: u32 = 4294967295 / 2 % 3"))
        assertContains(unsigned, "udiv r0, r1, r0")
        assertContains(unsigned, "udiv r2, r1, r0")
        assertFalse(unsigned.contains("sdiv"))
    }
    @Test fun `u8 arithmetic is narrowed at expression boundaries`() {
        val asm = emit(main("let x: u8 = (255 + 1) * 2"))
        assertContains(asm, "add.w r0, r1, r0\n    uxtb r0, r0")
        assertContains(asm, "mul r0, r1, r0\n    uxtb r0, r0")
    }
    @Test fun `comparison conditions reflect signedness`() {
        listOf("<" to ("lt" to "lo"), ">" to ("gt" to "hi"), "<=" to ("le" to "ls"),
            ">=" to ("ge" to "hs"), "==" to ("eq" to "eq"), "!=" to ("ne" to "ne")).forEach { (op, conditions) ->
            for ((type, condition) in listOf("i32" to conditions.first, "u32" to conditions.second)) {
                val asm = emit(main("let x: $type = 1\nlet b: bool = x $op 2"))
                assertContains(asm, "cmp r1, r0\n    mov.w r0, #0\n    it $condition\n    mov$condition.w r0, #1")
            }
        }
    }
    @Test fun `short circuit branches skip RHS calls`() {
        for ((op, branch) in listOf("&&" to "beq", "||" to "bne")) {
            val asm = emit(main("let b: bool = true $op gpio_read(BUTTON_1)"))
            val jump = Regex("$branch\\.w (\\.Lbool_end_\\d+)").find(asm)!!
            val call = asm.indexOf("bl embed_gpio_read")
            assertTrue(jump.range.first < call)
            assertTrue(asm.indexOf(jump.groupValues[1] + ":") > call)
        }
    }
    @Test fun `unary logical not and negate`() {
        val asm = emit(main("let x: i32 = 1\nlet y: i32 = -x\nlet b: bool = !false"))
        assertContains(asm, "rsb.w r0, r0, #0")
        assertContains(asm, "it eq\n    moveq.w r0, #1")
    }
    @Test fun `loop condition is inside loop labels`() {
        val asm = emit(main("while millis() < 1000 { delay_ms(1) }"))
        val start = Regex("(\\.Lwhile_start_\\d+):").find(asm)!!.groupValues[1]
        val end = Regex("(\\.Lwhile_end_\\d+):").find(asm)!!.groupValues[1]
        assertTrue(asm.indexOf(start + ":") < asm.indexOf("bl embed_millis"))
        assertContains(asm, "beq.w $end")
        assertContains(asm, "b.w $start")
    }
    @Test fun `nested branches have unique defined labels`() {
        val asm = emit(main("if true { while false { if false {} else {} } } else { while false {} }"))
        val labels = Regex("(?m)^(\\.L\\w+):").findAll(asm).map { it.groupValues[1] }.toList()
        assertEquals(labels.size, labels.toSet().size)
        Regex("b(?:eq|ne)?\\.w (\\.L\\w+)").findAll(asm).forEach { assertTrue(it.groupValues[1] in labels) }
    }
    @Test fun `parameter spills and value return use AAPCS registers`() {
        val asm = emit("fn add(a: i32, b: i32) -> i32 { return a + b }\n" + main("add(1, 2)"))
        assertContains(asm, "str.w r0, [r7, #0]\n    str.w r1, [r7, #4]")
        assertContains(asm, "bl embed_fn_add")
        assertContains(asm, "ldr.w r0, [r7, #0]")
        assertContains(asm, "b.w .Lreturn_0")
    }
    @Test fun `more than four parameters use aligned outgoing stack arguments`() {
        val asm = emit("fn f(a: i32, b: i32, c: i32, d: i32, e: i32, g: i32) -> i32 { return e + g }\n" + main("f(1, 2, 3, 4, 5, 6)"))
        assertContains(asm, "str.w r0, [sp, #0]")
        assertContains(asm, "str.w r0, [sp, #4]")
        // f has six locals plus one scratch word, rounded to 32 bytes; saved r7/lr take 8.
        assertContains(asm, "ldr.w r0, [r7, #40]")
        assertContains(asm, "ldr.w r0, [r7, #44]")
        assertContains(asm, "bl embed_fn_f\n    movs r12, #8\n    add.w sp, sp, r12")
    }
    @Test fun `nested calls finish before final argument registers are loaded`() {
        val asm = emit("fn f(a: u32, b: u32) -> u32 { return a + b }\n" + main("let x: u32 = millis() + f(millis(), millis())"))
        val calls = Regex("bl embed_millis").findAll(asm).map { it.range.first }.toList()
        assertEquals(3, calls.size)
        val finalLoad = asm.lastIndexOf("ldr.w r1,")
        assertTrue(finalLoad > calls.last())
        assertTrue(asm.indexOf("bl embed_fn_f") > calls.last())
        assertContains(asm, "str.w r0, [r7, #4]") // outer LHS survives every call
    }
    @Test fun `recursive and forward calls have collision safe symbols`() {
        val asm = emit(main("f(2)") + "\nfn f(n: i32) -> i32 { if n <= 0 { return 0 } return f(n - 1) }")
        assertEquals(2, Regex("bl embed_fn_f\\b").findAll(asm).count())
        assertContains(asm, ".global embed_fn_f")
    }
    @Test fun `hardware functions remain external and constants are not guessed`() {
        val asm = emit(main("gpio_mode(LED_GREEN, OUTPUT)\ngpio_write(LED_GREEN, HIGH)\ngpio_toggle(LED_GREEN)\ngpio_read(BUTTON_1)\ndelay_ms(1)\nmillis()"))
        listOf("gpio_mode", "gpio_write", "gpio_toggle", "gpio_read", "delay_ms", "millis").forEach {
            assertContains(asm, ".extern embed_$it\n")
            assertContains(asm, "bl embed_$it")
            assertFalse(asm.contains("embed_$it:"))
        }
        assertContains(asm, "#:lower16:embed_const_LED_GREEN")
        assertContains(asm, ".extern embed_const_OUTPUT")
        assertFalse(asm.contains("embed_const_HIGH"))
    }
    @Test fun `large frames do not rely on immediate offset or literal pool limits`() {
        val declarations = (0..1030).joinToString("\n") { "let x$it: i32 = $it" }
        val asm = emit(main(declarations + "\nx1030 = x1029"))
        assertContains(asm, "add.w r12, r7, r12")
        assertContains(asm, "str.w r0, [r12]")
        assertFalse(asm.contains("ldr r0, ="))
    }
    @Test fun `both example assembly files match deterministic generation`() {
        for (name in listOf("basic", "blink")) {
            val source = javaClass.getResource("/$name.emb")!!.readText()
            val asm = emit(source)
            assertEquals(asm, emit(source))
            assertEquals(javaClass.getResource("/$name.s")!!.readText().replace("\r\n", "\n"), asm)
        }
    }
}
