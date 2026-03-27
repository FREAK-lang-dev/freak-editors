/// <reference types="tree-sitter-cli/dsl" />
// Tree-sitter grammar for the FREAK programming language
// Alternative-4 Edition

module.exports = grammar({
  name: "freak",

  extras: ($) => [/\s/, $.comment],

  word: ($) => $.identifier,

  conflicts: ($) => [
    [$.binary_expression, $.assignment],
    [$.binary_expression, $.compound_assignment],
    [$._expression, $.shape_literal],
    [$.if_statement, $.if_expression],
    [$._pattern, $.constructor_pattern],
    [$.call_expression, $._expression],
  ],

  rules: {
    source_file: ($) => repeat($._statement),

    _statement: ($) =>
      choice(
        $.function_declaration,
        $.launch_declaration,
        $.variable_declaration,
        $.fixed_variable_declaration,
        $.shape_declaration,
        $.doctrine_declaration,
        $.impl_block,
        $.route_declaration,
        $.use_import,
        $.extern_declaration,
        $.annotation,
        $.if_statement,
        $.when_statement,
        $.repeat_statement,
        $.training_arc,
        $.for_each_statement,
        $.eventually_block,
        $.trust_me_block,
        $.isekai_block,
        $.deus_ex_machina,
        $.foreshadow_declaration,
        $.payoff_statement,
        $.return_statement,
        $.say_statement,
        $.break_statement,
        $.continue_statement,
        $.test_block,
        $.expression_statement,
        $.block,
      ),

    // ---- Comments ----
    comment: ($) => token(seq("--", /.*/)),

    // ---- Blocks ----
    block: ($) => seq("{", repeat($._statement), choice("}", "done")),

    // ---- Annotations ----
    annotation: ($) =>
      prec.right(seq("@", field("name", $.identifier), optional($._statement))),

    // ---- Variable declarations ----
    variable_declaration: ($) =>
      seq(
        "pilot",
        field("name", $.identifier),
        optional(seq(":", field("type", $._type))),
        "=",
        field("value", $._expression),
      ),

    fixed_variable_declaration: ($) =>
      seq("fixed", "pilot", field("name", $.identifier),
        optional(seq(":", field("type", $._type))),
        "=", field("value", $._expression)),

    // ---- Functions ----
    function_declaration: ($) =>
      seq("task", field("name", $.identifier),
        "(", optional($.parameter_list), ")",
        optional(seq("->", field("return_type", $._type))),
        field("body", $.block)),

    launch_declaration: ($) =>
      seq("launch", "task", field("name", $.identifier),
        "(", optional($.parameter_list), ")",
        optional(seq("->", field("return_type", $._type))),
        field("body", $.block)),

    parameter_list: ($) => commaSep1($.parameter),

    parameter: ($) =>
      seq(
        optional(choice("lend", seq("lend", "mut"), "copy")),
        field("name", $.identifier),
        ":", field("type", $._type)),

    // ---- Shape (struct) ----
    shape_declaration: ($) =>
      seq("shape", field("name", $.type_identifier),
        optional($.generic_parameters),
        "{", repeat($.field_declaration), choice("}", "done")),

    field_declaration: ($) =>
      seq(field("name", $.identifier), ":", field("type", $._type)),

    // ---- Doctrine (trait) ----
    doctrine_declaration: ($) =>
      seq("doctrine", field("name", $.type_identifier),
        optional($.generic_parameters), field("body", $.block)),

    // ---- Impl ----
    impl_block: ($) =>
      seq("impl", field("type", $.type_identifier),
        optional(seq("for", field("target", $.type_identifier))),
        "{", repeat($.function_declaration), choice("}", "done")),

    // ---- Route (enum) ----
    route_declaration: ($) =>
      seq("route", field("name", $.type_identifier),
        "{", commaSep1($.route_variant), optional(","), choice("}", "done")),

    route_variant: ($) =>
      seq(field("name", $.type_identifier),
        optional(seq("{", commaSep1($.field_declaration), "}"))),

    // ---- Use import ----
    use_import: ($) =>
      seq("use", $.module_path),

    module_path: ($) =>
      seq($.identifier, repeat(seq("::", $.identifier)),
        optional(seq("::", "{", commaSep1($.identifier), "}"))),

    // ---- Extern ----
    extern_declaration: ($) =>
      seq("extern", "task", field("name", $.identifier),
        "(", optional($.parameter_list), ")",
        optional(seq("->", field("return_type", $._type)))),

    // ---- Control flow ----
    if_statement: ($) =>
      prec.right(seq("if", field("condition", $._expression),
        field("consequence", $.block),
        optional(seq("else", field("alternative", choice($.if_statement, $.block)))))),

    when_statement: ($) =>
      seq("when", field("subject", $._expression),
        "{", repeat($.when_arm), choice("}", "done")),

    when_arm: ($) =>
      prec.right(seq(field("pattern", $._pattern), "->",
        field("body", choice($.block, $._expression, $.return_statement, $.say_statement)))),

    _pattern: ($) =>
      choice(
        $.wildcard_pattern,
        $.constructor_pattern,
        $.number,
        $.string,
        $.boolean,
        $.identifier,
      ),

    wildcard_pattern: ($) => "_",

    constructor_pattern: ($) =>
      prec(1, seq(
        field("name", $.type_identifier),
        optional(seq("(", commaSep1($._pattern), ")")),
      )),

    // ---- Loops ----
    repeat_statement: ($) =>
      choice(
        seq("repeat", field("count", $._expression), "times", field("body", $.block)),
        seq("repeat", "until", field("condition", $._expression), field("body", $.block)),
        seq("repeat", field("body", $.block)),
      ),

    training_arc: ($) =>
      seq("training", "arc", field("name", $.identifier),
        optional(seq("from", field("from", $._expression), "to", field("to", $._expression))),
        field("body", $.block)),

    for_each_statement: ($) =>
      seq("for", "each", field("variable", $.identifier),
        "in", field("iterable", $._expression), field("body", $.block)),

    // ---- Special blocks ----
    eventually_block: ($) =>
      seq("eventually",
        optional(seq("if", field("condition", $._expression))),
        field("body", $.block)),

    trust_me_block: ($) =>
      seq("trust-me", optional(field("reason", $.string)), field("body", $.block)),

    isekai_block: ($) =>
      seq("isekai", field("body", $.block),
        optional(seq("bringing", "back", "{", commaSep1($.identifier), "}"))),

    deus_ex_machina: ($) =>
      seq("deus_ex_machina", field("monologue", $.string), field("body", $.block)),

    foreshadow_declaration: ($) =>
      seq("foreshadow", $.variable_declaration),

    payoff_statement: ($) => seq("payoff", field("name", $.identifier)),

    // ---- Statements ----
    return_statement: ($) =>
      prec.right(seq("give", "back", optional(field("value", $._expression)))),

    say_statement: ($) => prec.right(seq("say", field("value", $._expression))),

    break_statement: ($) => "break",
    continue_statement: ($) => "continue",

    expression_statement: ($) => prec(-1, $._expression),

    test_block: ($) =>
      seq("test", field("name", $.string), optional($.annotation), field("body", $.block)),

    // ---- Types ----
    _type: ($) =>
      choice($.primitive_type, $.type_identifier, $.generic_type,
        $.array_type, $.pointer_type),

    primitive_type: ($) =>
      choice("int", "uint", "num", "tiny", "bool", "word", "char",
        "void", "float", "float32", "big"),

    type_identifier: ($) => /[A-Z][a-zA-Z0-9_]*/,

    generic_type: ($) =>
      seq(field("name", choice($.type_identifier, $.identifier)),
        "<", commaSep1($._type), ">"),

    generic_parameters: ($) =>
      seq("<", commaSep1($.type_identifier), ">"),

    array_type: ($) =>
      seq("[", field("element", $._type), ";", field("size", $.number), "]"),

    pointer_type: ($) =>
      seq("*", optional("mut"), field("type", $._type)),

    // ---- Expressions ----
    _expression: ($) =>
      choice(
        $.identifier,
        $.type_identifier,
        $.number,
        $.string,
        $.boolean,
        $.mood_literal,
        $.nobody_literal,
        $.some_expression,
        $.ok_expression,
        $.err_expression,
        $.binary_expression,
        $.unary_expression,
        $.call_expression,
        $.method_call,
        $.field_access,
        $.index_expression,
        $.pipe_expression,
        $.assignment,
        $.compound_assignment,
        $.shape_literal,
        $.list_literal,
        $.lambda,
        $.if_expression,
        $.parenthesized_expression,
        $.propagation_expression,
      ),

    identifier: ($) => /[a-z_][a-zA-Z0-9_]*/,

    number: ($) =>
      token(choice(
        /0x[0-9a-fA-F_]+/,
        /0b[01_]+/,
        /0o[0-7_]+/,
        /[0-9][0-9_]*\.[0-9][0-9_]*/,
        /[0-9][0-9_]*/,
      )),

    string: ($) =>
      seq('"', repeat(choice($.escape_sequence, $.string_interpolation, $.string_content)), '"'),

    string_content: ($) => token.immediate(prec(-1, /[^"\\{]+/)),

    escape_sequence: ($) =>
      token.immediate(seq("\\", choice("n", "r", "t", "\\", '"', "0", "{", "}"))),

    string_interpolation: ($) =>
      seq(token.immediate("{"), $._expression, "}"),

    boolean: ($) => choice("true", "false", "yes", "no", "hai", "iie"),

    mood_literal: ($) =>
      seq(".", choice("chill", "focused", "hype", "mono_no_aware", "muv_luv")),

    nobody_literal: ($) => "nobody",
    some_expression: ($) => seq("some", "(", $._expression, ")"),
    ok_expression: ($) => seq("ok", "(", $._expression, ")"),
    err_expression: ($) => seq("err", "(", $._expression, ")"),

    binary_expression: ($) =>
      choice(
        ...[
          ["+", 6], ["-", 6],
          ["*", 7], ["/", 7], ["%", 7],
          ["==", 4], ["!=", 4],
          ["<", 5], [">", 5], ["<=", 5], [">=", 5],
          ["and", 3], ["or", 2],
        ].map(([op, p]) =>
          prec.left(p, seq(field("left", $._expression), field("operator", op), field("right", $._expression)))
        ),
      ),

    unary_expression: ($) =>
      prec(8, seq(field("operator", choice("-", "not")), field("operand", $._expression))),

    assignment: ($) =>
      prec.right(1, seq(field("left", $._expression), "=", field("right", $._expression))),

    compound_assignment: ($) =>
      prec.right(1, seq(field("left", $._expression),
        field("operator", choice("+=", "-=", "*=", "/=")),
        field("right", $._expression))),

    call_expression: ($) =>
      prec(9, seq(
        field("function", choice($.identifier, $.scoped_identifier)),
        "(", optional(commaSep1($._expression)), ")")),

    scoped_identifier: ($) =>
      seq(field("scope", choice($.identifier, $.type_identifier)),
        "::", field("name", $.identifier)),

    method_call: ($) =>
      prec.left(9, seq(
        field("object", $._expression), ".",
        field("method", $.identifier),
        "(", optional(commaSep1($._expression)), ")")),

    field_access: ($) =>
      prec.left(9, seq(field("object", $._expression), ".", field("field", $.identifier))),

    index_expression: ($) =>
      prec(9, seq(field("object", $._expression), "[", field("index", $._expression), "]")),

    pipe_expression: ($) =>
      prec.left(1, seq(field("left", $._expression), "|>", field("right", $._expression))),

    shape_literal: ($) =>
      prec(1, seq(field("type", $.type_identifier), "{",
        optional(commaSep1($.shape_field_init)), optional(","), "}")),

    shape_field_init: ($) =>
      seq(field("name", $.identifier), ":", field("value", $._expression)),

    list_literal: ($) =>
      seq("[", optional(commaSep1($._expression)), optional(","), "]"),

    lambda: ($) =>
      seq(optional(seq("copy", "(", commaSep1($.identifier), ")")),
        "||", field("body", $.block)),

    if_expression: ($) =>
      prec.right(seq("if", field("condition", $._expression),
        field("consequence", $.block),
        optional(seq("else", field("alternative", choice($.if_expression, $.block)))))),

    parenthesized_expression: ($) =>
      seq("(", $._expression, ")"),

    propagation_expression: ($) =>
      prec(10, seq(field("expression", $._expression), "?")),
  },
});

function commaSep1(rule) {
  return seq(rule, repeat(seq(",", rule)));
}
