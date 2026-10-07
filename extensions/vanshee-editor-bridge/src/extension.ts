import * as vscode from 'vscode';
import WebSocket from 'ws';

let wsClient: WebSocket | null = null;
let reconnectTimer: NodeJS.Timeout | null = null;
let statusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {
    console.log('[V.ANSHEE Bridge] Extensión activada.');

    // Crear ícono en la barra de estado
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'vanshee.status';
    statusBarItem.text = '$(circle-slash) V.ANSHEE: Desconectado';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Registrar comandos
    context.subscriptions.push(
        vscode.commands.registerCommand('vanshee.connect', () => connectToVanshee(context)),
        vscode.commands.registerCommand('vanshee.disconnect', () => disconnectFromVanshee()),
        vscode.commands.registerCommand('vanshee.status', () => showStatus())
    );

    // Registrar observadores de eventos del editor para emitir telemetría de contexto
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(() => broadcastContext()),
        vscode.window.onDidChangeTextEditorSelection(() => broadcastContext()),
        vscode.workspace.onDidSaveTextDocument(() => broadcastContext())
    );

    // Auto-conexión si está configurada
    const autoConnect = vscode.workspace.getConfiguration('vanshee').get<boolean>('autoConnect', true);
    if (autoConnect) {
        connectToVanshee(context);
    }
}

export function deactivate() {
    disconnectFromVanshee();
}

function connectToVanshee(context: vscode.ExtensionContext) {
    if (wsClient && wsClient.readyState === WebSocket.OPEN) {
        vscode.window.showInformationMessage('V.ANSHEE Bridge ya está conectado.');
        return;
    }

    const serverUrl = vscode.workspace.getConfiguration('vanshee').get<string>('serverUrl', 'ws://localhost:8000/ws/editor');
    statusBarItem.text = '$(sync~spin) V.ANSHEE: Conectando...';

    try {
        wsClient = new WebSocket(serverUrl);

        wsClient.on('open', () => {
            console.log('[V.ANSHEE Bridge] Conectado a V.ANSHEE Core.');
            statusBarItem.text = '$(radio-tower) V.ANSHEE: Conectado';
            statusBarItem.backgroundColor = undefined;

            // Registrar este editor con su información inicial
            const editorInfo = getEditorMetadata();
            sendJson({
                jsonrpc: '2.0',
                id: 'init_reg',
                method: 'register',
                editor_name: vscode.env.appName || 'vscode',
                metadata: editorInfo
            });
        });

        wsClient.on('message', async (data: string) => {
            try {
                const msg = JSON.parse(data);
                await handleIncomingRpc(msg);
            } catch (e) {
                console.error('[V.ANSHEE Bridge Error] Error procesando mensaje:', e);
            }
        });

        wsClient.on('close', () => {
            console.log('[V.ANSHEE Bridge] Conexión cerrada. Reintentando en 5s...');
            statusBarItem.text = '$(circle-slash) V.ANSHEE: Desconectado';
            scheduleReconnect(context);
        });

        wsClient.on('error', (err) => {
            console.warn('[V.ANSHEE Bridge Warning] Error de conexión:', err.message);
            statusBarItem.text = '$(alert) V.ANSHEE: Error';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        });

    } catch (e) {
        console.error('[V.ANSHEE Bridge Error] No se pudo crear WebSocket:', e);
        scheduleReconnect(context);
    }
}

function disconnectFromVanshee() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    if (wsClient) {
        wsClient.close();
        wsClient = null;
    }
    statusBarItem.text = '$(circle-slash) V.ANSHEE: Desconectado';
    statusBarItem.backgroundColor = undefined;
}

function scheduleReconnect(context: vscode.ExtensionContext) {
    if (reconnectTimer) {
        return;
    }
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectToVanshee(context);
    }, 5000);
}

function sendJson(payload: any) {
    if (wsClient && wsClient.readyState === WebSocket.OPEN) {
        wsClient.send(JSON.stringify(payload));
    }
}

function getEditorMetadata() {
    const editor = vscode.window.activeTextEditor;
    const workspaceFolders = vscode.workspace.workspaceFolders;
    const workspaceRoot = workspaceFolders && workspaceFolders.length > 0 ? workspaceFolders[0].uri.fsPath : '';

    return {
        editor_name: vscode.env.appName || 'antigravity',
        workspace_root: workspaceRoot,
        active_file: editor ? editor.document.fileName : '',
        language_id: editor ? editor.document.languageId : '',
        cursor_line: editor ? editor.selection.active.line + 1 : 1,
        cursor_column: editor ? editor.selection.active.character + 1 : 1,
        selected_text: editor ? editor.document.getText(editor.selection) : '',
    };
}

function broadcastContext() {
    const meta = getEditorMetadata();
    sendJson({
        jsonrpc: '2.0',
        method: 'context_update',
        data: meta
    });
}

async function handleIncomingRpc(req: any) {
    const id = req.id;
    const method = req.method;
    const params = req.params || {};

    if (!method) {
        return;
    }

    try {
        if (method === 'send_prompt') {
            const prompt = params.prompt || '';
            // Intentar abrir el chat nativo o enfocar la vista del agente de IA
            try {
                await vscode.commands.executeCommand('workbench.action.chat.open');
            } catch (e) {
                // Fallback si el comando de chat difiere
            }
            // Inyectar en el clipboard o notificar
            await vscode.env.clipboard.writeText(prompt);
            vscode.window.showInformationMessage(`[V.ANSHEE] Prompt recibido: "${prompt}" (Copiado al portapapeles)`);

            sendJson({
                jsonrpc: '2.0',
                id: id,
                result: { success: true, prompt: prompt }
            });

        } else if (method === 'insert_code') {
            const code = params.code || '';
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                await editor.edit((editBuilder) => {
                    if (editor.selection.isEmpty) {
                        editBuilder.insert(editor.selection.active, code);
                    } else {
                        editBuilder.replace(editor.selection, code);
                    }
                });
                sendJson({ jsonrpc: '2.0', id: id, result: { success: true } });
            } else {
                sendJson({ jsonrpc: '2.0', id: id, result: { success: false, error: 'No active editor' } });
            }

        } else if (method === 'open_file') {
            const filePath = params.file_path || '';
            const line = Math.max(0, (params.line || 1) - 1);
            const column = Math.max(0, (params.column || 1) - 1);

            const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
            const editor = await vscode.window.showTextDocument(doc);
            const pos = new vscode.Position(line, column);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(new vscode.Range(pos, pos));

            sendJson({ jsonrpc: '2.0', id: id, result: { success: true } });

        } else if (method === 'run_command') {
            const command = params.command || '';
            let terminal = vscode.window.activeTerminal || vscode.window.createTerminal('V.ANSHEE');
            terminal.show();
            terminal.sendText(command);

            sendJson({ jsonrpc: '2.0', id: id, result: { success: true } });

        } else if (method === 'ping') {
            sendJson({ jsonrpc: '2.0', id: id, result: 'pong' });
        }
    } catch (err: any) {
        sendJson({
            jsonrpc: '2.0',
            id: id,
            error: { code: -32603, message: err.message || 'Internal RPC Error' }
        });
    }
}

function showStatus() {
    const isConnected = wsClient && wsClient.readyState === WebSocket.OPEN;
    const statusMsg = isConnected ? 'Conectado a V.ANSHEE Core (ws://localhost:8000/ws/editor)' : 'Desconectado de V.ANSHEE Core';
    vscode.window.showInformationMessage(statusMsg, isConnected ? 'Desconectar' : 'Conectar')
        .then((choice) => {
            if (choice === 'Conectar') {
                connectToVanshee({} as any);
            } else if (choice === 'Desconectar') {
                disconnectFromVanshee();
            }
        });
}
