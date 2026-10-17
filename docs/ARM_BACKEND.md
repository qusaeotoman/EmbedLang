# Milestone 3: ARM Thumb-2 assembly backend

The backend consumes the existing typed structured IR and emits GNU assembler
text for STM32F407VGT6 / Cortex-M4 / ARMv7E-M / Thumb-2. The frontend, AST,
semantic rules, and IR are unchanged. This is not a firmware build: startup,
vector tables, linker scripts, runtime bodies, binary emission, flashing,
debugger integration, and editor plugins remain outside this milestone.

Milestone 4A now provides startup, linking and runtime separately in `firmware/`;
see [STM32_RUNTIME.md](STM32_RUNTIME.md). The assembly emitter is unchanged.

## Entry point and output

```sh
embedlang --emit-asm program.emb
```

`ArmBackend.emit(IrProgram)` returns assembly as a string. The CLI lowers only
successfully checked source and emits no partial assembly on frontend errors.
`--emit-ir` and ordinary validation keep their existing behavior. Output uses
`.syntax unified`, `.cpu cortex-m4`, `.thumb`, and `.text`; functions use
`.global`, `.type`, `.thumb_func`, and `.size` directives.

`main` retains its name. Other user functions become `embed_fn_<name>` and
built-ins become `embed_<name>`, preventing collisions between user and runtime
names. Labels are globally unique within an emitted file and deterministic.

## Registers and calling convention

| Register | Use |
| --- | --- |
| `r0` | Expression result, first argument, scalar return value |
| `r1` | Saved left operand after evaluating the right operand; second argument |
| `r2` | Quotient scratch for remainder; third argument |
| `r3` | Fourth argument |
| `r7` | Stable frame base; saved/restored |
| `r12` | Address/stack-adjustment scratch; never live across a call |
| `sp`, `lr` | Stack pointer and return address |

The backend implements the scalar subset of
[AAPCS32](https://github.com/ARM-software/abi-aa/blob/main/aapcs32/aapcs32.rst):
first four arguments in `r0`–`r3`, later arguments in ascending words starting
at the caller's `sp`, and results in `r0`. There are no aggregate, floating-point,
variadic, or 64-bit values. Calls may clobber `r0`–`r3`, `r12`, flags, and `lr`.
No live temporary depends on these registers surviving a call. Untouched
callee-saved registers stay untouched; `r7` and `lr` are saved by the prologue.
The stack is 8-byte aligned on entry and at every call, including recursion.

Arguments are evaluated left to right into distinct frame slots before loading
argument registers. Nested calls cannot overwrite earlier arguments. Additional
arguments use a temporary, 8-byte-rounded outgoing stack area, reclaimed after
`bl`. Incoming stack arguments are read above the local frame and saved-register
area. Register parameters are spilled before incoming stack arguments use `r0`.

## Stack frames and locals

Each parameter/local occupies a four-byte frame slot, including `u8` and `bool`.
IR local IDs resolve shadowed bindings to separate slots. A traversal collects
locals first; expression emission tracks maximum simultaneously live temporary
slots. Frame size is `(locals + peak temporaries) * 4`, rounded up to 8 bytes.

The prologue pushes `{r7, lr}`, allocates the frame, and sets `r7 = sp`.
Positive offsets from `r7` address slots, even when outgoing arguments adjust
`sp`. All explicit returns branch to one epilogue, which restores `sp`, frees
the frame, and pops `{r7, pc}`. Void fallthrough reaches the same epilogue.
No unwinding metadata or stack-overflow checking is emitted.

Loads/stores use immediate offsets through 4095, and computed `r12` addresses
for larger offsets. Stack adjustments use a materialized size in `r12`.
Constants use `movs` or `movw`/`movt`; no distance-sensitive literal pools exist.
This simple strategy favors correctness and readability over efficient code.

## IR to instructions

| IR operation | Assembly strategy |
| --- | --- |
| Integer/bool constant | Materialize exact 32-bit pattern / 0 or 1 in `r0` |
| Local read / declaration / assignment | `ldr` / `str` on its bound frame slot |
| `+`, `-`, `*` | Save LHS in frame, evaluate RHS, restore LHS in `r1`; `add`, `sub`, `mul` |
| `/` | `sdiv` for i32; `udiv` for u32/u8 |
| `%` | Divide into `r2`, then `mls` computes dividend − quotient × divisor |
| Equality / ordering | `cmp`, zero result, one-instruction IT block sets result to 1 |
| `!` / unary `-` / unary `+` | Zero comparison / `rsb` from zero / preserve value |
| `&&`, `||` | Conditional branch around RHS; operands/results are canonical bool |
| Call | Stage arguments, populate ABI locations, `bl`, reclaim outgoing stack |
| Return | Evaluate optional value into `r0`, branch to shared epilogue |
| If/else | Condition, `cmp`, conditional branch, else/end labels |
| While | Start label, reevaluated condition, exit branch, body, backward branch |

Signed comparisons use `lt`, `gt`, `le`, `ge`; unsigned comparisons use `lo`,
`hi`, `ls`, `hs`. Equality uses `eq`/`ne` independently of signedness.
Wide branches avoid narrow Thumb branch-distance limits. There is no optimizer,
SSA conversion, register allocator, or change to IR representation.

## Backend execution policies

Version 0.1 left runtime behavior deferred. The policies below are explicitly
chosen for this target backend; they do not silently alter `LANGUAGE_SPEC.md`:

- Integers wrap at their declared width. i32/u32 naturally retain the low 32 bits;
  u8 arithmetic results use `uxtb` at each typed expression boundary, not just stores.
- Signed division truncates toward zero; remainder is dividend minus quotient
  times divisor. No software division-by-zero check is generated. Cortex-M4's
  divide behavior depends on the runtime's DIV_0_TRP configuration, which is
  outside this milestone. Signed minimum divided by -1 follows hardware behavior.
- `&&` and `||` short-circuit. Non-short-circuit arithmetic/comparison operands
  and call arguments evaluate left to right. Calls within loop conditions remain
  inside the loop and execute on each condition evaluation.
- bool values are canonicalized to 0/1; u8 call results are zero-extended with
  `uxtb`. There are no implicit language-level numeric conversions.

## External runtime contract

Calls reference `embed_gpio_mode`, `embed_gpio_write`, `embed_gpio_read`,
`embed_gpio_toggle`, `embed_delay_ms`, and `embed_millis`. Only referenced symbols
receive `.extern` declarations. Their implementations must follow the scalar
calling convention above; this backend does not define their STM32 bodies.

`HIGH` and `LOW` materialize logical true/false. Pin and mode values remain
unspecified: `INPUT`, `OUTPUT`, `LED_GREEN`, `LED_YELLOW`, `LED_RED`, and `BUTTON_1`
load from external **32-bit data objects** named `embed_const_<NAME>`.
`movw`/`movt` address relocations followed by `ldr` load their values; these symbols
must not be supplied as absolute assembler equates. No board pin numbers are
invented by the backend. Milestone 4A supplies these data objects using the
official SDK-1.1M mappings in a separate runtime.

GNU syntax/directives follow the
[GNU assembler ARM documentation](https://sourceware.org/binutils/docs/as/ARM-Directives.html).
The checked-in `examples/basic.s` and `examples/blink.s` are generated text.
Tests cover instruction selection, typed comparisons, narrowing, bindings,
short-circuit branches, loops, nested calls, stack arguments, recursion, large
frames, external symbols, deterministic examples, and CLI error gating.

## Validation

The complete Gradle suite passes 76 JUnit tests, including the previous 57.
GNU ARM assembler accepted both generated example files. The optional
`tests/arm_execution.py` harness additionally assembles/links a self-contained
test fixture and executes 15 checks under Unicorn Cortex-M4 emulation. It checks
actual results plus stack and r7 restoration, including recursive/nested calls,
six arguments, loops, signed/unsigned divide/remainder, byte wrapping, boolean
normalization, and short-circuiting an otherwise infinite function. Tooling is
test-only: no firmware/linker script/startup code is added. See README for usage.
