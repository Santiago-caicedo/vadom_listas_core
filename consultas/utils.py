"""Utilidades compartidas del módulo de consultas."""
from django.utils import timezone


def periodo_cupo():
    """
    Info del periodo mensual de cupo (mes calendario, hora local America/Bogota).
    El cupo se reinicia el 1° del mes siguiente a las 00:00.
    Devuelve: reinicio (datetime), dias_restantes (int), horas_restantes (int).
    """
    ahora = timezone.localtime()
    year, month = ahora.year, ahora.month
    if month == 12:
        year, month = year + 1, 1
    else:
        month = month + 1
    reinicio = ahora.replace(year=year, month=month, day=1,
                             hour=0, minute=0, second=0, microsecond=0)
    delta = reinicio - ahora
    return {
        'reinicio': reinicio,
        'dias_restantes': delta.days,
        'horas_restantes': delta.seconds // 3600,
    }
