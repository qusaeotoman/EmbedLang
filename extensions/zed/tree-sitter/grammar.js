// Editor parser only. ANTLR remains the language authority and compiler parser.
module.exports = grammar({
  name: 'embedlang',
  extras: $ => [/[ \t\r]/, $.comment],
  word: $ => $.identifier,
  conflicts: $ => [[$.if_statement]],
  rules: {
    source_file: $ => repeat(choice($.function_declaration, $._separator)),
    _separator: _ => choice('\n', ';'),
    function_declaration: $ => seq('fn', field('name', $.identifier), '(',
      optional(seq($.parameter, repeat(seq(',', $.parameter)))), ')', '->', $.type, $.block),
    parameter: $ => seq(field('name', $.identifier), ':', $.type),
    type: _ => choice('i32', 'u32', 'u8', 'bool', 'void'),
    block: $ => seq('{', repeat(choice($._statement, $._separator)), '}'),
    // Tolerate missing terminators while editing. CLI validation enforces them.
    _statement: $ => choice($.declaration, $.assignment, $.return_statement,
      $.call_expression, $.if_statement, $.while_statement),
    declaration: $ => seq('let', field('name', $.identifier), ':', $.type, '=', $._expression),
    assignment: $ => seq(field('name', $.identifier), '=', $._expression),
    return_statement: $ => prec.right(seq('return', optional($._expression))),
    if_statement: $ => seq('if', $._expression, $.block,
      optional(seq(repeat($._separator), 'else', $.block))),
    while_statement: $ => seq('while', $._expression, $.block),
    _expression: $ => choice($.integer, $.boolean, $.identifier, $.call_expression,
      $.unary_expression, $.binary_expression, $.parenthesized_expression),
    parenthesized_expression: $ => seq('(', $._expression, ')'),
    call_expression: $ => seq(field('function', $.identifier), '(',
      optional(seq($._expression, repeat(seq(',', $._expression)))), ')'),
    unary_expression: $ => prec(7, seq(choice('!', '-', '+'), $._expression)),
    binary_expression: $ => choice(...[
      [1, ['||']], [2, ['&&']], [3, ['==', '!=']], [4, ['<', '>', '<=', '>=']],
      [5, ['+', '-']], [6, ['*', '/', '%']]
    ].map(([precedence, operators]) => prec.left(precedence,
      seq(field('left', $._expression), field('operator', operators.length === 1 ? operators[0] : choice(...operators)), field('right', $._expression))))),
    identifier: _ => /[a-zA-Z_][a-zA-Z_0-9]*/,
    integer: _ => /[0-9]+/,
    boolean: _ => choice('true', 'false'),
    comment: _ => token(seq('//', /[^\r\n]*/))
  }
});
