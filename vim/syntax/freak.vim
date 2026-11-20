" Vim syntax file for FREAK (.fk)
" Works in Vim 8.2+ and as Neovim's fallback when the tree-sitter parser is
" not installed. Keyword lists follow the VS Code TextMate grammar.

if exists("b:current_syntax")
  finish
endif

let s:cpo_save = &cpo
set cpo&vim

syn case match
syn sync minlines=200

" ---- Strings and interpolation ---------------------------------------------
syn match  freakEscapeError contained "\\."
syn match  freakEscape      contained "\\\%([nrt\\\"'0{}]\|x\x\x\)"
syn region freakInterpolation contained matchgroup=freakInterpolationDelim
      \ start="{" end="}" contains=@freakExpression
syn region freakString start=+"+ skip=+\\\\\|\\"+ end=+"+
      \ contains=freakEscapeError,freakEscape,freakInterpolation,@Spell
syn region freakChar   start=+'+ skip=+\\\\\|\\'+ end=+'+
      \ contains=freakEscapeError,freakEscape

" ---- Numbers and constants -------------------------------------------------
syn match freakNumber "\<\d[0-9_]*\>"
syn match freakNumber "\<0x[0-9a-fA-F_]\+\>"
syn match freakNumber "\<0b[01_]\+\>"
syn match freakNumber "\<0o[0-7_]\+\>"
syn match freakFloat  "\<\d[0-9_]*\.\d[0-9_]*\>"

syn keyword freakBoolean true false yes no hai iie
syn keyword freakBoolean True False Yes No Hai Iie TRUE FALSE YES NO HAI IIE
syn keyword freakConstant nobody
syn match   freakMood "\.\zs\%(chill\|focused\|hype\|mono_no_aware\|muv_luv\)\>"

" ---- Keywords ---------------------------------------------------------------
syn keyword freakStorage    pilot fixed grounded mut lend copy move
syn keyword freakKeyword    task launch extern impl dyn as self
syn keyword freakStructure  shape doctrine route variant alias
syn keyword freakInclude    use
syn keyword freakConditional if else when check got
syn keyword freakRepeat     while repeat times with until for each in
syn keyword freakRepeat     training arc
syn keyword freakStatement  break continue done
syn match   freakStatement  "\<give\s\+back\>"
syn keyword freakSpecial    eventually foreshadow payoff deus_ex_machina isekai
syn match   freakSpecial    "\<bringing\%(\s\+back\)\?\>"
syn match   freakSpecial    "\<trust\%(-\|\s\+\)me\>"
syn keyword freakBuiltin    say some ok err
syn keyword freakOperatorWord and or not
syn match   freakOperatorWord "\<or\s\+else\>"
syn keyword freakTest       test expect
syn match   freakTest       "\<to\s\+\%(be\|equal\)\>"
" `step` and `max` are keywords only before an operand.
syn match   freakRepeat     "\<step\ze\s\+[-0-9a-zA-Z_(]"

" ---- Types ------------------------------------------------------------------
syn keyword freakType int uint num tiny bool word char void never float float32 big
syn keyword freakType maybe result List Map Set Lineup Shared Weak mood prob power
syn match   freakTypeName "\<\u\w*\>"

" ---- Declarations, calls and paths ----------------------------------------
syn match freakFuncCall  "\<\h\w*\ze\s*("
syn match freakFuncName  "\%(\<task\s\+\)\@<=\h\w*"
syn match freakTypeDecl  "\%(\<\%(shape\|doctrine\|route\|impl\|for\)\s\+\)\@<=\u\w*"
syn match freakNamespace "\<\h\w*\ze::"

" ---- Annotations and operators ---------------------------------------------
syn match freakAnnotation "@\h\w*"
syn match freakOperator   "\.\.=\?\||>\|->\|[-+*/%=<>!?]=\?\|::\|?"
syn match freakDelimiter  "[;,:]"

" ---- Comments ---------------------------------------------------------------
" Defined after the operators so `--` wins over `-` at the same column.
syn keyword freakTodo contained TODO FIXME XXX NOTE HACK
syn match   freakComment "--.*$" contains=freakTodo,@Spell

syn cluster freakExpression contains=freakNumber,freakFloat,freakBoolean,
      \freakConstant,freakMood,freakKeyword,freakOperatorWord,freakBuiltin,
      \freakType,freakTypeName,freakFuncCall,freakNamespace,freakOperator,
      \freakString,freakChar

" ---- Default links ----------------------------------------------------------
hi def link freakTodo              Todo
hi def link freakComment           Comment
hi def link freakString            String
hi def link freakChar              Character
hi def link freakEscape            SpecialChar
hi def link freakEscapeError       Error
hi def link freakInterpolationDelim Delimiter
hi def link freakNumber            Number
hi def link freakFloat             Float
hi def link freakBoolean           Boolean
hi def link freakConstant          Constant
hi def link freakMood              Constant
hi def link freakStorage           StorageClass
hi def link freakKeyword           Keyword
hi def link freakStructure         Structure
hi def link freakInclude           Include
hi def link freakConditional       Conditional
hi def link freakRepeat            Repeat
hi def link freakStatement         Statement
hi def link freakSpecial           Special
hi def link freakBuiltin           Function
hi def link freakOperatorWord      Operator
hi def link freakTest              Keyword
hi def link freakType              Type
hi def link freakTypeName          Type
hi def link freakTypeDecl          Type
hi def link freakFuncName          Function
hi def link freakFuncCall          Function
hi def link freakNamespace         Include
hi def link freakAnnotation        PreProc
hi def link freakOperator          Operator
hi def link freakDelimiter         Delimiter

let b:current_syntax = "freak"

let &cpo = s:cpo_save
unlet s:cpo_save
