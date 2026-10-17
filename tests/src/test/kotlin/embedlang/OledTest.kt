package embedlang

import embedlang.backend.arm.ArmBackend
import embedlang.frontend.Frontend
import org.junit.jupiter.api.Test
import kotlin.test.*

class OledTest {
    private fun program(body: String) = "fn main() -> void {\n$body\n}"

    @Test fun `OLED scalar signatures lower to ordinary runtime calls`() {
        val result = Frontend.lower(program("""
            let ready: bool = oled_init()
            oled_clear()
            let placed: bool = oled_cursor(15, 27)
            let written: bool = oled_write_char(84)
            let sent: bool = oled_update()
        """.trimIndent()))
        assertTrue(result.isSuccess, result.diagnostics.toString())
        val asm = ArmBackend.emit(result.ir!!)
        for (name in listOf("init", "clear", "cursor", "write_char", "update")) {
            assertContains(asm, ".extern embed_oled_$name")
            assertContains(asm, "bl embed_oled_$name")
        }
    }

    @Test fun `OLED arguments require u32`() {
        for (call in listOf("oled_cursor(true, 0)", "oled_write_char(false)")) {
            val result = Frontend.analyze(program(call))
            assertFalse(result.isSuccess)
            assertTrue(result.diagnostics.any { it.code == "TYPE_MISMATCH" })
        }
    }

    @Test fun `OLED argument counts are checked`() {
        for (call in listOf("oled_init(1)", "oled_clear(1)", "oled_cursor(1)",
                            "oled_write_char()", "oled_update(1)")) {
            assertFalse(Frontend.analyze(program(call)).isSuccess)
        }
    }

    @Test fun `OLED bool and void results retain their types`() {
        assertFalse(Frontend.analyze(program("let x: u32 = oled_init()")).isSuccess)
        assertFalse(Frontend.analyze(program("let x: bool = oled_clear()")).isSuccess)
    }

    @Test fun `OLED builtin names are reserved`() {
        val result = Frontend.analyze("fn oled_init() -> bool { return true }\n" + program(""))
        assertTrue(result.diagnostics.any { it.code == "DUPLICATE_FUNCTION" })
    }

    @Test fun `string literals remain excluded`() {
        assertFalse(Frontend.analyze(program("oled_write_char(\"T\")")).isSuccess)
    }
}
