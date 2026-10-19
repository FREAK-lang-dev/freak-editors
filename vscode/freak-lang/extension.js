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
    { id: 'freak.hangarInstall', label: '$(package) Hangar: Install Dependencies', hangar: ['install'] },
    { id: 'freak.hangarUpdate', label: '$(sync) Hangar: Update Dependencies', hangar: ['update'] },
    { id: 'freak.hangarAdd', label: '$(add) Hangar: Add Dependency', hangar: ['add'] },
    { id: 'freak.hangarOutdated', label: '$(versions) Hangar: Show Outdated', hangar: ['outdated'] },
    { id: 'freak.hangarAudit', label: '$(shield) Hangar: Audit', hangar: ['audit'] },
    { id: 'freak.hangarLogin', label: '$(sign-in) Hangar: Log In', hangar: ['auth', 'login'] },
    { id: 'freak.hangarStatus', label: '$(account) Hangar: Account Status', hangar: ['auth', 'status'] },
    { id: 'freak.hangarLogout', label: '$(sign-out) Hangar: Log Out', hangar: ['auth', 'logout'] },
    { id: 'freak.hangarPublishDryRun', label: '$(eye) Hangar: Publish (Dry Run)', hangar: ['publish', '--dry-run'] },
    { id: 'freak.hangarPublish', label: '$(cloud-upload) Hangar: Publish', hangar: ['publish'] },
    { id: 'freak.restartServer', label: '$(refresh) Restart Language Server' },
];

// Build profile flags only apply to build and run; the diagnostic cast also
// applies to check. Settings left at "default" pass nothing, so older
// compilers keep working.
const OPT_FLAGS = { O0: '--O0', O1: '--O1', O2: '--O2', O3: '--O3' };
const LTO_FLAGS = { off: '--lto=off', thin: '--tlto', full: '--flto' };

function compilerFlags(verb) {
    const config = vscode.workspace.getConfiguration('freak');
    const flags = [];
    if (verb === 'build' || verb === 'run') {
        const opt = OPT_FLAGS[config.get('build.optimization', 'default')];
        const lto = LTO_FLAGS[config.get('build.lto', 'default')];
        if (opt) flags.push(opt);
        if (lto) flags.push(lto);
    }
    const cast = config.get('diagnosticCast', 'default');
    if (['off', 'minimal', 'normal'].includes(cast)) flags.push(`--diagnostic-cast=${cast}`);
    return flags;
}

async function activate(context) {
    outputChannel = vscode.window.createOutputChannel('FREAK');
    context.subscriptions.push(outputChannel);

    for (const { id, verb } of COMMANDS.filter(command => command.verb)) {
        context.subscriptions.push(vscode.commands.registerCommand(id, uri => runOnFile(verb, uri)));
    }
    context.subscriptions.push(
        vscode.commands.registerCommand('freak.testProject', testProject),
        ...COMMANDS.filter(command => command.hangar)
            .map(({ id, hangar }) => vscode.commands.registerCommand(id, () => runHangar(hangar))),
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
    // The compiler echoes the path it was given; an absolute one lets the
    // problem matcher locate the file whatever the task's directory.
    await runCompiler(`${verb} ${path.basename(file)}`, [verb, file, ...compilerFlags(verb)],
        path.dirname(file), vscode.workspace.getWorkspaceFolder(document.uri));
}

// ---- Hangar ----

// The nearest hangar.toml above the active file, else in the first workspace
// folder that has one.
function hangarProject() {
    const editor = vscode.window.activeTextEditor;
    const folders = vscode.workspace.workspaceFolders || [];
    if (editor && editor.document.uri.scheme === 'file') {
        const folder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
        const stop = folder ? folder.uri.fsPath : path.parse(editor.document.uri.fsPath).root;
        let dir = path.dirname(editor.document.uri.fsPath);
        for (;;) {
            if (fs.existsSync(path.join(dir, 'hangar.toml'))) return { dir, folder };
            const parent = path.dirname(dir);
            if (dir === stop || parent === dir) break;
            dir = parent;
        }
    }
    for (const folder of folders) {
        if (fs.existsSync(path.join(folder.uri.fsPath, 'hangar.toml'))) {
            return { dir: folder.uri.fsPath, folder };
        }
    }
    return null;
}

async function runHangar(args) {
    const needsProject = args[0] !== 'auth';
    const project = needsProject ? hangarProject() : null;
    if (needsProject && !project) {
        vscode.window.showWarningMessage('FREAK: no hangar.toml found. Run `hangar init` in your project first.');
        return;
    }
    args = [...args];
    if (args[0] === 'add') {
        const name = await vscode.window.showInputBox({
            prompt: 'Package to add',
            placeHolder: 'cockpit',
            validateInput: value => /^[A-Za-z0-9_-]+$/.test(value.trim()) ? null : 'Use letters, digits, - or _',
        });
        if (!name) return;
        const source = await vscode.window.showInputBox({
            prompt: 'Version constraint or Git URL (leave empty for the newest version)',
            placeHolder: '^0.1.0',
        });
        if (source === undefined) return;
        args.push(name.trim());
        if (source.trim()) args.push(source.trim());
    }
    if (args[0] === 'publish' && !args.includes('--dry-run')) {
        const choice = await vscode.window.showWarningMessage(
            `Publish ${path.basename(project.dir)} to the Hangar registry? A published version can't be replaced.`,
            { modal: true }, 'Publish');
        if (choice !== 'Publish') return;
    }
    const cwd = project ? project.dir
        : ((vscode.workspace.workspaceFolders || [])[0] || { uri: { fsPath: process.cwd() } }).uri.fsPath;
    // Hangar reads the manifest and sources from disk; never run (above all
    // publish) against files that failed to save.
    if (!(await vscode.workspace.saveAll(false))) {
        vscode.window.showErrorMessage('FREAK: some files could not be saved, so Hangar was not run.');
        return;
    }
    await runCompiler(`hangar ${args.join(' ')}`, ['hangar', ...args], cwd, project && project.folder);
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

    // A user-supplied server (for example a native FREAK language server)
    // replaces the bundled Python one. It must speak LSP over stdio.
    const command = (config.get('lsp.command', []) || []).filter(part => typeof part === 'string' && part);
    if (command.length) {
        outputChannel.appendLine(`Server: ${command.join(' ')}`);
        return launchClient({ command: command[0], args: command.slice(1), transport: TransportKind.stdio }, config);
    }

    // The native server (freak-lsp) answers from the Maverick compiler's
    // queries. `auto` uses it when it is installed and keeps the Python
    // server otherwise.
    const choice = config.get('lsp.server', 'auto');
    if (choice !== 'python') {
        const native = findNativeServer();
        if (native) {
            outputChannel.appendLine(`Server: ${native}`);
            return launchClient({ command: native, args: [], transport: TransportKind.stdio }, config);
        }
        if (choice === 'freak-lsp') {
            vscode.window.showWarningMessage('FREAK: freak-lsp was not found on PATH or next to the compiler; using the bundled Python server.');
        }
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
    return launchClient({
        command: pythonPath,
        args: [serverPath, '--stdio'],
        transport: TransportKind.stdio,
    }, config);
}

async function launchClient(serverOptions, config) {
    const clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'freak' }],
        outputChannel: outputChannel,
        initializationOptions: {
            compilerPath: compilerPath(),
            compilerDiagnostics: config.get('diagnostics.compiler', true),
            maverickDiagnostics: config.get('diagnostics.maverick', false),
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

let restarting = Promise.resolve();

// Configuration events can arrive in bursts; overlapping restarts would
// leave more than one client running.
function restartServer(context) {
    const run = async () => {
        await stopServer();
        await startServer(context);
    };
    restarting = restarting.then(run, run);
    return restarting;
}

// freak-lsp on PATH, else beside the configured compiler.
function findNativeServer() {
    const names = process.platform === 'win32' ? ['freak-lsp.exe', 'freak-lsp'] : ['freak-lsp'];
    const dirs = (process.env.PATH || '').split(path.delimiter).filter(Boolean);
    const compiler = compilerPath();
    if (path.isAbsolute(compiler)) dirs.unshift(path.dirname(compiler));
    for (const dir of dirs) {
        for (const name of names) {
            const candidate = path.join(dir, name);
            try {
                if (fs.statSync(candidate).isFile()) return candidate;
            } catch (e) {}
        }
    }
    return null;
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
