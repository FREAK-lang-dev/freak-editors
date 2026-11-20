; FREAK highlights for Neovim (nvim-treesitter capture names).
; Written against tree-sitter-freak at the revision pinned in lua/freak/init.lua.
; Later patterns win, so the general `(identifier) @variable` comes first.

(identifier) @variable

; Comments
(comment) @comment @spell

; Strings and interpolation
(string) @string
(string_content) @string
(escape_sequence) @string.escape

; Numbers and constants
(number) @number
(boolean) @boolean
(nobody_literal) @constant.builtin
(mood_literal) @constant.builtin

; Keywords: declarations
[
  "pilot"
  "fixed"
  "launch"
  "extern"
  "impl"
] @keyword

"task" @keyword.function

[
  "shape"
  "doctrine"
  "route"
] @keyword.type

"use" @keyword.import

[
  "mut"
  "grounded"
  "lend"
  "copy"
] @keyword.modifier

; Keywords: control flow
[
  "if"
  "else"
  "when"
] @keyword.conditional

[
  "repeat"
  "times"
  "until"
  "while"
  "with"
  "step"
  "training"
  "arc"
  "for"
  "each"
  "in"
] @keyword.repeat

(break_statement) @keyword.repeat
(continue_statement) @keyword.repeat

[
  "give"
  "back"
] @keyword.return

"done" @punctuation.bracket

; `impl X for Y` is not a loop.
(impl_block
  "for" @keyword)

; Keywords: FREAK's special blocks
[
  "eventually"
  "trust-me"
  "isekai"
  "bringing"
  "deus_ex_machina"
  "foreshadow"
  "payoff"
] @keyword

"test" @keyword

; Built-in calls and constructors
[
  "say"
  "some"
  "ok"
  "err"
] @function.builtin

; Logical operators
[
  "and"
  "or"
  "not"
] @keyword.operator

; Types
(primitive_type) @type.builtin
(type_identifier) @type

(generic_type
  name: (type_identifier) @type)
(generic_type
  name: (identifier) @type)
(generic_parameters
  (type_identifier) @type)

; Functions
(function_declaration
  name: (identifier) @function)
(launch_declaration
  name: (identifier) @function)

(call_expression
  function: (identifier) @function.call)
(call_expression
  function: (scoped_identifier
    scope: (_) @module
    name: (identifier) @function.call))

(method_call
  method: (identifier) @function.method.call)

(parameter
  name: (identifier) @variable.parameter)

; Shapes, routes and fields
(shape_declaration
  name: (type_identifier) @type.definition)
(doctrine_declaration
  name: (type_identifier) @type.definition)
(route_declaration
  name: (type_identifier) @type.definition)
(impl_block
  type: (type_identifier) @type)
(impl_block
  target: (type_identifier) @type)

(route_variant
  name: (type_identifier) @constant)

(field_declaration
  name: (identifier) @variable.member)
(field_access
  field: (identifier) @variable.member)
(shape_field_init
  name: (identifier) @variable.member)

; Annotations
(annotation
  "@" @attribute
  name: (identifier) @attribute)

; Operators
[
  "|>"
  ".."
  "..="
  "->"
  "?"
  "="
  "+="
  "-="
  "*="
  "/="
  "+"
  "-"
  "*"
  "/"
  "%"
  "=="
  "!="
  "<"
  ">"
  "<="
  ">="
] @operator

; Punctuation
[
  "("
  ")"
  "["
  "]"
  "{"
  "}"
] @punctuation.bracket

[
  ","
  ";"
  ":"
  "::"
  "."
] @punctuation.delimiter

; Interpolation braces, after the generic brackets so they win.
(string_interpolation
  "{" @punctuation.special
  "}" @punctuation.special)
