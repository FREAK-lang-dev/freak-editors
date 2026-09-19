const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client = null;

async function activate(context) {
    const outputChannel = vscode.window.createOutputChannel('FREAK');

    const config = vscode.workspace.getConfiguration('freak');
    if (!config.get('lsp.enabled', true)) {
        outputChannel.appendLine('FREAK LSP disabled in settings');
        return;
    }

    // Find python
    const pythonPath = config.get('lsp.pythonPath', '') || findPython();
    if (!pythonPath) {
        vscode.window.showErrorMessage('FREAK: Python not found. Install Python and set freak.lsp.pythonPath');
        return;
    }

    // Find freak_lsp.py — bundled with the extension
    let serverPath = config.get('lsp.serverPath', '');
    if (!serverPath) {
        serverPath = path.join(context.extensionPath, 'freak_lsp.py');
    }

    if (!fs.existsSync(serverPath)) {
        vscode.window.showErrorMessage(`FREAK: LSP server not found at ${serverPath}`);
        return;
    }

    outputChannel.appendLine(`Python: ${pythonPath}`);
    outputChannel.appendLine(`Server: ${serverPath}`);

    // Ensure pygls is installed
    const pyglsOk = await checkPygls(pythonPath, outputChannel);
    if (!pyglsOk) {
        const choice = await vscode.window.showWarningMessage(
            'FREAK LSP needs pygls. Install it now?',
            'Install', 'Cancel'
        );
        if (choice === 'Install') {
            const installed = await installPygls(pythonPath, path.join(context.extensionPath, 'requirements.txt'), outputChannel);
            if (!installed) return;
        } else {
            outputChannel.appendLine('pygls not installed — LSP disabled');
            return;
        }
    }

    // Start LSP
    const serverOptions = {
        command: pythonPath,
        args: [serverPath, '--stdio'],
        transport: TransportKind.stdio,
    };

    const clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'freak' }],
        outputChannel: outputChannel,
    };

    client = new LanguageClient('freak-lsp', 'FREAK Language Server', serverOptions, clientOptions);

    try {
        await client.start();
        outputChannel.appendLine('FREAK LSP started');
        context.subscriptions.push({ dispose: () => client.stop() });
    } catch (err) {
        outputChannel.appendLine(`Failed to start LSP: ${err.message}`);
        vscode.window.showErrorMessage(`FREAK LSP failed: ${err.message}`);
    }
}

function findPython() {
    // Try common Python names
    const { execSync } = require('child_process');
    for (const cmd of ['python3', 'python', 'py']) {
        try {
            execSync(`${cmd} --version`, { stdio: 'pipe', timeout: 5000 });
            return cmd;
        } catch (e) {}
    }
    return null;
}

function checkPygls(pythonPath, outputChannel) {
    return new Promise((resolve) => {
        const { execFile } = require('child_process');
        execFile(pythonPath, ['-c', "from pygls.server import LanguageServer; import lsprotocol; print('ok')"], { timeout: 10000 }, (err, stdout) => {
            if (err || !stdout.includes('ok')) {
                outputChannel.appendLine('pygls/lsprotocol not installed');
                resolve(false);
            } else {
                outputChannel.appendLine('pygls OK');
                resolve(true);
            }
        });
    });
}

function installPygls(pythonPath, requirementsPath, outputChannel) {
    return new Promise((resolve) => {
        const { execFile } = require('child_process');
        outputChannel.appendLine('Installing pygls and lsprotocol...');
        outputChannel.show();

        execFile(pythonPath, ['-m', 'pip', 'install', '-r', requirementsPath], { timeout: 60000 }, (err, stdout, stderr) => {
            if (err) {
                outputChannel.appendLine(`Install failed: ${stderr}`);
                vscode.window.showErrorMessage(`Failed to install FREAK LSP dependencies. Run: ${pythonPath} -m pip install -r "${requirementsPath}"`);
            } else {
                outputChannel.appendLine('pygls installed successfully');
            }
            resolve(!err);
        });
    });
}

function deactivate() {
    if (client) {
        return client.stop();
    }
}

module.exports = { activate, deactivate };
