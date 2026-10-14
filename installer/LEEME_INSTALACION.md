# ⚡ V.ANSHEE Core - Instalador Autónomo Offline para Windows

Este paquete contiene la instalación completa, autónoma e independiente de **V.ANSHEE Core** para ejecutarse en cualquier computadora con **Windows 10 u 11 (64-bit)** sin requerir conexión a internet ni descargas adicionales de ningún tipo.

---

## 🎯 Modalidades de Instalación

### Modalidad 1: Aplicación Autónoma / Usuario Final (Recomendada)
**No requiere instalar Python.** Incluye todo el entorno compilado, librerías, interfaz HUD cyberpunk, servicio de IA Ollama y modelos neuronales offline.

1. Conecta la memoria USB o copia esta carpeta a la computadora destino.
2. Abre la carpeta y haz doble clic en:
   ```cmd
   Instalar_Vanshee.bat
   ```
3. El asistente realizará en cuestión de segundos:
   - ✅ Verificación de arquitectura de 64 bits.
   - ✅ Instalación silenciosa del motor de IA local **Ollama**.
   - ✅ Despliegue de los modelos neuronales **Llama 3.2** (100% offline).
   - ✅ Despliegue del motor de reconocimiento por voz **Faster-Whisper (Medium)** en español.
   - ✅ Despliegue de ejecutables y librerías compiladas de V.ANSHEE.
   - ✅ Creación de accesos directos en el **Escritorio** y en el **Menú Inicio**.

Para iniciar la aplicación:
- Haz doble clic en el acceso directo **Vanshee** en tu Escritorio o búscalo en el Menú Inicio.

---

### Modalidad 2: Entorno de Desarrollo (Código Fuente en Python)
Si en la otra computadora deseas modificar el código fuente con Python en lugar de usar el ejecutable compilado:

1. Asegúrate de tener Python 3.10 o superior instalado en esa computadora.
2. Haz doble clic en:
   ```cmd
   install_dev_offline.bat
   ```
3. Este script creará un entorno virtual `.venv` e instalará todas las librerías desde la carpeta local `offline_wheels\` sin conectarse a internet.

---

## 🗑️ Desinstalación Limpia

Si alguna vez deseas desinstalar V.ANSHEE y sus accesos directos:
- Haz doble clic en **Desinstalar_Vanshee.bat**.

---

## 📦 Estructura del Paquete Offline

- `Instalar_Vanshee.bat` : Asistente de instalación automática en 1 clic.
- `Desinstalar_Vanshee.bat` : Script de desinstalación limpia.
- `install_dev_offline.bat` : Instalador de entorno virtual Python para desarrolladores.
- `app/` : Aplicación standalone completa (ejecutable, runtime, consola HUD).
- `models/whisper/` : Modelo neuronal Faster-Whisper precargado para voz.
- `ollama/` : Instalador oficial de Ollama y modelos Llama 3.2 offline.
- `offline_wheels/` : Repositorio local de todas las ruedas (.whl) de Python.
- `engine/` : Motor PowerShell con gestión de permisos y accesos directos.
