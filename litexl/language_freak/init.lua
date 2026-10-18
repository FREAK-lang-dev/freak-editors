-- mod-version:3
-- FREAK language support for Lite XL: syntax highlighting, and the bundled
-- language server when the lite-xl-lsp plugin is installed.
local core = require "core"
local common = require "core.common"
local config = require "core.config"
local syntax = require "core.syntax"

config.plugins.language_freak = common.merge({
  -- Register the bundled Python language server with the lsp plugin.
  lsp = true,
  -- Interpreter with pygls installed (see requirements.txt).
  python = PLATFORM == "Windows" and "python" or "python3",
  -- Compiler used for `freak check` diagnostics on open and save.
  compiler = "freak",
  compiler_diagnostics = true,
  -- Command that starts a different FREAK language server over stdio, such as
  -- { "freak-lsp" }. When set it replaces the bundled Python server.
  server_command = nil,
}, config.plugins.language_freak)

local symbols = {}

local function add(kind, words)
  for word in words:gmatch("%S+") do
    symbols[word] = kind
  end
end

add("keyword", [[
  pilot fixed grounded mut task shape doctrine impl variant alias route launch
  extern use as dyn lend copy move
  if else when while repeat times with until for each in training arc
  give back break continue check got
  say done eventually foreshadow payoff deus_ex_machina isekai bringing trust
  test expect and or not
]])

add("keyword2", [[
  int uint num tiny bool word char void never float float32 big
  maybe result List Map Set Lineup Shared Weak mood prob power
]])

add("literal", [[
  true false yes no hai iie True False Yes No Hai Iie TRUE FALSE YES NO HAI IIE
  nobody some ok err self
]])

syntax.add {
  name = "FREAK",
  files = { "%.fk$" },
  comment = "--",
  patterns = {
    { pattern = "%-%-.*",                    type = "comment"  },
    { pattern = { '"', '"', '\\' },          type = "string"   },
    { pattern = { "'", "'", '\\' },          type = "string"   },
    { pattern = "0x[%x_]+",                  type = "number"   },
    { pattern = "0b[01_]+",                  type = "number"   },
    { pattern = "0o[0-7_]+",                 type = "number"   },
    { pattern = "%d[%d_]*%.%d[%d_]*",        type = "number"   },
    { pattern = "%d[%d_]*",                  type = "number"   },
    { pattern = "@[%a_][%w_]*",              type = "keyword2" },
    { pattern = "%.%.=?",                    type = "operator" },
    { pattern = "|>",                        type = "operator" },
    { pattern = "[%+%-%*/%%=<>!?|]+",        type = "operator" },
    -- Mood literals: .chill, .hype, ...
    { pattern = "%.()mono_no_aware%f[^%w_]", type = { "normal", "literal" } },
    { pattern = "%.()muv_luv%f[^%w_]",       type = { "normal", "literal" } },
    { pattern = "%.()chill%f[^%w_]",         type = { "normal", "literal" } },
    { pattern = "%.()focused%f[^%w_]",       type = { "normal", "literal" } },
    { pattern = "%.()hype%f[^%w_]",          type = { "normal", "literal" } },
    -- Words that are keywords only in position, and ordinary names elsewhere.
    { pattern = "%f[%w_]step%f[%s]%s+%f[%w_(%-]",   type = "keyword" },
    { pattern = "%f[%w_]max%f[%s]%s+%f[%w_(]",      type = "keyword" },
    { pattern = "%f[%w_]sessions%f[%s]%s*%f[{]",    type = "keyword" },
    { pattern = "%f[%w_]to%s+be%f[^%w_]",           type = "keyword" },
    { pattern = "[%a_][%w_]*%f[(]",          type = "function" },
    { pattern = "%u[%w_]*",                  type = "keyword2" },
    { pattern = "[%a_][%w_]*",               type = "symbol"   },
  },
  symbols = symbols,
}

-- The server sits beside this file in the installed plugin directory.
local function find_server()
  for _, root in ipairs { USERDIR, DATADIR } do
    local path = table.concat({ root, "plugins", "language_freak", "freak_lsp.py" }, PATHSEP)
    if system.get_file_info(path) then
      return path
    end
  end
end

-- Wait until every plugin has loaded, so a missing or disabled lsp plugin is
-- simply skipped rather than loaded behind the user's back.
core.add_thread(function()
  local options = config.plugins.language_freak
  local lsp = package.loaded["plugins.lsp"]
  if not options.lsp or type(lsp) ~= "table" or not lsp.add_server then
    return
  end
  local command = options.server_command
  if type(command) == "string" then command = { command } end
  if type(command) ~= "table" or #command == 0 then
    local server = find_server()
    if not server then
      core.warn("FREAK: freak_lsp.py not found in plugins/language_freak")
      return
    end
    command = { options.python, server, "--stdio" }
  end
  lsp.add_server {
    name = "freak-lsp",
    language = "freak",
    file_patterns = { "%.fk$" },
    command = command,
    init_options = {
      compilerPath = options.compiler,
      compilerDiagnostics = options.compiler_diagnostics,
    },
    verbose = false,
  }
end)
