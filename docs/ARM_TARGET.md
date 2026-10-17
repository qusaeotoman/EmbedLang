# Intended hardware target

| Property | Target |
| --- | --- |
| Microcontroller | STM32F407VGT6 |
| CPU core | ARM Cortex-M4 |
| Architecture | ARMv7E-M |
| Instruction set | Thumb / Thumb-2 (16-bit and 32-bit instruction encodings) |

ST lists STM32F407VGT6 in the STM32F407VG family, based on Cortex-M4.
See [STMicroelectronics product documentation](https://www.st.com/en/microcontrollers-microprocessors/stm32f407vg.html).
Arm documents Cortex-M4 as ARMv7E-M with Thumb/Thumb-2 support; see
[Arm Cortex-M4 product support](https://support.arm.com/compute-ip/cortex-m4).

`embedlang.backend.arm.ArmTarget` records these identifiers. Milestone 3 emits
human-readable Thumb-2 assembly through `ArmBackend`; it does not emit object
files or firmware images. See `ARM_BACKEND.md`.
The IR carries exact integer/bool types, local identities, calls, and structured
control flow consumed by the assembly backend.

The assembly backend specifies instruction selection, scalar calling conventions,
signed/unsigned operations, and stack layout. Milestone 4A's separate firmware
layer supplies official startup/vector code, the cLAB RAM linker layout, and
board-specific HAL runtime bindings. See `STM32_RUNTIME.md` and `ITMO_CLAB.md`.
No LED/button pin numbers are assumed from the microcontroller model alone.
The hardware's optional capabilities do not add floating-point types or any
other unsupported construct to EmbedLang v0.1.
