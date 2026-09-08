#!/usr/bin/env bash
echo "========================================================"
echo "      V.ANSHEE - Sistema Inteligente de Control por Voz"
echo "========================================================"
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js no está instalado."
    echo "Por favor instala Node.js 18+ desde https://nodejs.org/"
    exit 1
fi

echo "[1/3] Node.js detectado: $(node -v)"

# Install dependencies if not present
if [ ! -d "node_modules" ]; then
    echo "[2/3] Instalando dependencias con npm install..."
    npm install
else
    echo "[2/3] Dependencias ya instaladas."
fi

# Run application
echo "[3/3] Iniciando V.ANSHEE Core en http://localhost:3000..."
npm run dev
