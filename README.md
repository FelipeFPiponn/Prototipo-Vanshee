# V.ANSHEE — Sistema Inteligente de Control por Voz y Aprendizaje de Rutinas

**V.ANSHEE** es una solución tecnológica desarrollada como proyecto de perfil de egreso (Duoc UC, APT122), orientada a la automatización e interpretación en tiempo real de comandos de voz, procesamiento de lenguaje natural (NLP) y aprendizaje continuo de rutinas diarias.

---

## 🚀 Inicio Rápido para Evaluadores y Terceros

Este proyecto está optimizado para que cualquier persona que lo descargue o clone pueda ejecutarlo de inmediato sin requerir configuración compleja, compiladores de C++, servidores externos o dependencias nativas conflictivas.

### Requisitos Previos
- **Node.js**: Versión 18, 20 o 22 (LTS recomendada). Descargar desde [nodejs.org](https://nodejs.org/).

---

### Opción 1: En Windows (Ejecución en 1 Clic)
1. Descarga o clona este repositorio.
2. Haz doble clic en el archivo **`start.bat`**.
3. El script detectará Node.js, instalará las dependencias automáticamente si es la primera vez y abrirá `http://localhost:3000` en tu navegador.

---

### Opción 2: Desde Terminal (Windows / Linux / macOS)
1. Clona el repositorio e ingresa a la carpeta:
   ```bash
   git clone https://github.com/FelipeFPiponn/Prototipo-Vanshee.git
   cd Prototipo-Vanshee
   ```
2. Instala las dependencias:
   ```bash
   npm install
   ```
3. Inicia el servidor de desarrollo:
   ```bash
   npm run dev
   ```
4. Abre tu navegador en **`http://localhost:3000`**.

---

## 🛠️ ¿Por qué esta solución resuelve los problemas de instalación de terceros?

En prototipos tradicionales de Python con librerías nativas suelen presentarse múltiples fallos al compartirse con terceros:
1. **Compiladores C++ y DLLs**: Librerías como `faster-whisper` y `ctranslate2` requieren herramientas de compilación de Microsoft Visual C++ y CUDA que la mayoría de los usuarios no tienen instaladas.
2. **Dependencias del Sistema Operativo**: Paquetes como `pywin32` impiden la instalación en computadores con macOS o Linux.
3. **Drivers de Audio y PortAudio**: Librerías como `PyAudio` o `sounddevice` fallan si faltan controladores de audio o librerías dinámicas locales.
4. **Dependencia de Servidores Locales**: Modelos que exigen tener un daemon de `ollama` corriendo con modelos descargados de varios gigabytes fallan si el usuario no tiene Ollama configurado.

**Solución implementada en V.ANSHEE:**
- **STT en Tiempo Real**: Integración directa con la API de reconocimiento de voz del navegador (Web Speech API) con micrófono en vivo y captura de baja latencia sin drivers adicionales.
- **Motor NLU Híbrido**: Funciona **100% de manera autónoma y offline** mediante el parser determinista que replica el esquema `intents_schema.json`, y además soporta opcionalmente modelos LLM (Google Gemini) configurando la variable de entorno en `.env`.
- **Portabilidad Universal**: Ejecutable en Windows, macOS y Linux en cualquier navegador moderno.

---

## 📐 Arquitectura del Sistema (4 Capas)

```
        [ Entrada de Audio / Micrófono ] 
                       │
                       ▼
        [ Módulo STT (Speech-to-Text) ] 
                       │
                       ▼
        [ Motor NLP / NLU Parser ] ──── (Interpretación de Intención y Pasos)
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
        [ Dispatcher de OS / Resolver ]   [ Engine de Rutinas / ML ]
        (Ejecución y Mapeo de Targets)    (Análisis de Patrones y Hábito)
```

1. **Capa 1: Captura & Transcripción (STT)**: Transforma la señal de voz del usuario en texto estructurado en tiempo real con indicador visual de escucha.
2. **Capa 2: Interpretación Semántica (NLP)**: Modela la intención (`OPEN_APP`, `CREATE_PROJECT`, `SYSTEM_CONTROL`, `FORGET_COMMAND`), identifica entidades (aplicaciones, parámetros) y descompone comandos encadenados.
3. **Capa 3: Capa de Despacho (OS Dispatcher & Dynamic Resolver)**:
   - Resuelve software nativo y servicios web frecuentes (`KNOWN_TARGETS`).
   - Memoria dinámica (`learned_commands`) para enseñar nuevos atajos con palabras clave personalizadas.
   - Generador de proyectos de desarrollo (`python`, `node`, `react`, `csharp`).
4. **Capa 4: Módulo de Rutinas y Aprendizaje (HabitEngine)**:
   - Registro de histórico con estampas temporales, día de la semana (`day_of_week`) y hora (`hour_of_day`).
   - Detección de patrones: si un comando se repite 3 o más veces en el mismo bloque horario, se consolida como rutina sugerida.
   - Gráfico de distribución de 24 horas y disparador de sugerencias en tiempo real.

---

## 🧪 Ejemplos de Prueba Recomendados

Puedes probar los siguientes comandos mediante voz o escribiéndolos en la consola:

- **Comando encadenado de desarrollo:**
  > *"ejecuta vs code e inicia un nuevo proyecto python llamado mi_api"*
  - *Resultado:* Descompone en 2 pasos: Apertura de VS Code y generación de la estructura del proyecto `mi_api`.

- **Comando encadenado de servicios:**
  > *"abrir chat gpt y spotify"*
  - *Resultado:* Resuelve ambos accesos mediante el Dynamic Resolver y los abre simultáneamente.

- **Comando de sistema y herramientas:**
  > *"ejecutar terminal y abrir github"*

- **Memoria dinámica (Olvidar comando):**
  > *"olvida spotify"*

- **Prueba del Motor de Hábitos:**
  - Ve a la pestaña **Motor de Hábitos** para observar las rutinas detectadas y el gráfico de 24 horas. Puedes pulsar **"Probar patrón x3"** para ver al motor identificar un hábito en tiempo real.

---

## ⚙️ Configuración Opcional (`.env`)

El sistema funciona de forma nativa sin ninguna API key. Si deseas activar el parseo avanzado con Gemini:
1. Copia `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
2. Añade tu API Key de Gemini:
   ```env
   GEMINI_API_KEY=tu_clave_aqui
   ```

---

## 👨‍💻 Autores
- Proyecto APT122 — Duoc UC
