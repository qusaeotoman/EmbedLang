(identifier) @variable
(comment) @comment
(integer) @number
(boolean) @boolean
(type) @type.builtin
["fn" "let" "if" "else" "while" "return"] @keyword
["+" "-" "*" "/" "%" "==" "!=" "<" ">" "<=" ">=" "&&" "||" "!" "=" "->"] @operator
["(" ")" "{" "}"] @punctuation.bracket
["," ":" ";"] @punctuation.delimiter
(function_declaration name: (identifier) @function)
(call_expression function: (identifier) @function)
(parameter name: (identifier) @variable.parameter)
((identifier) @constant.builtin
  (#match? @constant.builtin "^(INPUT|OUTPUT|HIGH|LOW|LED_GREEN|LED_YELLOW|LED_RED|BUTTON_1)$"))
((call_expression function: (identifier) @function.builtin)
  (#match? @function.builtin "^(gpio_mode|gpio_write|gpio_read|gpio_toggle|delay_ms|millis|oled_init|oled_clear|oled_cursor|oled_write_char|oled_update)$"))
