-- Neovim only: Vim does not load Lua files from plugin/.
-- Sets FREAK up with the defaults unless your config already called
-- require("freak").setup({...}), or set vim.g.freak_no_setup = true to skip this.
if vim.g.loaded_freak or vim.g.freak_no_setup then
  return
end
vim.g.loaded_freak = true
local freak = require("freak")
-- A setup() call from init.lua runs first; keep its options.
if not freak.configured then
  freak.setup()
end
