grammar EmbedLang;

program : separators* (functionDecl separators*)* EOF;
functionDecl : FN IDENT LPAREN parameterList? RPAREN ARROW type block;
parameterList : parameter (COMMA parameter)*;
parameter : IDENT COLON type;
type : I32 | U32 | U8 | BOOL | VOID;
block : LBRACE separators* (statement separators*)* RBRACE;

statement
    : LET IDENT COLON type ASSIGN expression terminator  # letStatement
    | IDENT ASSIGN expression terminator                # assignmentStatement
    | IF expression block (separators* ELSE block)?      # ifStatement
    | WHILE expression block                            # whileStatement
    | RETURN expression? terminator                     # returnStatement
    | call terminator                                   # callStatement
    ;

// Newlines delimit simple statements. A final statement can end at a brace.
terminator : separators+ | { _input.LA(1) == RBRACE }?;
separators : NEWLINE | SEMI;
expression : logicalOr;
logicalOr : logicalAnd (OR logicalAnd)*;
logicalAnd : equality (AND equality)*;
equality : comparison ((EQ | NE) comparison)*;
comparison : additive ((LT | GT | LE | GE) additive)*;
additive : multiplicative ((PLUS | MINUS) multiplicative)*;
multiplicative : unary ((STAR | SLASH | PERCENT) unary)*;
unary : (NOT | MINUS | PLUS) unary | primary;
primary : INTEGER | TRUE | FALSE | call | IDENT | LPAREN expression RPAREN;
call : IDENT LPAREN argumentList? RPAREN;
argumentList : expression (COMMA expression)*;

FN: 'fn';
LET: 'let';
IF: 'if';
ELSE: 'else';
WHILE: 'while';
RETURN: 'return';
I32: 'i32';
U32: 'u32';
U8: 'u8';
BOOL: 'bool';
VOID: 'void';
TRUE: 'true';
FALSE: 'false';
ARROW: '->';
OR: '||';
AND: '&&';
EQ: '==';
NE: '!=';
LE: '<=';
GE: '>=';
LT: '<';
GT: '>';
NOT: '!';
PLUS: '+';
MINUS: '-';
STAR: '*';
SLASH: '/';
PERCENT: '%';
ASSIGN: '=';
LPAREN: '(';
RPAREN: ')';
LBRACE: '{';
RBRACE: '}';
COLON: ':';
COMMA: ',';
SEMI: ';';
INTEGER: [0-9]+;
IDENT: [a-zA-Z_] [a-zA-Z_0-9]*;
LINE_COMMENT: '//' ~[\r\n]* -> skip;
WS: [ \t]+ -> skip;
NEWLINE: '\r'? '\n';
