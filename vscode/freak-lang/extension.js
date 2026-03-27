const vscode = require('vscode');
const path = require('path');
const { spawn } = require('child_process');

let lspProcess = null;
let outputChannel = null;

function activate(context) {
    outputChannel = vscode.window.createOutputChannel('FREAK LSP');

    const config = vscode.workspace.getConfiguration('freak');
    if (!config.get('lsp.enabled', true)) {
        outputChannel.appendLine('FREAK LSP is disabled');
        return;
    }

    const pythonPath = config.get('lsp.pythonPath', 'python');
    let serverPath = config.get('lsp.serverPath', '');

    if (!serverPath) {
        // Auto-detect: look for freak_lsp.py relative to extension
        const candidates = [
            path.join(context.extensionPath, '..', '..', 'lsp', 'freak_lsp.py'),
            path.join(context.extensionPath, 'freak_lsp.py'),
        ];
        for (const candidate of candidates) {
            try {
                require('fs').accessSync(candidate);
                serverPath = candidate;
                break;
            } catch (e) {}
        }
    }

    if (!serverPath) {
        outputChannel.appendLine('Could not find freak_lsp.py. Set freak.lsp.serverPath in settings.');
        vscode.window.showWarningMessage(
            'FREAK LSP: freak_lsp.py not found. Install pygls (pip install pygls) and set freak.lsp.serverPath.'
        );
        return;
    }

    outputChannel.appendLine(`Starting FREAK LSP: ${pythonPath} ${serverPath}`);

    // Check if pygls is installed
    const checkProcess = spawn(pythonPath, ['-c', 'import pygls; print("ok")']);
    let checkOutput = '';
    checkProcess.stdout.on('data', (data) => { checkOutput += data.toString(); });
    checkProcess.on('close', (code) => {
        if (code !== 0 || !checkOutput.includes('ok')) {
            vscode.window.showWarningMessage(
                'FREAK LSP requires pygls. Run: pip install pygls lsprotocol'
            );
            outputChannel.appendLine('pygls not installed. Run: pip install pygls lsprotocol');
            return;
        }
        startLSP(context, pythonPath, serverPath);
    });
}

function startLSP(context, pythonPath, serverPath) {
    // Use vscode-languageclient if available, otherwise fall back to raw process
    try {
        const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

        const serverOptions = {
            command: pythonPath,
            args: [serverPath, '--stdio'],
            transport: TransportKind.stdio,
        };

        const clientOptions = {
            documentSelector: [{ scheme: 'file', language: 'freak' }],
            outputChannel: outputChannel,
        };

        const client = new LanguageClient('freak-lsp', 'FREAK Language Server', serverOptions, clientOptions);
        client.start();
        context.subscriptions.push({ dispose: () => client.stop() });
        outputChannel.appendLine('FREAK LSP started (vscode-languageclient)');
    } catch (e) {
        // vscode-languageclient not installed, start raw process for basic functionality
        outputChannel.appendLine('vscode-languageclient not found, starting raw LSP process');
        outputChannel.appendLine('For full LSP support: npm install vscode-languageclient');

        lspProcess = spawn(pythonPath, [serverPath, '--stdio']);
        lspProcess.stderr.on('data', (data) => {
            outputChannel.appendLine(`LSP stderr: ${data}`);
        });
        lspProcess.on('close', (code) => {
            outputChannel.appendLine(`LSP process exited with code ${code}`);
        });
        context.subscriptions.push({ dispose: () => { if (lspProcess) lspProcess.kill(); } });
    }
}

function deactivate() {
    if (lspProcess) {
        lspProcess.kill();
        lspProcess = null;
    }
}

module.exports = { activate, deactivate };
