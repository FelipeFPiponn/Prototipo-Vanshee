"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const ws_1 = __importDefault(require("ws"));
let wsClient = null;
let reconnectTimer = null;
let statusBarItem;
function activate(context) {
    console.log('[V.ANSHEE Bridge] Extensión activada.');
    // Crear ícono en la barra de estado
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'vanshee.status';
    statusBarItem.text = '$(circle-slash) V.ANSHEE: Desconectado';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
    // Registrar comandos
    context.subscriptions.push(vscode.commands.registerCommand('vanshee.connect', () => connectToVanshee(context)), vscode.commands.registerCommand('vanshee.disconnect', () => disconnectFromVanshee()), vscode.commands.registerCommand('vanshee.status', () => showStatus()));
    // Registrar observadores de eventos del editor para emitir telemetría de contexto
    context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(() => broadcastContext()), vscode.window.onDidChangeTextEditorSelection(() => broadcastContext()), vscode.workspace.onDidSaveTextDocument(() => broadcastContext()));
    // Auto-conexión si está configurada
    const autoConnect = vscode.workspace.getConfiguration('vanshee').get('autoConnect', true);
    if (autoConnect) {
        connectToVanshee(context);
    }
}
function deactivate() {
    disconnectFromVanshee();
}
function connectToVanshee(context) {
    if (wsClient && wsClient.readyState === ws_1.default.OPEN) {
        vscode.window.showInformationMessage('V.ANSHEE Bridge ya está conectado.');
        return;
    }
    const serverUrl = vscode.workspace.getConfiguration('vanshee').get('serverUrl', 'ws://localhost:8000/ws/editor');
    statusBarItem.text = '$(sync~spin) V.ANSHEE: Conectando...';
    try {
        wsClient = new ws_1.default(serverUrl);
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
        wsClient.on('message', async (data) => {
            try {
                const msg = JSON.parse(data);
                await handleIncomingRpc(msg);
            }
            catch (e) {
                console.error('[V.ANSHEE Bridge Error] Error procesando mensaje:', e);
            }
        });
        wsClient.on('close', () => {
            console.log('[V.ANSHEE Bridge] Conexión cerrada. Reintentando en 5s...');
            statusBarItem.text = '$(circle-slash) V.ANSHEE: Desconectado';
            scheduleReconnect(context);
        });
        wsClient.on('error', (err) => {
            console.warn('[V.ANSHEE Bridge Warning] Error de conexión:', err?.message || err);
            statusBarItem.text = '$(alert) V.ANSHEE: Error';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        });
    }
    catch (e) {
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
function scheduleReconnect(context) {
    if (reconnectTimer) {
        return;
    }
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectToVanshee(context);
    }, 5000);
}
function sendJson(payload) {
    if (wsClient && wsClient.readyState === ws_1.default.OPEN) {
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
async function handleIncomingRpc(req) {
    const id = req.id;
    const method = req.method;
    const params = req.params || {};
    if (!method) {
        return;
    }
    try {
        if (method === 'send_prompt') {
            const prompt = params.prompt || '';
            const mode = params.mode || 'agent';
            let opened = false;
            let delivered = false;
            // 1. Antigravity IDE y VS Code Chat en Modo Agente nativo (mode: 'agent' + submit directo)
            try {
                // Al pasar mode: 'agent' y isPartialQuery: false, VS Code / Antigravity cambia el chat al modo Agente
                // y ejecuta automáticamente acceptInput() enviando el prompt de forma inmediata (no como mensaje/borrador).
                await vscode.commands.executeCommand('workbench.action.chat.open', {
                    mode: 'agent',
                    query: prompt,
                    isPartialQuery: false
                });
                opened = true;
                delivered = true;
                console.log('[V.ANSHEE Bridge] Prompt enviado directamente al Agente (workbench.action.chat.open mode=agent)');
            }
            catch (err) {
                console.warn('[V.ANSHEE Bridge] workbench.action.chat.open con mode=agent no disponible:', err);
            }
            // 2. VS Code Copilot Edits / Sesión de Agente de edición
            if (!delivered) {
                try {
                    await vscode.commands.executeCommand('workbench.action.chat.openEditSession', {
                        query: prompt,
                        isPartialQuery: false
                    });
                    opened = true;
                    delivered = true;
                    console.log('[V.ANSHEE Bridge] Prompt enviado vía workbench.action.chat.openEditSession');
                }
                catch (err) {
                    console.warn('[V.ANSHEE Bridge] workbench.action.chat.openEditSession no disponible:', err);
                }
            }
            // 3. Cursor Composer en Modo Agente
            if (!delivered) {
                try {
                    await vscode.commands.executeCommand('cursor.composer.open', { text: prompt });
                    opened = true;
                    delivered = true;
                    try {
                        await vscode.commands.executeCommand('cursor.action.composer.agent');
                    }
                    catch { }
                    try {
                        await vscode.commands.executeCommand('workbench.action.chat.submit');
                    }
                    catch { }
                    console.log('[V.ANSHEE Bridge] Prompt enviado a Cursor Composer');
                }
                catch (err) {
                    console.warn('[V.ANSHEE Bridge] cursor.composer.open no disponible:', err);
                }
            }
            // 4. Windsurf Cascade (Agente de Windsurf)
            if (!delivered) {
                try {
                    await vscode.commands.executeCommand('windsurf.cascade.focus');
                    opened = true;
                    delivered = true;
                    try {
                        await vscode.commands.executeCommand('workbench.action.chat.submit');
                    }
                    catch { }
                    console.log('[V.ANSHEE Bridge] Prompt enfocado en Windsurf Cascade');
                }
                catch { }
            }
            // 5. Fallback general: workbench.action.chat.open asegurando no quedar como mensaje sin enviar
            if (!delivered) {
                try {
                    await vscode.commands.executeCommand('workbench.action.chat.open', {
                        query: prompt,
                        isPartialQuery: false
                    });
                    opened = true;
                    delivered = true;
                    try {
                        await vscode.commands.executeCommand('workbench.action.chat.submit');
                    }
                    catch { }
                    console.log('[V.ANSHEE Bridge] Prompt enviado vía fallback workbench.action.chat.open');
                }
                catch (err) {
                    console.warn('[V.ANSHEE Bridge] Fallback workbench.action.chat.open falló:', err);
                }
            }
            // Respaldo en portapapeles
            try {
                await vscode.env.clipboard.writeText(prompt);
            }
            catch { }
            // Indicador no invasivo en la barra de estado
            vscode.window.setStatusBarMessage(`$(sparkle) [V.ANSHEE] Prompt enviado al Agente: "${prompt.slice(0, 40)}"`, 5000);
            sendJson({
                jsonrpc: '2.0',
                id: id,
                result: { success: delivered || opened, prompt: prompt, delivered: delivered, opened: opened, mode: 'agent' }
            });
        }
        else if (method === 'insert_code') {
            const code = params.code || '';
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                await editor.edit((editBuilder) => {
                    if (editor.selection.isEmpty) {
                        editBuilder.insert(editor.selection.active, code);
                    }
                    else {
                        editBuilder.replace(editor.selection, code);
                    }
                });
                sendJson({ jsonrpc: '2.0', id: id, result: { success: true } });
            }
            else {
                sendJson({ jsonrpc: '2.0', id: id, result: { success: false, error: 'No active editor' } });
            }
        }
        else if (method === 'open_file') {
            const filePath = params.file_path || '';
            const line = Math.max(0, (params.line || 1) - 1);
            const column = Math.max(0, (params.column || 1) - 1);
            const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
            const editor = await vscode.window.showTextDocument(doc);
            const pos = new vscode.Position(line, column);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(new vscode.Range(pos, pos));
            sendJson({ jsonrpc: '2.0', id: id, result: { success: true } });
        }
        else if (method === 'run_command') {
            const command = params.command || '';
            let terminal = vscode.window.activeTerminal || vscode.window.createTerminal('V.ANSHEE');
            terminal.show();
            terminal.sendText(command);
            sendJson({ jsonrpc: '2.0', id: id, result: { success: true } });
        }
        else if (method === 'ping') {
            sendJson({ jsonrpc: '2.0', id: id, result: 'pong' });
        }
    }
    catch (err) {
        sendJson({
            jsonrpc: '2.0',
            id: id,
            error: { code: -32603, message: err.message || 'Internal RPC Error' }
        });
    }
}
function showStatus() {
    const isConnected = wsClient && wsClient.readyState === ws_1.default.OPEN;
    const statusMsg = isConnected ? 'Conectado a V.ANSHEE Core (ws://localhost:8000/ws/editor)' : 'Desconectado de V.ANSHEE Core';
    vscode.window.showInformationMessage(statusMsg, isConnected ? 'Desconectar' : 'Conectar')
        .then((choice) => {
        if (choice === 'Conectar') {
            connectToVanshee({});
        }
        else if (choice === 'Desconectar') {
            disconnectFromVanshee();
        }
    });
}
//# sourceMappingURL=extension.js.map