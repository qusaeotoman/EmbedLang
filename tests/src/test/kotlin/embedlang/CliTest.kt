package embedlang

import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.TimeUnit
import kotlin.test.*

class CliTest {
    @TempDir lateinit var directory: Path
    private data class Result(val code: Int, val stdout: String, val stderr: String)

    private fun source(text: String): String {
        val path = directory.resolve("program.emb")
        Files.writeString(path, text)
        return path.toString()
    }

    private fun run(vararg arguments: String): Result {
        val windows = System.getProperty("os.name").startsWith("Windows")
        val java = Path.of(System.getProperty("java.home"), "bin", if (windows) "java.exe" else "java").toString()
        val classpath = checkNotNull(System.getProperty("embedlang.cli.classpath"))
        val process = ProcessBuilder(listOf(java, "-cp", classpath, "embedlang.MainKt") + arguments).start()
        try {
            assertTrue(process.waitFor(20, TimeUnit.SECONDS), "CLI did not finish")
            return Result(process.exitValue(), process.inputStream.bufferedReader().readText().replace("\r\n", "\n"),
                process.errorStream.bufferedReader().readText().replace("\r\n", "\n"))
        } finally {
            process.destroyForcibly()
        }
    }

    @Test fun `emit ir prints only typed IR`() {
        val result = run("--emit-ir", source("fn main() -> void { delay_ms(500) }"))
        assertEquals(0, result.code, result.stderr)
        assertEquals("func @main() -> void {\n  call builtin @delay_ms(500:u32):void\n}\n", result.stdout)
        assertEquals("", result.stderr)
    }
    @Test fun `emit asm prints assembly text`() {
        val result = run("--emit-asm", source("fn main() -> void { gpio_toggle(LED_GREEN) }"))
        assertEquals(0, result.code, result.stderr)
        assertTrue(result.stdout.startsWith(".syntax unified\n.cpu cortex-m4\n.thumb"))
        assertContains(result.stdout, "bl embed_gpio_toggle")
        assertFalse(result.stdout.contains("OK:"))
        assertEquals("", result.stderr)
    }
    @Test fun `emit asm errors produce no partial assembly`() {
        for (text in listOf("fn main() -> void { missing() }", "fn main() -> void { @ }")) {
            val result = run("--emit-asm", source(text))
            assertEquals(1, result.code)
            assertEquals("", result.stdout)
            assertContains(result.stderr, "error [")
        }
        assertEquals(2, run("--emit-asm").code)
        assertEquals(2, run("--emit-asm", directory.resolve("missing.emb").toString()).code)
    }
    @Test fun `emit ir reports errors without partial IR`() {
        for (text in listOf("fn main() -> void { missing() }", "fn main() -> void { @ }")) {
            val result = run("--emit-ir", source(text))
            assertEquals(1, result.code)
            assertEquals("", result.stdout)
            assertContains(result.stderr, "error [")
            assertContains(result.stderr, "program.emb:1:")
        }
    }
    @Test fun `normal validation mode preserved`() {
        val path = source("fn main() -> void {}")
        val result = run(path)
        assertEquals(0, result.code)
        assertEquals("OK: $path (1 functions checked)\n", result.stdout)
        assertEquals("", result.stderr)
    }
    @Test fun `help malformed options and missing files keep correct exit codes`() {
        val help = run("--help")
        assertEquals(0, help.code)
        assertContains(help.stdout, "[--emit-ir]")
        assertEquals(2, run().code)
        assertEquals(2, run("--emit-ir").code)
        assertEquals(2, run("--unknown").code)
        assertEquals(2, run("--emit-ir", directory.resolve("missing.emb").toString()).code)
    }
}
