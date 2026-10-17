.syntax unified
.cpu cortex-m4
.thumb
.text
.extern embed_const_LED_GREEN
.extern embed_gpio_write
.extern embed_millis

.balign 2
.global main
.type main, %function
.thumb_func
main:
    push {r7, lr}
    movs r12, #24
    sub.w sp, sp, r12
    mov r7, sp
    movs r0, #10
    str.w r0, [r7, #16]
    movs r0, #20
    str.w r0, [r7, #20]
    ldr.w r0, [r7, #16]
    ldr.w r1, [r7, #20]
    bl embed_fn_add
    str.w r0, [r7, #0]
    ldr.w r0, [r7, #0]
    str.w r0, [r7, #16]
    movs r0, #30
    ldr.w r1, [r7, #16]
    cmp r1, r0
    mov.w r0, #0
    it ge
    movge.w r0, #1
    cmp r0, #0
    beq.w .Lbool_end_1
    movs r0, #0
    cmp r0, #0
    mov.w r0, #0
    it eq
    moveq.w r0, #1
.Lbool_end_1:
    str.w r0, [r7, #4]
    movs r0, #255
    str.w r0, [r7, #8]
    bl embed_millis
    str.w r0, [r7, #12]
    ldr.w r0, [r7, #4]
    cmp r0, #0
    mov.w r0, #0
    it ne
    movne.w r0, #1
    cmp r0, #0
    beq.w .Lelse_2
    ldr.w r0, [r7, #0]
    str.w r0, [r7, #16]
    movs r0, #1
    ldr.w r1, [r7, #16]
    add.w r0, r1, r0
    str.w r0, [r7, #0]
    b.w .Lif_end_3
.Lelse_2:
    movs r0, #0
    str.w r0, [r7, #0]
.Lif_end_3:
.Lwhile_start_4:
    ldr.w r0, [r7, #0]
    str.w r0, [r7, #16]
    movs r0, #0
    ldr.w r1, [r7, #16]
    cmp r1, r0
    mov.w r0, #0
    it gt
    movgt.w r0, #1
    cmp r0, #0
    beq.w .Lwhile_end_5
    ldr.w r0, [r7, #0]
    str.w r0, [r7, #16]
    movs r0, #1
    ldr.w r1, [r7, #16]
    sub.w r0, r1, r0
    str.w r0, [r7, #0]
    b.w .Lwhile_start_4
.Lwhile_end_5:
    movw r0, #:lower16:embed_const_LED_GREEN
    movt r0, #:upper16:embed_const_LED_GREEN
    ldr r0, [r0]
    str.w r0, [r7, #16]
    movs r0, #1
    str.w r0, [r7, #20]
    ldr.w r0, [r7, #16]
    ldr.w r1, [r7, #20]
    bl embed_gpio_write
    b.w .Lreturn_0
.Lreturn_0:
    mov sp, r7
    movs r12, #24
    add.w sp, sp, r12
    pop {r7, pc}
.size main, .-main

.balign 2
.global embed_fn_add
.type embed_fn_add, %function
.thumb_func
embed_fn_add:
    push {r7, lr}
    movs r12, #16
    sub.w sp, sp, r12
    mov r7, sp
    str.w r0, [r7, #0]
    str.w r1, [r7, #4]
    ldr.w r0, [r7, #0]
    str.w r0, [r7, #8]
    ldr.w r0, [r7, #4]
    ldr.w r1, [r7, #8]
    add.w r0, r1, r0
    b.w .Lreturn_6
.Lreturn_6:
    mov sp, r7
    movs r12, #16
    add.w sp, sp, r12
    pop {r7, pc}
.size embed_fn_add, .-embed_fn_add

.section .note.GNU-stack,"",%progbits
