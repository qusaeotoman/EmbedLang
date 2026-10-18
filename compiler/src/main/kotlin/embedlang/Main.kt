package embedlang

import embedlang.frontend.Frontend
import embedlang.ir.IrPrinter
import embedlang.backend.arm.ArmBackend
import java.nio.file.Files
import java.nio.file.Path
import kotlin.system.exitProcess

fun main(args: Array<String>) {
    if (args.size == 1 && args[0] in listOf("--help", "-h")) {
        printUsage()
        return
    }
    val emitIr = args.size == 2 && args[0] == "--emit-ir"
    val debugLines = args.size == 3 && args[0] == "--emit-asm" && args[1] == "--debug-lines"
    val emitAsm = (args.size == 2 && args[0] == "--emit-asm") || debugLines
    if (!(args.size == 1 && !args[0].startsWith("-")) && !emitIr && !emitAsm) {
        printUsage()
        exitProcess(2)
    }
    val sourceArgument = if (debugLines) args[2] else if (emitIr || emitAsm) args[1] else args[0]
    val path = try {
        Path.of(sourceArgument)
    } catch (exception: java.nio.file.InvalidPathException) {
        System.err.println("Invalid source path: ${exception.message}")
        exitProcess(2)
    }
    val source = try {
        Files.readString(path)
    } catch (exception: java.io.IOException) {
        System.err.println("$path: Cannot read source: ${exception.message}")
        exitProcess(2)
    }
    if (emitIr || emitAsm) {
        // Debug paths resolve from the invocation cwd, not the assembler's cwd.
        // Use platform separators only: a literal POSIX backslash is a filename character.
        val sourceFile = if (debugLines) path.toAbsolutePath().normalize().toString()
            .replace(java.io.File.separatorChar, '/') else path.toString()
        val result = Frontend.lower(source, sourceFile)
        if (!result.isSuccess) {
            result.diagnostics.forEach { System.err.println(it) }
            exitProcess(1)
        }
        print(if (emitAsm) ArmBackend.emit(result.ir!!, debugLines) else IrPrinter.print(result.ir!!))
        return
    }
    val result = Frontend.analyze(source, path.toString())
    if (!result.isSuccess) {
        result.diagnostics.forEach { System.err.println(it) }
        exitProcess(1)
    }
    println("OK: $path (${result.program!!.functions.size} functions checked)")
}

private fun printUsage() {
    println("Usage: embedlang [--emit-ir] <source.emb>")
    println("       embedlang --emit-asm <source.emb>")
    println("       embedlang --emit-asm --debug-lines <source.emb>")
    println("Checks source or emits typed IR / Thumb-2 assembly text. No firmware image is emitted.")
}
