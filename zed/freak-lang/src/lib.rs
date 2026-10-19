//! Starts `freak-lsp`, the native FREAK language server, for `.fk` files.
//!
//! The server binary is not downloaded: it is found on the worktree's PATH,
//! or set explicitly in Zed's settings:
//!
//! ```json
//! { "lsp": { "freak-lsp": { "binary": { "path": "/path/to/freak-lsp" } } } }
//! ```

use zed_extension_api::{self as zed, settings::LspSettings, LanguageServerId, Result};

struct FreakExtension;

impl zed::Extension for FreakExtension {
    fn new() -> Self {
        FreakExtension
    }

    fn language_server_command(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &zed::Worktree,
    ) -> Result<zed::Command> {
        let binary = LspSettings::for_worktree(language_server_id.as_ref(), worktree)
            .ok()
            .and_then(|settings| settings.binary);
        let configured = binary.as_ref().and_then(|binary| binary.path.clone());
        let args = binary.as_ref().and_then(|binary| binary.arguments.clone()).unwrap_or_default();
        // Configured variables win over the worktree's shell environment.
        let mut env = worktree.shell_env();
        if let Some(extra) = binary.and_then(|binary| binary.env) {
            env.retain(|(key, _)| !extra.contains_key(key));
            env.extend(extra);
        }
        let command = configured
            .or_else(|| worktree.which("freak-lsp"))
            .ok_or_else(|| {
                "freak-lsp was not found on PATH. Build it with \
                 `python src/compiler/v4/build_lsp.py` in Freak-lang, or set \
                 lsp.freak-lsp.binary.path in Zed's settings."
                    .to_string()
            })?;
        Ok(zed::Command { command, args, env })
    }

    fn language_server_initialization_options(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &zed::Worktree,
    ) -> Result<Option<zed::serde_json::Value>> {
        let options = LspSettings::for_worktree(language_server_id.as_ref(), worktree)
            .ok()
            .and_then(|settings| settings.initialization_options);
        Ok(options.or_else(|| {
            let compiler = worktree.which("freak").unwrap_or_else(|| "freak".to_string());
            Some(zed::serde_json::json!({ "compilerPath": compiler }))
        }))
    }
}

zed::register_extension!(FreakExtension);
