package embedlang

import embedlang.backend.arm.ArmBackend
import embedlang.frontend.Frontend
import org.junit.jupiter.api.Test
import kotlin.test.*

class DebugLinesTest {
    private fun lower(source: String, file: String = "original.emb") =
        Frontend.lower(source, file).also { assertTrue(it.isSuccess, it.diagnostics.toString()) }.ir!!

    @Test fun `optional debug mode changes only file and loc directives`() {
        val ir = lower("""
            fn main() -> void {
                let x: i32 = 6 * 7
                if x > 0 { x = x - 1 } else { x = 0 }
                while x > 0 { x = x - 1 }
            }
        """.trimIndent())
        val plain = ArmBackend.emit(ir)
        assertEquals(plain, ArmBackend.emit(ir, debugLines = false))
        assertFalse(plain.contains(".loc"))
        val mapped = ArmBackend.emit(ir, debugLines = true)
        assertEquals(plain, mapped.lineSequence()
            .filterNot { it.startsWith(".file ") || it.startsWith(".loc ") }.joinToString("\n"))
    }

    @Test fun `debug file is original source and C string escaped`() {
        val ir = lower("fn main() -> void { return }", "dir\\source \"name\"\t.emb")
        val asm = ArmBackend.emit(ir, debugLines = true)
        assertContains(asm, ".file 1 \"dir\\\\source \\\"name\\\"\\t.emb\"")
        assertEquals(1, asm.lineSequence().count { it.startsWith(".file ") })
    }

    @Test fun `statements retain source lines and one based columns`() {
        val ir = lower("// header\nfn main() -> void {\n    let x: i32 = 6\n    x = x * 7\n    return\n}")
        val asm = ArmBackend.emit(ir, debugLines = true)
        for (line in 3..5) assertContains(asm, ".loc 1 $line 5 is_stmt 1\n")
        assertFalse(asm.contains(".loc 1 1 ")) // comment has no instruction
        assertContains(asm, ".loc 1 2 1 is_stmt 0\n    push")
        assertContains(asm, ".loc 1 2 1 is_stmt 0 epilogue_begin")
    }

    @Test fun `loop condition mapping starts at the backedge target`() {
        val asm = ArmBackend.emit(lower("fn main() -> void {\n    while true { return }\n}"), debugLines = true)
        val start = Regex("\\.Lwhile_start_\\d+:").find(asm)!!
        assertTrue(asm.lastIndexOf(".loc 1 2 5 is_stmt 1", start.range.first) >= 0)
        assertTrue(asm.indexOf("movs r0, #1", start.range.last) > start.range.last)
        assertContains(asm, ".loc 1 2 5 is_stmt 0\n    b.w .Lwhile_start_")
    }

    @Test fun `UTF8 file names use lossless ASCII octal escapes`() {
        val asm = ArmBackend.emit(lower("fn main() -> void {}", "source_Ω.emb"), debugLines = true)
        assertContains(asm, ".file 1 \"source_\\316\\251.emb\"")
        assertTrue(asm.all { it.code < 128 })
    }
}
