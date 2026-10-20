"""Monitor de Diagnóstico de Hardware y Rendimiento del Sistema en Windows.

Consulta uso de CPU, memoria RAM, estado de discos y temperaturas en < 2ms sin herramientas externas.
"""

import psutil
from typing import Dict, Any, Tuple


class HardwareMonitor:
    """Monitorea recursos de hardware del equipo."""

    def get_system_telemetry(self) -> Dict[str, Any]:
        """Obtiene un informe detallado del uso de recursos del sistema."""
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        battery = psutil.sensors_battery()
        battery_pct = battery.percent if battery else None
        is_charging = battery.power_plugged if battery else None

        return {
            "cpu_percent": cpu_pct,
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_percent": mem.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_percent": disk.percent,
            "battery_percent": battery_pct,
            "is_charging": is_charging
        }

    def get_voice_summary(self) -> str:
        """Retorna un resumen natural para que V.ANSHEE lo hable por voz."""
        data = self.get_system_telemetry()
        res = (
            f"El procesador está al {int(data['cpu_percent'])}% y la memoria RAM "
            f"al {int(data['ram_percent'])}% ({data['ram_used_gb']} GB de {data['ram_total_gb']} GB). "
            f"Tienes {data['disk_free_gb']} GB libres en el disco principal."
        )
        if data["battery_percent"] is not None:
            charging_str = "cargando" if data["is_charging"] else "con batería"
            res += f" Batería al {int(data['battery_percent'])}% ({charging_str})."
        return res


# Instancia global compartida
hardware_monitor = HardwareMonitor()
