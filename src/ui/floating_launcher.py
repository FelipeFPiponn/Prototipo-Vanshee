import os
import sys
import threading
import time
import urllib.request
import tkinter as tk
from typing import Optional

def get_primary_work_area():
    """Retorna las coordenadas del área de trabajo disponible (restando la barra de tareas de Windows)."""
    try:
        import win32api
        import win32con
        hmon = win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
        info = win32api.GetMonitorInfo(hmon)
        work = info.get("work", (0, 0, 1920, 1040))
        return work[0], work[1], work[2], work[3]
    except Exception:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            return 0, 0, sw, max(600, sh - 48)
        except Exception:
            return 0, 0, 1920, 1040

class FloatingLauncherBubble:
    """Widget de escritorio flotante circular nativo (círculo perfecto y semi-transparente con clic responsivo)."""

    def __init__(self, api_url: str = "http://127.0.0.1:8000"):
        self.api_url = api_url
        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None
        self.size = 64
        
        # Coordenadas de arrastre y estado
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.win_start_x = 0
        self.win_start_y = 0
        self.is_dragged = False
        self.is_hovered = False
        
        # Opacidad translúcida
        self.idle_alpha = 0.82
        self.hover_alpha = 0.98
        self.last_toggle_time = 0.0

    def start(self):
        """Inicia el bucle de la burbuja flotante."""
        wx, wy, wr, wb = get_primary_work_area()
        
        # Posición inicial: esquina inferior derecha, flotando 24px arriba de la barra de tareas
        x = max(wx, wr - self.size - 24)
        y = max(wy, wb - self.size - 24)

        self.root = tk.Tk()
        self.root.title("Vanshee Bubble")
        
        # Eliminar barra de título y bordes de ventana del SO
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Clave de color para transparencia total (los píxeles con este color serán 100% click-through e invisibles)
        trans_color = "#010101"
        self.root.attributes("-transparentcolor", trans_color)
        self.root.attributes("-alpha", self.idle_alpha)
        self.root.config(bg=trans_color)
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")

        # Canvas para dibujar el círculo exacto
        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size,
            bg=trans_color,
            highlightthickness=0,
            cursor="hand2"
        )
        self.canvas.pack(fill="both", expand=True)

        # Dibujar la burbuja
        self._render_bubble()

        # Enlazar eventos de ratón (clic, arrastre y hover) tanto al canvas como a la raíz
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Button-3>", self._show_context_menu)

        self.root.mainloop()

    def _render_bubble(self):
        """Dibuja el círculo con estilo cyberpunk oscuro semi-transparente y halo cian brillante."""
        if not self.canvas:
            return
        self.canvas.delete("all")
        
        ring_color = "#38bdf8" if self.is_hovered else "#00d2ff"
        ring_width = 3 if self.is_hovered else 2
        bg_fill = "#162032" if self.is_hovered else "#0d111a"

        # 1. Círculo base oscuro semi-transparente
        self.canvas.create_oval(
            3, 3, self.size - 3, self.size - 3,
            fill=bg_fill,
            outline=ring_color,
            width=ring_width
        )
        
        # 2. Anillo interior suave
        self.canvas.create_oval(
            6, 6, self.size - 6, self.size - 6,
            fill="",
            outline="#0369a1",
            width=1
        )

        # 3. Icono central ⚡
        self.canvas.create_text(
            self.size // 2,
            self.size // 2 - 1,
            text="⚡",
            font=("Segoe UI Emoji", 20, "bold"),
            fill="#38bdf8" if self.is_hovered else "#00d2ff"
        )

        # 4. Indicador de estado (Punto verde Online)
        self.canvas.create_oval(
            self.size - 18, 4, self.size - 6, 16,
            fill="#10b981",
            outline="#0d111a",
            width=2
        )

    def _on_enter(self, event=None):
        self.is_hovered = True
        try:
            if self.root:
                self.root.attributes("-alpha", self.hover_alpha)
        except Exception:
            pass
        self._render_bubble()

    def _on_leave(self, event=None):
        self.is_hovered = False
        try:
            if self.root:
                self.root.attributes("-alpha", self.idle_alpha)
        except Exception:
            pass
        self._render_bubble()

    def _on_press(self, event):
        self.is_dragged = False
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        if self.root:
            self.win_start_x = self.root.winfo_x()
            self.win_start_y = self.root.winfo_y()

    def _on_drag(self, event):
        dx = event.x_root - self.drag_start_x
        dy = event.y_root - self.drag_start_y
        if abs(dx) > 4 or abs(dy) > 4:
            self.is_dragged = True
            if self.root:
                new_x = self.win_start_x + dx
                new_y = self.win_start_y + dy
                self.root.geometry(f"+{new_x}+{new_y}")

    def _on_release(self, event):
        # Si fue un clic simple sin desplazamiento notable, alternar la ventana de chat
        if not self.is_dragged:
            self.toggle_chat()

    def _show_context_menu(self, event):
        """Menú contextual con clic derecho sobre la burbuja."""
        menu = tk.Menu(self.root, tearoff=0, bg="#0d111a", fg="#ffffff", activebackground="#0284c7")
        menu.add_command(label="💬 Abrir / Ocultar Chat", command=self.toggle_chat)
        menu.add_separator()
        menu.add_command(label="❌ Cerrar Vanshee por completo", command=self._shutdown_app)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _shutdown_app(self):
        def _call():
            try:
                req = urllib.request.Request(
                    f"{self.api_url}/api/system/shutdown",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=1.5):
                    pass
            except Exception:
                import os
                os._exit(0)
        threading.Thread(target=_call, daemon=True).start()

    def toggle_chat(self):
        """Alterna la visibilidad de la ventana de chat evitando llamadas duplicadas."""
        now = time.time()
        if (now - self.last_toggle_time) < 0.45:
            return
        self.last_toggle_time = now

        def _call():
            try:
                req = urllib.request.Request(
                    f"{self.api_url}/api/window/toggle_chat",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=1.5):
                    pass
            except Exception as e:
                print(f"[Bubble Toggle Chat Error] {e}")

        threading.Thread(target=_call, daemon=True).start()

    def destroy(self):
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
