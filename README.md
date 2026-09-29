# ⚡ V.ANSHEE Core - Sistema Autónomo de Control por Voz y Automatización para Windows

**V.ANSHEE (Visual & Audio Natural System for Holistic Execution & Empowerment)** es un asistente y copiloto inteligente autónomo diseñado para controlar, automatizar y sincronizarse con el entorno operativo de **Windows OS** mediante lenguaje natural, comandos de voz y percepción contextual.

---

## 🌟 Nueva Interfaz de Control de Vanguardia (UI)

Se ha incorporado una consola visual de última generación estilo estación de trabajo cyberpunk / HUD que resuelve las limitaciones de la línea de comandos tradicional y permite operar el sistema con máxima eficiencia.

### 🚀 Cómo Iniciar la Interfaz

Puedes iniciar la consola de cualquiera de las siguientes formas:

1. **PowerShell (Recomendado):**
   ```powershell
   .\start_vanshee.ps1
   # o específicamente:
   .\start_vanshee_ui.ps1
   ```

2. **Doble clic desde el Explorador de Windows:**
   - Ejecuta `start_vanshee_ui.bat`.

3. **Ejecución directa en Python:**
   ```powershell
   .\.venv\Scripts\python.exe run_ui.py
   ```

*(Nota: Si deseas ejecutar el bucle clásico en terminal por voz, usa `.\start_vanshee.ps1 -Cli`)*

---

## 🖥️ Módulos de la Interfaz

### 1. ⚡ Centro de Mando (HUD)
- **Neural Core Visualizer**: Orbe holográfico animado que reacciona en tiempo real a los estados del sistema:
  - `LISTO` (Pulso cian suave)
  - `ESCUCHANDO` (Resplandor violeta/carmesí reactivo a la voz)
  - `RAZONANDO` (Giro dorado de inferencia con Ollama Llama 3.2)
  - `EJECUTANDO` (Onda esmeralda de confirmación)
- **Doble Modalidad de Entrada**:
  - **Voz con Espectrograma**: Graba voz mediante el navegador o el micrófono local con visualizador de frecuencias en vivo en Canvas. Atajo global: `Ctrl + Espacio`.
  - **Barra de Comandos en Lenguaje Natural**: Escribe directamente instrucciones sin depender del silencio ambiental.
  - **Sugerencias Rápidas**: Chips de 1 clic para abrir VS Code, Chrome, Terminal, crear proyectos o generar archivos.
- **Monitor de Contexto en Vivo**: Detecta la ventana activa del usuario en Windows y genera sugerencias inteligentes automáticas.
- **Flujo de Ejecución (Pipeline Inspector)**: Muestra en tarjetas el desglose secuencial de pasos ejecutados con estado de éxito o error.

### 2. 🚀 Lanzador de Aplicaciones
- Explora y busca al instante entre las **más de 140 aplicaciones locales indexadas** de tu equipo.
- Filtros por categoría: *Desarrollo / IDE, Navegadores, Sistema & Terminal, Multimedia, Juegos*.
- Botón de **Lanzamiento Inmediato** con un solo clic.

### 3. 🧠 Inspector NLU & Pipeline
- Permite escribir o dictar órdenes compuestas (ej: *"abre vs code e inicia un proyecto node llamado mi_web"*).
- Visualiza la descomposición estructurada en JSON procesada por **Ollama (Llama 3.2)**.
- Permite ejecutar pipelines inspeccionados de forma selectiva.

### 4. 💾 Memoria Persistente & Aprendizaje
- **Hechos Aprendidos (Brain Facts)**: Vista y gestión de hechos clave (ubicación preferida, última app, preferencias). Permite agregar hechos manualmente o eliminarlos.
- **Comandos Dinámicos Aprendidos**: Diccionario de atajos aprendidos por V.ANSHEE con opción de borrado/olvido.
- **Historial de Interacciones**: Registro completo de órdenes de voz y texto con estado de ejecución.
- **Rutinas y Hábitos**: Patrones de uso detectados por frecuencia y franja horaria.

### 5. ⚙️ Diagnóstico & Calibración de Hardware
- **Test de Micrófono en Tiempo Real**: Mide nivel RMS y pico máximo con indicador de estado (Voz clara / Nivel bajo / Silencio).
- **Control Deslizante de Sensibilidad**: Ajusta el umbral RMS dinámico (`AUDIO_THRESHOLD_RMS`) para micrófonos de baja o alta ganancia.
- **Prueba de Voz TTS**: Prueba la síntesis de voz en español mediante Microsoft SAPI.
- **Chequeo de Subsistemas**: Verificación de conectividad con Ollama, Faster-Whisper, base de datos SQLite y mapeador de pantalla.

---

## 🛠️ Arquitectura del Sistema

```
vanshee-core/
├── config/
│   ├── settings.py           # Configuraciones generales, audio, NLU y servidor
│   └── intents_schema.json   # Esquema NLU de intenciones
├── data/
│   └── vanshee.db            # Base de datos persistente SQLite
├── src/
│   ├── audio/
│   │   ├── recorder.py       # Captura de audio con calibración dinámica y VAD
│   │   ├── stt_whisper.py    # Motor Speech-to-Text Faster-Whisper local
│   │   ├── tts_engine.py     # Síntesis de voz con Windows SAPI
│   │   └── voice_dialog.py   # Diálogos y confirmación por voz
│   ├── executor/
│   │   ├── app_indexer.py    # Indexación de accesos directos de Windows
│   │   ├── dynamic_resolver.py # Resolución de apps, URLs y comandos
│   │   ├── os_executor.py    # Ejecución de pipelines en el sistema operativo
│   │   └── screen_mapper.py  # Detección de ventanas y contexto visual
│   ├── nlu/
│   │   └── intent_parser.py  # Descomposición de intenciones con Ollama Llama 3.2
│   ├── routines/
│   │   ├── db.py             # Esquema e inicialización de tablas SQLite
│   │   └── habit_engine.py   # Registro y aprendizaje de hábitos
│   ├── web/
│   │   ├── index.html        # Estructura de la interfaz de usuario
│   │   └── static/
│   │       ├── css/vanshee.css # Sistema de diseño HUD futurista
│   │       └── js/app.js       # Lógica cliente, Web Audio API y websockets
│   ├── brain.py              # Coordinador central de percepción y acción
│   ├── context_awareness.py  # Detección contextual y sugerencias
│   ├── memory_store.py       # Almacenamiento persistente de hechos
│   ├── semantic_memory.py    # Memoria semántica y similitud
│   └── server.py             # Servidor API FastAPI / Uvicorn
├── run_ui.py                 # Script de arranque de la consola y ventana de escritorio
├── start_vanshee.ps1         # Script de inicio rápido (UI o CLI)
├── start_vanshee_ui.ps1      # Lanzador PowerShell dedicado a la UI
├── start_vanshee_ui.bat      # Lanzador .bat de doble clic
└── requirements.txt          # Dependencias del proyecto
```

---

## 🧪 Verificación del Sistema

Para comprobar que todos los componentes requeridos están listos:
```powershell
.\.venv\Scripts\python.exe scripts\check_system.py
```

Para correr la suite de pruebas unitarias:
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_basic_tasks.py
```
