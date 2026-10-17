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
    val emitAsm = args.size == 2 && args[0] == "--emit-asm"
    if (!(args.size == 1 && !args[0].startsWith("-")) && !emitIr && !emitAsm) {
        printUsage()
        exitProcess(2)
    }
    val sourceArgument = if (emitIr || emitAsm) args[1] else args[0]
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
        val result = Frontend.lower(source, path.toString())
        if (!result.isSuccess) {
            result.diagnostics.forEach { System.err.println(it) }
            exitProcess(1)
        }
        print(if (emitAsm) ArmBackend.emit(result.ir!!) else IrPrinter.print(result.ir!!))
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
    println("Checks source or emits typed IR / Thumb-2 assembly text. No firmware image is emitted.")
}
