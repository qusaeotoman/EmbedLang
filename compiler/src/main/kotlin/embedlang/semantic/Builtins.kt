package embedlang.semantic

import embedlang.ast.Type

data class FunctionSignature(val parameterTypes: List<Type>, val returnType: Type)

/** Typed runtime ABI. Each firmware profile supplies its supported implementations. */
object Builtins {
    val functions: Map<String, FunctionSignature> = mapOf(
        "gpio_mode" to FunctionSignature(listOf(Type.U32, Type.U32), Type.VOID),
        "gpio_write" to FunctionSignature(listOf(Type.U32, Type.BOOL), Type.VOID),
        "gpio_read" to FunctionSignature(listOf(Type.U32), Type.BOOL),
        "gpio_toggle" to FunctionSignature(listOf(Type.U32), Type.VOID),
        "delay_ms" to FunctionSignature(listOf(Type.U32), Type.VOID),
        "millis" to FunctionSignature(emptyList(), Type.U32),
        "oled_init" to FunctionSignature(emptyList(), Type.BOOL),
        "oled_clear" to FunctionSignature(emptyList(), Type.VOID),
        "oled_cursor" to FunctionSignature(listOf(Type.U32, Type.U32), Type.BOOL),
        "oled_write_char" to FunctionSignature(listOf(Type.U32), Type.BOOL),
        "oled_update" to FunctionSignature(emptyList(), Type.BOOL),
    )
    val constants: Map<String, Type> = mapOf(
        "INPUT" to Type.U32, "OUTPUT" to Type.U32,
        "HIGH" to Type.BOOL, "LOW" to Type.BOOL,
        "LED_GREEN" to Type.U32, "LED_YELLOW" to Type.U32, "LED_RED" to Type.U32,
        "BUTTON_1" to Type.U32,
    )
}
