-- Neovim only: Vim does not load Lua files from plugin/.
-- Sets FREAK up with the defaults. Call require("freak").setup({...}) from your
-- config to change them, or set vim.g.freak_no_setup = true to skip this.
if vim.g.loaded_freak or vim.g.freak_no_setup then
  return
end
vim.g.loaded_freak = true
require("freak").setup()
