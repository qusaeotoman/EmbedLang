# Milestone 2: typed Intermediate Representation

## Design and boundary

```text
Source → ANTLR parse tree → AST → semantic analysis → IR → future ARM backend
```

The IR is a small, target-independent tree with structured blocks. Unlike the
syntax AST, it has resolved expression types, local identities, normalized
integer values, and function symbols. It is not SSA, three-address code, machine
instructions, or executable bytecode. No language rules change in this milestone.

The semantic analyzer records types as it performs its existing checks. Its
diagnostics-only API remains available. `TypedAnalysisResult` binds the exact AST
to an identity-keyed, read-only type table. `IrLowerer.lower(analysis)` requires
successful analysis; `Frontend.lower(source, file)` handles errors before invoking
it. Invalid programs never produce partial IR.

## Nodes and invariants of generated IR

| Node | Meaning |
| --- | --- |
| `IrProgram`, `IrFunction`, `IrBlock` | Ordered functions, parameter locals, structured statements |
| `IrLocal` | ID, source name, exact type, declaration location |
| `IrIntegerConstant` | Resolved integer type and exact `Long` value |
| `IrBooleanConstant` | `bool` value |
| `IrBuiltinConstant` | Symbolic constant name and type |
| `IrLocalRead` | Bound local identity; type comes from that local |
| `IrUnary`, `IrBinary` | Explicit operator, ordered operands, resolved result type |
| `IrCall` | Resolved function signature, arguments, result type, built-in marker |
| `IrLocalDeclaration`, `IrAssignment` | Initialize/store into a specific local |
| `IrCallStatement`, `IrReturn` | Discarded call result; optional return value |
| `IrIf`, `IrWhile` | Boolean condition and nested blocks |

Every expression has a concrete v0.1 type. A void call is valid as a statement;
it cannot become a local value. Integer constants fit their analyzed types. A
host `Long` represents all valid i32/u32/u8 constants, including `4294967295`.
Signed literal chains normalize as a whole, allowing `-2147483648` without an
out-of-range positive intermediate. General arithmetic is not constant-folded.

IDs start at zero in each function: parameters first, then declarations in source
traversal order. Shadowed locals have distinct IDs. Initializers resolve before
the new binding is introduced. Function symbols are registered before lowering
bodies, so forward calls and recursion refer to resolved signatures.

All IR nodes retain source locations. Shared `Type` and `SourceLocation` values
remain in `embedlang.ast` to avoid moving the existing frontend's public types.
IR operators have their own enums and printable mnemonics.

## Behavior preserved and deferred

Statement order, expression operand order/grouping, calls within expressions,
and branch/loop nesting are retained. A while condition stays inside its loop,
so lowering never hoists a `millis()` or `gpio_read()` call. Empty else blocks
remain distinct from absent else blocks. Explicit return and void fallthrough
are preserved; no synthetic return is inserted. Unreachable code remains in IR.

`and` and `or` nodes retain their expression operands. This printer/lowering
stage does not execute them or settle short-circuit execution semantics that
v0.1 explicitly defers. Arithmetic overflow, division-by-zero behavior, calling
conventions, register allocation, stack layout, and hardware mapping are likewise
deferred. Built-in pin/mode constants and HIGH/LOW stay symbolic; the backend will
eventually provide their runtime values.

## Textual format

```text
func @main() -> void {
  local %count.0:i32 = 10:i32
  store %count.0:i32 <- add(%count.0:i32, 1:i32):i32
  if gt(%count.0:i32, 0:i32):bool {
    call builtin @gpio_write($LED_GREEN:u32, $HIGH:bool):void
  }
  return
}
```

- `@name` is a function; `call builtin` identifies a built-in signature.
- `%name.id:type` is a resolved parameter/local, not a register or address.
- `$NAME:type` is a symbolic built-in constant.
- `value:type` is a typed constant. Operations print their result type.
- `local` introduces a local; `store` assigns to it.
- `if`, `else`, and `while` enclose structured blocks.

Arithmetic mnemonics are `add`, `sub`, `mul`, `div`, `mod`; comparisons are
`eq`, `ne`, `lt`, `gt`, `le`, `ge`; boolean operations are `and`, `or`, `not`;
unary numeric operations are `neg`, `pos`. Output uses two-space indentation and
LF newlines, with deterministic IDs and source function order. It is a debugging
format, not a serialization protocol or accepted EmbedLang source.

## CLI and tests

Use `embedlang --emit-ir program.emb` after installing the distribution (see
README). Without `--emit-ir`, the original validation mode remains available.
Failures print source-located diagnostics to stderr with exit code 1; usage and
file-reading failures use 2. Successful emission prints only IR to stdout.

Tests cover exact types and integer boundaries, all operations, bound assignments,
shadowing, parameters, forward/recursive calls, branches, loops with effectful
conditions, void return/fallthrough, symbolic built-ins, diagnostic gating,
source locations, deterministic printing, and actual CLI behavior. Golden output
for both examples lives under `tests/src/test/resources/ir/`.
