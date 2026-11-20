" Vim indent file for FREAK (.fk)
" Brace-based: indent after an unclosed {, ( or [, and dedent lines that start
" with }, ), ] or `done` (FREAK's synonym for }).

if exists("b:did_indent")
  finish
endif
let b:did_indent = 1

setlocal autoindent
setlocal indentexpr=FreakIndent(v:lnum)
setlocal indentkeys=0},0),0],!^F,o,O,0=done
let b:undo_indent = "setlocal autoindent< indentexpr< indentkeys<"

if exists("*FreakIndent")
  finish
endif

let s:cpo_save = &cpo
set cpo&vim

" The line with strings blanked and the trailing -- comment removed.
function! s:Code(lnum) abort
  let line = getline(a:lnum)
  let line = substitute(line, '"\%(\\.\|[^"\\]\)*"', '""', 'g')
  let line = substitute(line, "'\\%(\\\\.\\|[^'\\\\]\\)*'", "''", 'g')
  return substitute(line, '--.*$', '', '')
endfunction

function! s:Count(text, pattern) abort
  return len(split(a:text, a:pattern, 1)) - 1
endfunction

function! s:Closers(text) abort
  return matchstr(a:text, '^\s*\%([})\]]\s*\|done\>\s*\)*')
endfunction

function! FreakIndent(lnum) abort
  let prev = prevnonblank(a:lnum - 1)
  " Comment-only lines keep their own indent and don't change the block depth.
  while prev > 0 && getline(prev) =~# '^\s*--'
    let prev = prevnonblank(prev - 1)
  endwhile
  if prev == 0
    return 0
  endif

  let code = s:Code(prev)
  let leading = s:Closers(code)
  let rest = code[len(leading):]
  let opens = s:Count(rest, '[{(\[]')
  let closes = s:Count(rest, '[})\]]') + s:Count(rest, '\<done\>')

  let ind = indent(prev)
  " `}}` closes two blocks; the line's own indent only accounts for the first.
  let extra = s:Count(leading, '[})\]]') + s:Count(leading, '\<done\>') - 1
  if extra > 0
    let ind -= extra * shiftwidth()
  endif
  if opens > closes
    let ind += shiftwidth()
  elseif closes > opens
    let ind -= shiftwidth()
  endif
  if s:Code(a:lnum) =~# '^\s*\%([})\]]\|done\>\)'
    let ind -= shiftwidth()
  endif
  return ind < 0 ? 0 : ind
endfunction

let &cpo = s:cpo_save
unlet s:cpo_save
