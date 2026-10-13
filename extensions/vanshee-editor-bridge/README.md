# V.ANSHEE Editor Bridge

Extensión y puente de comunicación nativa entre **V.ANSHEE Core** y editores de código modernos (**Antigravity IDE**, **VS Code**, **Cursor**, **Windsurf**).

---

## 🚀 Capacidades

1. **Inyección Inmediata de Prompts (< 10ms):**
   - Transmite los comandos de voz de V.ANSHEE directamente al panel del agente de IA o chat sin teclear letra por letra ni mover el ratón.
2. **Inserción Atómica de Código:**
   - Permite que V.ANSHEE inserte fragmentos de código, funciones o archivos completos directamente en la posición activa del cursor mediante la API `editor.edit()`.
3. **Telemetría y Contexto en Tiempo Real:**
   - Informa a V.ANSHEE de forma automática sobre:
     - El archivo abierto y lenguaje de programación (`active_file`, `language_id`).
     - El texto o función seleccionada (`selected_text`).
     - La posición del cursor (`cursor_line`, `cursor_column`).
     - El directorio raíz del espacio de trabajo (`workspace_root`).
4. **Navegación por Voz:**
   - Abre archivos y salta a líneas específicas bajo demanda.

---

## ⚙️ Configuración y Uso

### Opción 1: Conexión WebSocket (Extensión)
1. Inicia el servidor de V.ANSHEE (`.\start_vanshee_ui.ps1`).
2. La extensión se conectará automáticamente a:
   ```text
   ws://localhost:8000/ws/editor
   ```
3. En la barra de estado inferior derecha verás el indicador: `$(radio-tower) V.ANSHEE: Conectado`.

### Opción 2: Model Context Protocol (MCP Server)
Para editores con soporte nativo de MCP (Antigravity IDE, Claude Desktop, Cursor, OpenCode), agrega la siguiente entrada en tu archivo `mcp_config.json`:

```json
{
  "mcpServers": {
    "vanshee": {
      "command": "python",
      "args": ["-m", "src.integrations.mcp_server"],
      "cwd": "c:\\Users\\Entoma\\Desktop\\vanshee-core"
    }
  }
}
```
