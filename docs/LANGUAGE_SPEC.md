# EmbedLang language specification — v0.1

## Program and syntax

A UTF-8 source file contains only function declarations, with mandatory entry
point `fn main() -> void`. No global variables or modules exist. Functions are
visible throughout the file, so forward calls and recursion are permitted.

```text
fn add(a: i32, b: i32) -> i32 {
    return a + b
}
fn main() -> void {
    let x: i32 = add(1, 2)
    x = x + 1
}
```

Names are case-sensitive ASCII identifiers: `[a-zA-Z_][a-zA-Z_0-9]*`. Keywords
are reserved. Decimal integer literals contain digits only. `true` and `false`
are boolean literals. `//` starts a comment through the end of the line.
Spaces and tabs are ignored; LF and CRLF delimit simple statements.

Simple statements (declarations, assignments, calls, returns) must end with a
newline or `;`, or immediately precede `}`. Blank lines and extra semicolons are
allowed. Expressions and function headers occupy one line; blocks may span
lines. The opening brace follows the condition/function header on the same line.
`else` may follow `}` on the same line or after separators. Parentheses are
optional around conditions. There is no automatic multiline expression joining.

## Types

| Type | Meaning | Literal range |
| --- | --- | --- |
| `i32` | Signed 32-bit integer | -2147483648 .. 2147483647 |
| `u32` | Unsigned 32-bit integer | 0 .. 4294967295 |
| `u8` | Unsigned 8-bit integer | 0 .. 255 |
| `bool` | Boolean | `true`, `false` |
| `void` | No result | No values |

Variables and parameters cannot be `void`. All declarations require an explicit
type and initializer. `let` creates a mutable local. Types do not implicitly
convert: `u8`, `u32`, and `i32` remain distinct. There are no casts in v0.1.

Integer literals (including unary signed literals) take the numeric type required
by a declaration, assignment, return, or function parameter. Within arithmetic
or a comparison, a typed operand determines the literal type. Otherwise integers
default to `i32`. For example, `delay_ms(500)`, `let byte: u8 = 255`, and
`millis() > 1000` are valid. Negative unsigned literals and out-of-range literals
are errors. `-2147483648` is a valid `i32` literal. Negation of a named unsigned
value is an error. Literal range checking does not evaluate arithmetic expressions.

## Operators

Precedence from highest to lowest; binary operators associate left:

| Level | Operators | Operands/result |
| --- | --- | --- |
| Primary | Calls, parentheses, literals, names | Depends on expression |
| Unary | `!`, `-`, `+` | `!`: bool → bool; signs: integer → same type |
| Multiplicative | `*`, `/`, `%` | Matching integer types → same type |
| Additive | `+`, `-` | Matching integer types → same type |
| Ordering | `<`, `>`, `<=`, `>=` | Matching integer types → bool |
| Equality | `==`, `!=` | Matching integer types or bool → bool |
| Logical AND | `&&` | bool, bool → bool |
| Logical OR | `||` | bool, bool → bool |

Boolean operators require booleans; integers have no truthiness. Comparing
`void` results is invalid. Chained ordering such as `a < b < c` fails type
checking because `a < b` is bool. Expressions alone are not statements, except
function calls (whose result may be discarded).

## Scope and control flow

Function parameters and its outer body share a scope. Each if/else/while block
creates a child scope. Locals may shadow locals in an outer block. Same-scope
duplicates are errors. The initializer is checked before the newly declared
variable becomes visible. Built-in names and function names are reserved for
declarations; built-in constants cannot be assigned.

```text
if condition {
    // condition must be bool
} else {
}
while condition {
}
```

There is no `break`, `continue`, or `else if` shorthand (nest another `if` in an
else block). Assignment is a statement and targets a declared mutable variable.

Functions explicitly specify their result type. `return value` must match it;
`return` without a value is permitted only in a void function. Void functions may
finish without `return`. A non-void function must not fall through: a return,
an if/else whose branches both terminate, or a literal `while true` loop satisfies
this check. General loop conditions and constant conditions in `if` are treated
conservatively. Even unreachable statements are type-checked.

## Built-in interface

| Function | Signature |
| --- | --- |
| `gpio_mode` | `(pin: u32, mode: u32) -> void` |
| `gpio_write` | `(pin: u32, value: bool) -> void` |
| `gpio_read` | `(pin: u32) -> bool` |
| `gpio_toggle` | `(pin: u32) -> void` |
| `delay_ms` | `(ms: u32) -> void` |
| `millis` | `() -> u32` |

The local F427 OLED runtime adds the following reserved built-ins, using only
existing scalar types. These require the opt-in local `--oled` firmware build;
the cLAB runtime does not provide their implementations.

| Function | Signature |
| --- | --- |
| `oled_init` | `() -> bool` |
| `oled_clear` | `() -> void` |
| `oled_cursor` | `(x: u32, y: u32) -> bool` |
| `oled_write_char` | `(ascii: u32) -> bool` |
| `oled_update` | `() -> bool` |

Text is supplied as printable ASCII codes (32–126); string literals remain
excluded. See [OLED runtime semantics and limits](LOCAL_OLED.md). This is an
additive built-in API extension; the v0.1 grammar and type rules are unchanged.

| Constants | Type / intent |
| --- | --- |
| `INPUT`, `OUTPUT` | `u32` GPIO modes |
| `HIGH`, `LOW` | `bool` logical high/low |
| `LED_GREEN`, `LED_YELLOW`, `LED_RED`, `BUTTON_1` | `u32` symbolic board pins |

This milestone recognizes signatures and constant types only. It does not
implement hardware functions or assign board-specific numeric pin/mode values.

## Deferred and excluded behavior

The frontend emits no native code and does not run programs. Runtime arithmetic
overflow, division by zero, short-circuit execution, calling conventions, timing,
GPIO configuration, and physical pin mapping require a later runtime/backend
specification. No promises about executable behavior are made by this milestone.

Excluded: classes, objects, inheritance, generics, pointers, allocation,
garbage collection, strings, floating point, threads, exceptions, and modules.
