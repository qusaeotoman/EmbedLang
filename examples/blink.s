.syntax unified
.cpu cortex-m4
.thumb
.text
.extern embed_const_LED_GREEN
.extern embed_const_OUTPUT
.extern embed_delay_ms
.extern embed_gpio_mode
.extern embed_gpio_toggle

.balign 2
.global main
.type main, %function
.thumb_func
main:
    push {r7, lr}
    movs r12, #8
    sub.w sp, sp, r12
    mov r7, sp
    movw r0, #:lower16:embed_const_LED_GREEN
    movt r0, #:upper16:embed_const_LED_GREEN
    ldr r0, [r0]
    str.w r0, [r7, #0]
    movw r0, #:lower16:embed_const_OUTPUT
    movt r0, #:upper16:embed_const_OUTPUT
    ldr r0, [r0]
    str.w r0, [r7, #4]
    ldr.w r0, [r7, #0]
    ldr.w r1, [r7, #4]
    bl embed_gpio_mode
.Lwhile_start_1:
    movs r0, #1
    cmp r0, #0
    beq.w .Lwhile_end_2
    movw r0, #:lower16:embed_const_LED_GREEN
    movt r0, #:upper16:embed_const_LED_GREEN
    ldr r0, [r0]
    str.w r0, [r7, #0]
    ldr.w r0, [r7, #0]
    bl embed_gpio_toggle
    movw r0, #500
    str.w r0, [r7, #0]
    ldr.w r0, [r7, #0]
    bl embed_delay_ms
    b.w .Lwhile_start_1
.Lwhile_end_2:
.Lreturn_0:
    mov sp, r7
    movs r12, #8
    add.w sp, sp, r12
    pop {r7, pc}
.size main, .-main

.section .note.GNU-stack,"",%progbits
