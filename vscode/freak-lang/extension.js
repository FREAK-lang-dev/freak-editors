const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const { execFile, execSync } = require('child_process');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client = null;
let outputChannel = null;
let statusItem = null;

const COMMANDS = [
    { id: 'freak.runFile', label: '$(play) Run File', verb: 'run' },
    { id: 'freak.buildFile', label: '$(tools) Build File', verb: 'build' },
    { id: 'freak.checkFile', label: '$(check) Check File', verb: 'check' },
    { id: 'freak.testProject', label: '$(beaker) Test Project' },
    { id: 'freak.restartServer', label: '$(refresh) Restart Language Server' },
];

async function activate(context) {
    outputChannel = vscode.window.createOutputChannel('FREAK');
    context.subscriptions.push(outputChannel);

    for (const { id, verb } of COMMANDS.filter(command => command.verb)) {
        context.subscriptions.push(vscode.commands.registerCommand(id, uri => runOnFile(verb, uri)));
    }
    context.subscriptions.push(
        vscode.commands.registerCommand('freak.testProject', testProject),
        vscode.commands.registerCommand('freak.restartServer', () => restartServer(context)),
        vscode.commands.registerCommand('freak.showCommands', showCommands),
        vscode.window.onDidChangeActiveTextEditor(updateStatus),
        vscode.workspace.onDidChangeConfiguration(event => {
            if (event.affectsConfiguration('freak.compilerPath')) refreshVersion();
            if (event.affectsConfiguration('freak.lsp') || event.affectsConfiguration('freak.compilerPath')
                || event.affectsConfiguration('freak.diagnostics')) {
                restartServer(context);
            }
        }),
        { dispose: () => stopServer() },
    );

    statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusItem.command = 'freak.showCommands';
    context.subscriptions.push(statusItem);
    refreshVersion();

    await startServer(context);
}

function compilerPath() {
    return vscode.workspace.getConfiguration('freak').get('compilerPath', '') || 'freak';
}

// ---- Compiler commands ----

function runCompiler(label, args, cwd, scope) {
    const task = new vscode.Task(
        { type: 'freak', command: args[0] },
        scope || vscode.TaskScope.Workspace,
        label,
        'freak',
        new vscode.ShellExecution(compilerPath(), args, { cwd }),
        '$freak',
    );
    task.presentationOptions = { clear: true, panel: vscode.TaskPanelKind.Dedicated, showReuseMessage: false };
    return vscode.tasks.executeTask(task);
}

async function runOnFile(verb, uri) {
    const editor = vscode.window.activeTextEditor;
    const document = uri
        ? await vscode.workspace.openTextDocument(uri)
        : editor && editor.document;
    if (!document || document.languageId !== 'freak' || document.uri.scheme !== 'file') {
        vscode.window.showWarningMessage('FREAK: open a saved .fk file first.');
        return;
    }
    if (document.isDirty && !(await document.save())) return;
    const file = document.uri.fsPath;
    await runCompiler(`${verb} ${path.basename(file)}`, [verb, path.basename(file)],
        path.dirname(file), vscode.workspace.getWorkspaceFolder(document.uri));
}

async function testProject() {
    const editor = vscode.window.activeTextEditor;
    const folder = (editor && vscode.workspace.getWorkspaceFolder(editor.document.uri))
        || (vscode.workspace.workspaceFolders || [])[0];
    if (!folder) {
        vscode.window.showWarningMessage('FREAK: open a project folder to run its tests.');
        return;
    }
    await vscode.workspace.saveAll(false);
    await runCompiler('test', ['test'], folder.uri.fsPath, folder);
}

async function showCommands() {
    const picked = await vscode.window.showQuickPick(
        COMMANDS.map(({ id, label }) => ({ label, id })), { placeHolder: 'FREAK' });
    if (picked) vscode.commands.executeCommand(picked.id);
}

// ---- Status bar ----

function refreshVersion() {
    execFile(compilerPath(), ['version'], { timeout: 10000, env: { ...process.env, NO_COLOR: '1' } }, (err, stdout) => {
        const match = !err && /\d+\.\d+\.\d+/.exec(String(stdout));
        statusItem.text = match ? `FREAK ${match[0]}` : '$(warning) FREAK';
        statusItem.tooltip = match
            ? 'FREAK compiler commands'
            : `FREAK compiler not found (${compilerPath()}). Set freak.compilerPath.`;
        updateStatus();
    });
}

function updateStatus() {
    const editor = vscode.window.activeTextEditor;
    if (editor && editor.document.languageId === 'freak' && statusItem.text) statusItem.show();
    else statusItem.hide();
}

// ---- Language server ----

async function startServer(context) {
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
        initializationOptions: {
            compilerPath: compilerPath(),
            compilerDiagnostics: config.get('diagnostics.compiler', true),
        },
    };

    client = new LanguageClient('freak-lsp', 'FREAK Language Server', serverOptions, clientOptions);

    try {
        await client.start();
        outputChannel.appendLine('FREAK LSP started');
    } catch (err) {
        client = null;
        outputChannel.appendLine(`Failed to start LSP: ${err.message}`);
        vscode.window.showErrorMessage(`FREAK LSP failed: ${err.message}`);
    }
}

async function stopServer() {
    const running = client;
    client = null;
    if (running) {
        try {
            await running.stop();
        } catch (err) {
            outputChannel.appendLine(`LSP stop failed: ${err.message}`);
        }
    }
}

async function restartServer(context) {
    await stopServer();
    await startServer(context);
}

function findPython() {
    // Try common Python names
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
    return stopServer();
}

module.exports = { activate, deactivate };
