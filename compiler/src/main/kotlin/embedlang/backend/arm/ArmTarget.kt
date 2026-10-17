package embedlang.backend.arm

/** Assembly target; startup, linking, and firmware generation are deferred. */
object ArmTarget {
    const val MICROCONTROLLER = "STM32F407VGT6"
    const val CORE = "ARM Cortex-M4"
    const val ARCHITECTURE = "ARMv7E-M"
    const val INSTRUCTION_SET = "Thumb / Thumb-2"
}
