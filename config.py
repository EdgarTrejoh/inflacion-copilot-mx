from datetime import date

# =========================
# LÍMITES DE FECHA
# =========================
MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2026, 2, 1)

def get_date_limits():
    """Retorna los límites de fecha permitidos como un diccionario."""
    return {
        "MIN_DATE": MIN_DATE,
        "MAX_DATE": MAX_DATE
    }
