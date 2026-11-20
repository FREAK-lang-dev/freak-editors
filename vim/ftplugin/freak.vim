" Vim filetype plugin for FREAK (.fk)
" Works in Vim 8.2+ and Neovim.

if exists("b:did_ftplugin")
  finish
endif
let b:did_ftplugin = 1

let s:cpo_save = &cpo
set cpo&vim

setlocal comments=:--
setlocal commentstring=--\ %s
setlocal formatoptions-=t formatoptions+=croql
setlocal suffixesadd=.fk

let b:undo_ftplugin = "setlocal comments< commentstring< formatoptions< suffixesadd<"

" The FREAK sources, std and examples use four-space indentation.
" Set g:freak_recommended_style = 0 to keep your own settings.
if get(g:, "freak_recommended_style", 1)
  setlocal expandtab shiftwidth=4 softtabstop=4 tabstop=4
  let b:undo_ftplugin .= " | setlocal expandtab< shiftwidth< softtabstop< tabstop<"
endif

let &cpo = s:cpo_save
unlet s:cpo_save
