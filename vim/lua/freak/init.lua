-- FREAK support for Neovim: tree-sitter highlighting and the freak-lsp
-- language server. The regex syntax in syntax/freak.vim stays as the fallback
-- whenever the tree-sitter parser is not installed.
local M = {}

-- The grammar these queries are written and tested against. Keep in step
-- with zed/freak-lang/extension.toml; tests/vim_highlighting.py checks it.
M.grammar = {
  url = "https://github.com/FREAK-lang-dev/tree-sitter-freak",
  revision = "186ecf6344019574b0f59a968050c00c598e0b62",
}

local defaults = {
  -- Register the parser with nvim-treesitter (`:TSInstall freak`) and use
  -- tree-sitter highlighting in .fk buffers once the parser is installed.
  treesitter = true,
  -- Start a FREAK language server for .fk buffers.
  lsp = true,
  -- Server command. nil finds `freak-lsp` on PATH. To use the Python server
  -- from freak-editors instead: { "python3", "/path/to/freak_lsp.py", "--stdio" }
  lsp_cmd = nil,
  -- Passed as initializationOptions, e.g. { compilerPath = "freak" }.
  lsp_init_options = nil,
  -- Files that mark a project root for the server.
  root_markers = { "hangar.toml", ".git" },
}

M.options = vim.deepcopy(defaults)

local function parser_info()
  return {
    url = M.grammar.url,
    revision = M.grammar.revision,
    files = { "src/parser.c" },
    branch = "main",
  }
end

local function register_parser()
  local ok, parsers = pcall(require, "nvim-treesitter.parsers")
  if not ok or type(parsers) ~= "table" then
    return
  end
  if type(parsers.get_parser_configs) == "function" then
    -- nvim-treesitter `master`.
    parsers.get_parser_configs().freak = {
      install_info = parser_info(),
      filetype = "freak",
      maintainers = {},
    }
  else
    -- nvim-treesitter `main` rebuilds its parser table on :TSUpdate.
    local function add()
      require("nvim-treesitter.parsers").freak = { install_info = parser_info(), tier = 3 }
    end
    add()
    vim.api.nvim_create_autocmd("User", {
      group = M.group,
      pattern = "TSUpdate",
      callback = add,
    })
  end
end

local function root_dir(buf)
  local name = vim.api.nvim_buf_get_name(buf)
  local start = name ~= "" and vim.fs.dirname(name) or vim.fn.getcwd()
  local found = vim.fs.find(M.options.root_markers, { upward = true, path = start })[1]
  return found and vim.fs.dirname(found) or start
end

local function lsp_cmd()
  if M.options.lsp_cmd then
    return M.options.lsp_cmd
  end
  if vim.fn.executable("freak-lsp") == 1 then
    return { "freak-lsp" }
  end
end

local function attach(buf)
  if M.options.treesitter then
    -- Fails quietly when the parser isn't installed; regex syntax stays on.
    pcall(vim.treesitter.start, buf, "freak")
  end
  if M.options.lsp and vim.lsp.start then
    local cmd = lsp_cmd()
    if cmd then
      vim.lsp.start({
        name = "freak-lsp",
        cmd = cmd,
        root_dir = root_dir(buf),
        init_options = M.options.lsp_init_options,
      }, { bufnr = buf })
    end
  end
end

function M.setup(opts)
  M.options = vim.tbl_deep_extend("force", vim.deepcopy(defaults), opts or {})
  M.group = vim.api.nvim_create_augroup("freak", { clear = true })
  -- ftdetect/freak.vim covers plugin managers that add vim/ at startup; this
  -- covers ones that add it later, such as lazy.nvim's config function.
  if vim.filetype and vim.filetype.add then
    vim.filetype.add({ extension = { fk = "freak" } })
  end
  if M.options.treesitter then
    register_parser()
  end
  vim.api.nvim_create_autocmd("FileType", {
    group = M.group,
    pattern = "freak",
    callback = function(args)
      attach(args.buf)
    end,
  })
  -- Buffers that were already open when setup ran.
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_loaded(buf) and vim.bo[buf].filetype == "freak" then
      attach(buf)
    end
  end
end

return M
