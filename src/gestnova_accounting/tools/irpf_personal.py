"""IRPF Personal — Declaracion de la Renta wizard + calculo + deducciones por CCAA.

Permite al agente guiar al usuario paso a paso para preparar su declaracion,
calcular el resultado, y explicar todas las deducciones aplicables.

Cubre las 17 CCAA + Ceuta y Melilla. Pais Vasco y Navarra se marcan como
regimen foral (sus haciendas forales aplican normativa diferente).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from ._base import BaseTool

# ── Disclaimer legal (se incluye en todas las respuestas) ───────────────────
DISCLAIMER = (
    "Esta informacion es asistencia educativa basada en legislacion vigente. "
    "NO sustituye asesoria fiscal profesional. La veracidad de la declaracion "
    "es responsabilidad del contribuyente."
)

# ── CCAA con regimen foral ──────────────────────────────────────────────────
REGIMEN_FORAL: set[str] = {"pais_vasco", "navarra"}

# ── Todas las CCAA soportadas ───────────────────────────────────────────────
ALL_CCAA: list[str] = [
    "andalucia", "aragon", "asturias", "baleares", "canarias", "cantabria",
    "castilla_la_mancha", "castilla_y_leon", "cataluna", "extremadura",
    "galicia", "la_rioja", "madrid", "murcia", "navarra", "pais_vasco",
    "valencia", "ceuta", "melilla",
]

# ── IRPF Tramos Estatales 2024/2025 ──────────────────────────────────────────
TRAMOS_ESTATALES = [
    (0, 12450, 0.095),
    (12450, 20200, 0.12),
    (20200, 35200, 0.15),
    (35200, 60000, 0.185),
    (60000, 300000, 0.225),
    (300000, float("inf"), 0.245),
]

# ── Tramos autonomicos (17 CCAA + Ceuta/Melilla + default) ──────────────────
TRAMOS_AUTONOMICOS: dict[str, list[tuple[float, float, float]]] = {
    "andalucia": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 28000, 0.15),
        (28000, 35200, 0.155),
        (35200, 50000, 0.185),
        (50000, 60000, 0.19),
        (60000, 120000, 0.23),
        (120000, float("inf"), 0.245),
    ],
    "aragon": [
        (0, 12450, 0.10),
        (12450, 20200, 0.125),
        (20200, 34000, 0.155),
        (34000, 50000, 0.19),
        (50000, 60000, 0.215),
        (60000, 70000, 0.225),
        (70000, 90000, 0.235),
        (90000, 130000, 0.245),
        (130000, 150000, 0.25),
        (150000, float("inf"), 0.255),
    ],
    "asturias": [
        (0, 12450, 0.10),
        (12450, 17707, 0.12),
        (17707, 33007, 0.14),
        (33007, 53407, 0.185),
        (53407, 70000, 0.215),
        (70000, 90000, 0.225),
        (90000, 175000, 0.245),
        (175000, float("inf"), 0.255),
    ],
    "baleares": [
        (0, 10000, 0.095),
        (10000, 18000, 0.115),
        (18000, 30000, 0.145),
        (30000, 48000, 0.175),
        (48000, 70000, 0.20),
        (70000, 90000, 0.225),
        (90000, 120000, 0.235),
        (120000, 175000, 0.245),
        (175000, float("inf"), 0.25),
    ],
    "canarias": [
        (0, 12450, 0.09),
        (12450, 17707, 0.115),
        (17707, 33007, 0.14),
        (33007, 53407, 0.185),
        (53407, 90000, 0.235),
        (90000, float("inf"), 0.24),
    ],
    "cantabria": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.15),
        (35200, 46000, 0.175),
        (46000, 60000, 0.19),
        (60000, 90000, 0.235),
        (90000, float("inf"), 0.255),
    ],
    "castilla_la_mancha": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.15),
        (35200, 60000, 0.185),
        (60000, float("inf"), 0.225),
    ],
    "castilla_y_leon": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.145),
        (35200, 53407, 0.185),
        (53407, float("inf"), 0.215),
    ],
    "cataluna": [
        (0, 12450, 0.105),
        (12450, 17707, 0.12),
        (17707, 33007, 0.15),
        (33007, 53407, 0.175),
        (53407, 90000, 0.21),
        (90000, 120000, 0.235),
        (120000, 175000, 0.245),
        (175000, float("inf"), 0.255),
    ],
    "extremadura": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.155),
        (35200, 60000, 0.19),
        (60000, 80000, 0.235),
        (80000, 100000, 0.245),
        (100000, float("inf"), 0.25),
    ],
    "galicia": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.145),
        (35200, 60000, 0.185),
        (60000, float("inf"), 0.225),
    ],
    "la_rioja": [
        (0, 12450, 0.09),
        (12450, 20200, 0.115),
        (20200, 35200, 0.14),
        (35200, 50000, 0.185),
        (50000, 65000, 0.19),
        (65000, 80000, 0.235),
        (80000, float("inf"), 0.255),
    ],
    "madrid": [
        (0, 12961, 0.085),
        (12961, 18592, 0.109),
        (18592, 33636, 0.128),
        (33636, 53407, 0.179),
        (53407, float("inf"), 0.21),
    ],
    "murcia": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.145),
        (35200, 60000, 0.185),
        (60000, float("inf"), 0.235),
    ],
    "navarra": [],  # REGIMEN FORAL — no soportado en v1
    "pais_vasco": [
        (0, 15795, 0.23),
        (15795, 31590, 0.28),
        (31590, 47386, 0.35),
        (47386, 78630, 0.40),
        (78630, 130424, 0.45),
        (130424, float("inf"), 0.49),
    ],
    "valencia": [
        (0, 12450, 0.10),
        (12450, 17000, 0.12),
        (17000, 30000, 0.14),
        (30000, 50000, 0.18),
        (50000, 65000, 0.225),
        (65000, 80000, 0.24),
        (80000, 140000, 0.245),
        (140000, float("inf"), 0.255),
    ],
    "ceuta": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.15),
        (35200, 60000, 0.185),
        (60000, float("inf"), 0.225),
    ],
    "melilla": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.15),
        (35200, 60000, 0.185),
        (60000, float("inf"), 0.225),
    ],
    "default": [
        (0, 12450, 0.095),
        (12450, 20200, 0.12),
        (20200, 35200, 0.15),
        (35200, 60000, 0.185),
        (60000, float("inf"), 0.225),
    ],
}

# ── Deducciones estatales ────────────────────────────────────────────────────
DEDUCCIONES_ESTATALES = {
    "minimo_personal": {"amount": 5550, "description": "Minimo personal exento"},
    "minimo_descendientes_1": {"amount": 2400, "description": "1er hijo menor de 25 anios"},
    "minimo_descendientes_2": {"amount": 2700, "description": "2o hijo"},
    "minimo_descendientes_3": {"amount": 4000, "description": "3er hijo"},
    "minimo_descendientes_4": {"amount": 4500, "description": "4o hijo y sucesivos"},
    "hijo_menor_3": {"amount": 2800, "description": "Adicional por hijo menor de 3 anios"},
    "discapacidad_33_65": {"amount": 3000, "description": "Discapacidad 33-65%"},
    "discapacidad_65_plus": {"amount": 12000, "description": "Discapacidad >65%"},
    "ascendientes_65": {"amount": 1150, "description": "Ascendiente mayor de 65 anios conviviente"},
    "ascendientes_75": {"amount": 1400, "description": "Ascendiente mayor de 75 anios"},
    "plan_pensiones": {"max": 1500, "description": "Aportacion a plan de pensiones (max 1.500 EUR)"},
    "vivienda_habitual_pre2013": {
        "percent": 0.15,
        "max": 9040,
        "description": "Deduccion vivienda habitual (hipoteca anterior a 2013)",
    },
    "maternidad": {"amount": 1200, "description": "Deduccion por maternidad (hijos < 3 anios, madre trabajadora)"},
    "familia_numerosa": {"amount": 1200, "description": "Familia numerosa general"},
    "familia_numerosa_especial": {"amount": 2400, "description": "Familia numerosa especial"},
}

# ── Deducciones por CCAA (las mas relevantes) ────────────────────────────────
DEDUCCIONES_CCAA: dict[str, list[dict[str, Any]]] = {
    "andalucia": [
        {
            "id": "alquiler_vivienda",
            "amount": 500,
            "condition": "Alquiler vivienda habitual (menores 35 o mayores 65)",
            "max_renta": 19000,
        },
        {"id": "nacimiento_adopcion", "amount": 200, "condition": "Por nacimiento o adopcion de hijo"},
        {"id": "discapacidad_autonomica", "amount": 150, "condition": "Por discapacidad del contribuyente (>=33%)"},
        {
            "id": "inversiones_empresariales",
            "percent": 0.20,
            "condition": "Inversiones en empresas de nueva creacion",
            "max": 4000,
        },
    ],
    "aragon": [
        {"id": "alquiler_vivienda", "amount": 455, "condition": "Alquiler vivienda habitual", "max_renta": 15000},
        {"id": "nacimiento_adopcion", "amount": 500, "condition": "Por nacimiento o adopcion"},
    ],
    "asturias": [
        {
            "id": "alquiler_vivienda",
            "percent": 0.10,
            "condition": "Alquiler vivienda habitual (< 35 anios)",
            "max": 455,
            "max_renta": 22000,
        },
        {"id": "nacimiento_adopcion", "amount": 300, "condition": "Por nacimiento o adopcion"},
    ],
    "baleares": [
        {
            "id": "alquiler_vivienda",
            "percent": 0.15,
            "condition": "Alquiler vivienda habitual (< 36 anios)",
            "max": 400,
            "max_renta": 20000,
        },
        {"id": "nacimiento_adopcion", "amount": 400, "condition": "Por nacimiento o adopcion"},
    ],
    "canarias": [
        {"id": "alquiler_vivienda", "amount": 500, "condition": "Alquiler vivienda habitual", "max_renta": 20000},
        {"id": "nacimiento_adopcion", "amount": 200, "condition": "Por nacimiento o adopcion"},
        {"id": "gastos_estudios", "amount": 1500, "condition": "Gastos de estudios universitarios fuera de la isla"},
    ],
    "cantabria": [],  # Consultar normativa autonomica vigente
    "castilla_la_mancha": [],  # Consultar normativa autonomica vigente
    "castilla_y_leon": [
        {"id": "nacimiento_adopcion", "amount": 710, "condition": "Por nacimiento o adopcion (1er hijo)"},
        {"id": "nacimiento_adopcion_2", "amount": 1420, "condition": "Por nacimiento o adopcion (2o hijo+)"},
    ],
    "cataluna": [
        {
            "id": "alquiler_vivienda",
            "percent": 0.10,
            "condition": "Alquiler vivienda habitual",
            "max": 300,
            "max_renta": 20000,
        },
        {"id": "nacimiento_adopcion", "amount": 150, "condition": "Por nacimiento o adopcion"},
        {"id": "donaciones_entidades", "percent": 0.15, "condition": "Donaciones a entidades catalanas"},
        {
            "id": "rehabilitacion_vivienda",
            "percent": 0.015,
            "condition": "Rehabilitacion vivienda habitual",
            "max": 9040,
        },
    ],
    "extremadura": [
        {"id": "alquiler_vivienda", "amount": 300, "condition": "Alquiler vivienda habitual (< 36 anios)", "max_renta": 19000},
        {"id": "nacimiento_adopcion", "amount": 300, "condition": "Por nacimiento o adopcion"},
    ],
    "galicia": [
        {
            "id": "alquiler_vivienda",
            "percent": 0.10,
            "condition": "Alquiler vivienda habitual (< 35 anios)",
            "max": 300,
            "max_renta": 22000,
        },
        {"id": "nacimiento_adopcion", "amount": 360, "condition": "Por nacimiento o adopcion"},
    ],
    "la_rioja": [
        {"id": "nacimiento_adopcion", "amount": 600, "condition": "Por nacimiento o adopcion (1er hijo)"},
        {"id": "nacimiento_adopcion_2", "amount": 750, "condition": "Por nacimiento o adopcion (2o hijo)"},
        {"id": "nacimiento_adopcion_3", "amount": 900, "condition": "Por nacimiento o adopcion (3er hijo+)"},
    ],
    "madrid": [
        {
            "id": "alquiler_vivienda",
            "percent": 0.30,
            "condition": "Alquiler vivienda habitual (< 25 o > 65 anios)",
            "max": 1000,
            "max_renta": 25620,
        },
        {"id": "nacimiento_adopcion", "amount": 600, "condition": "Por nacimiento o adopcion (1er hijo)"},
        {"id": "nacimiento_adopcion_2", "amount": 750, "condition": "Por nacimiento o adopcion (2o hijo)"},
        {"id": "nacimiento_adopcion_3", "amount": 900, "condition": "Por nacimiento o adopcion (3er hijo+)"},
        {"id": "gastos_educativos", "percent": 0.15, "condition": "Gastos educativos (uniformes, idiomas)", "max": 400},
        {"id": "cuidado_hijos_3", "percent": 0.20, "condition": "Gastos guarderia hijos < 3 anios", "max": 1000},
    ],
    "murcia": [
        {"id": "alquiler_vivienda", "amount": 300, "condition": "Alquiler vivienda habitual (< 35 anios)", "max_renta": 24000},
        {"id": "nacimiento_adopcion", "amount": 200, "condition": "Por nacimiento o adopcion"},
    ],
    "navarra": [],  # REGIMEN FORAL — normativa propia
    "pais_vasco": [],  # REGIMEN FORAL — normativa propia
    "valencia": [
        {
            "id": "alquiler_vivienda",
            "percent": 0.15,
            "condition": "Alquiler vivienda habitual (< 35 anios)",
            "max": 550,
        },
        {"id": "nacimiento_adopcion_1", "amount": 270, "condition": "Por nacimiento o adopcion (1er hijo)"},
        {"id": "nacimiento_adopcion_2", "amount": 550, "condition": "2o hijo"},
        {"id": "nacimiento_adopcion_3", "amount": 800, "condition": "3er hijo+"},
        {"id": "material_escolar", "amount": 100, "condition": "Material escolar por hijo"},
        {
            "id": "eficiencia_energetica",
            "percent": 0.20,
            "condition": "Obras eficiencia energetica vivienda",
            "max": 5000,
        },
    ],
    "ceuta": [],  # Bonificacion del 60% en cuota — ver calculo especial
    "melilla": [],  # Bonificacion del 60% en cuota — ver calculo especial
}


# ── Wizard state ─────────────────────────────────────────────────────────────
@dataclass
class IRPFWizardState:
    """State for an ongoing IRPF wizard session."""

    session_id: str = ""
    step: int = 0
    ejercicio: int = 2025  # Fiscal year (default: current)
    ccaa: str = ""
    situacion_personal: str = ""  # soltero, casado, viudo, separado
    hijos: int = 0
    hijos_menores_3: int = 0
    ascendientes_65: int = 0
    discapacidad: str = "none"  # none, 33-65, 65+
    ingresos_brutos: float = 0
    retenciones_pagadas: float = 0
    cotizaciones_ss: float = 0
    otros_rendimientos: float = 0  # alquileres, dividendos
    hipoteca_pre2013: float = 0
    alquiler_anual: float = 0
    plan_pensiones: float = 0
    gastos_deducibles_autonomo: float = 0
    es_autonomo: bool = False
    es_madre_trabajadora: bool = False
    familia_numerosa: str = "none"  # none, general, especial
    donaciones: float = 0
    gastos_educativos: float = 0
    completed: bool = False
    results: dict = field(default_factory=dict)


# ── Core calculation ─────────────────────────────────────────────────────────


def calculate_irpf(state: IRPFWizardState) -> dict:
    """Calculate IRPF based on wizard inputs."""
    # 0. Check foral regime
    if state.ccaa in REGIMEN_FORAL:
        return {
            "error": True,
            "message": (
                f"La CCAA {state.ccaa} tiene regimen foral propio. "
                "Sus haciendas forales (Bizkaia, Gipuzkoa, Alava para Pais Vasco; "
                "Navarra) aplican normativa diferente al regimen comun. "
                "Este asistente actualmente solo cubre el regimen comun. "
                "Consulta con tu hacienda foral."
            ),
            "regimen": "foral",
            "ccaa": state.ccaa,
            "ejercicio": state.ejercicio,
            "disclaimer": DISCLAIMER,
        }

    # 1. Base imponible
    base = state.ingresos_brutos - state.cotizaciones_ss - state.gastos_deducibles_autonomo
    if base < 0:
        base = 0

    # 2. Minimo personal y familiar
    minimo = DEDUCCIONES_ESTATALES["minimo_personal"]["amount"]
    for i in range(state.hijos):
        key = f"minimo_descendientes_{min(i + 1, 4)}"
        minimo += DEDUCCIONES_ESTATALES[key]["amount"]
    if state.hijos_menores_3 > 0:
        minimo += DEDUCCIONES_ESTATALES["hijo_menor_3"]["amount"] * state.hijos_menores_3
    if state.ascendientes_65 > 0:
        minimo += DEDUCCIONES_ESTATALES["ascendientes_65"]["amount"] * state.ascendientes_65
    if state.discapacidad == "33-65":
        minimo += DEDUCCIONES_ESTATALES["discapacidad_33_65"]["amount"]
    elif state.discapacidad == "65+":
        minimo += DEDUCCIONES_ESTATALES["discapacidad_65_plus"]["amount"]

    # 3. Base liquidable
    base_liquidable = max(0, base - minimo)

    # 4. Plan de pensiones
    deduccion_pp = min(state.plan_pensiones, DEDUCCIONES_ESTATALES["plan_pensiones"]["max"])
    base_liquidable = max(0, base_liquidable - deduccion_pp)

    # 5. Cuota estatal
    cuota_estatal = _apply_tramos(base_liquidable, TRAMOS_ESTATALES)

    # 6. Cuota autonomica
    tramos_ccaa = TRAMOS_AUTONOMICOS.get(state.ccaa, TRAMOS_AUTONOMICOS["default"])
    cuota_autonomica = _apply_tramos(base_liquidable, tramos_ccaa)

    # 7. Cuota total
    cuota_integra = cuota_estatal + cuota_autonomica

    # 8. Deducciones
    deducciones: list[dict[str, Any]] = []
    total_deducciones = 0.0

    # Vivienda pre-2013
    if state.hipoteca_pre2013 > 0:
        d = min(state.hipoteca_pre2013, DEDUCCIONES_ESTATALES["vivienda_habitual_pre2013"]["max"])
        amount = d * DEDUCCIONES_ESTATALES["vivienda_habitual_pre2013"]["percent"]
        deducciones.append(
            {"concepto": "Vivienda habitual (hipoteca pre-2013)", "amount": round(amount, 2), "base_legal": "DT 18a Ley IRPF"}
        )
        total_deducciones += amount

    # Maternidad
    if state.es_madre_trabajadora and state.hijos_menores_3 > 0:
        amount = DEDUCCIONES_ESTATALES["maternidad"]["amount"]
        deducciones.append({"concepto": "Maternidad", "amount": amount, "base_legal": "Art. 81 Ley IRPF"})
        total_deducciones += amount

    # Familia numerosa
    if state.familia_numerosa == "general":
        amount = DEDUCCIONES_ESTATALES["familia_numerosa"]["amount"]
        deducciones.append({"concepto": "Familia numerosa", "amount": amount, "base_legal": "Art. 81 bis Ley IRPF"})
        total_deducciones += amount
    elif state.familia_numerosa == "especial":
        amount = DEDUCCIONES_ESTATALES["familia_numerosa_especial"]["amount"]
        deducciones.append(
            {"concepto": "Familia numerosa especial", "amount": amount, "base_legal": "Art. 81 bis Ley IRPF"}
        )
        total_deducciones += amount

    # Deducciones CCAA
    ccaa_deds = DEDUCCIONES_CCAA.get(state.ccaa, [])
    for ded in ccaa_deds:
        if "alquiler" in ded["id"] and state.alquiler_anual > 0:
            if "percent" in ded:
                amount = min(state.alquiler_anual * ded["percent"], ded.get("max", 99999))
            else:
                amount = ded.get("amount", 0)
            deducciones.append(
                {
                    "concepto": f"CCAA {state.ccaa}: {ded['condition']}",
                    "amount": round(amount, 2),
                    "base_legal": f"Ley IRPF {state.ccaa}",
                }
            )
            total_deducciones += amount
        elif "nacimiento" in ded["id"] and state.hijos > 0:
            amount = ded.get("amount", 0)
            deducciones.append(
                {
                    "concepto": f"CCAA {state.ccaa}: {ded['condition']}",
                    "amount": amount,
                    "base_legal": f"Ley IRPF {state.ccaa}",
                }
            )
            total_deducciones += amount

    # 9. Cuota liquida
    cuota_liquida = max(0, cuota_integra - total_deducciones)

    # 10. Resultado (a pagar o a devolver)
    resultado = cuota_liquida - state.retenciones_pagadas

    return {
        "ingresos_brutos": state.ingresos_brutos,
        "base_imponible": round(base, 2),
        "minimo_personal_familiar": round(minimo, 2),
        "base_liquidable": round(base_liquidable, 2),
        "cuota_estatal": round(cuota_estatal, 2),
        "cuota_autonomica": round(cuota_autonomica, 2),
        "cuota_integra": round(cuota_integra, 2),
        "deducciones": deducciones,
        "total_deducciones": round(total_deducciones, 2),
        "cuota_liquida": round(cuota_liquida, 2),
        "retenciones_pagadas": state.retenciones_pagadas,
        "resultado": round(resultado, 2),
        "a_devolver": resultado < 0,
        "ccaa": state.ccaa,
        "ejercicio": state.ejercicio,
        "tipo_efectivo": round((cuota_liquida / state.ingresos_brutos * 100) if state.ingresos_brutos > 0 else 0, 2),
        "reglas_aplicadas": [
            "Ley 35/2006 del IRPF",
            f"Tramos autonomicos {state.ccaa}",
            "RD 439/2007 Reglamento IRPF",
        ],
        "disclaimer": DISCLAIMER,
    }


def _apply_tramos(base: float, tramos: list) -> float:
    """Apply progressive tax brackets."""
    tax = 0.0
    for lower, upper, rate in tramos:
        if base <= lower:
            break
        taxable = min(base, upper) - lower
        tax += taxable * rate
    return tax


# ── Wizard questions ─────────────────────────────────────────────────────────
WIZARD_STEPS = [
    {
        "field": "ejercicio",
        "question": "Para que ejercicio fiscal? (ej: 2025 = declaracion que se presenta en 2026)",
        "type": "number",
        "default": 2025,
    },
    {
        "field": "ccaa",
        "question": "En que Comunidad Autonoma resides?",
        "type": "choice",
        "options": [
            "andalucia", "aragon", "asturias", "baleares", "canarias", "cantabria",
            "castilla_la_mancha", "castilla_y_leon", "cataluna", "extremadura",
            "galicia", "la_rioja", "madrid", "murcia", "navarra", "pais_vasco",
            "valencia", "ceuta", "melilla", "otra",
        ],
    },
    {
        "field": "situacion_personal",
        "question": "Cual es tu situacion personal?",
        "type": "choice",
        "options": ["soltero", "casado", "viudo", "separado"],
    },
    {
        "field": "ingresos_brutos",
        "question": "Cuales son tus ingresos brutos anuales (EUR)?",
        "type": "number",
    },
    {
        "field": "retenciones_pagadas",
        "question": "Cuanto te han retenido en total (IRPF retenido en nominas)?",
        "type": "number",
    },
    {
        "field": "cotizaciones_ss",
        "question": "Cuanto has pagado de Seguridad Social?",
        "type": "number",
    },
    {"field": "es_autonomo", "question": "Eres autonomo?", "type": "boolean"},
    {
        "field": "hijos",
        "question": "Cuantos hijos menores de 25 anios tienes?",
        "type": "number",
    },
    {
        "field": "hijos_menores_3",
        "question": "Cuantos de ellos son menores de 3 anios?",
        "type": "number",
    },
    {
        "field": "hipoteca_pre2013",
        "question": "Pagas hipoteca de vivienda habitual firmada antes de 2013? Si si, cuanto al anio?",
        "type": "number",
    },
    {
        "field": "alquiler_anual",
        "question": "Pagas alquiler? Si si, cuanto al anio?",
        "type": "number",
    },
    {
        "field": "plan_pensiones",
        "question": "Has aportado a un plan de pensiones? Cuanto?",
        "type": "number",
    },
    {
        "field": "donaciones",
        "question": "Has hecho donaciones a ONGs o entidades? Cuanto?",
        "type": "number",
    },
]


# ── In-memory wizard session store ───────────────────────────────────────────
_sessions: dict[str, IRPFWizardState] = {}


# ── MCP Tool classes ─────────────────────────────────────────────────────────


class IRPFWizardStartTool(BaseTool):
    name = "irpfWizardStart"
    description = (
        "Start an IRPF personal income tax wizard session. Returns the first "
        "question to ask the user and a session_id for follow-up calls."
    )
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        session_id = str(uuid.uuid4())[:8]
        state = IRPFWizardState(session_id=session_id, step=0)
        _sessions[session_id] = state
        step_info = WIZARD_STEPS[0]
        return {
            "session_id": session_id,
            "step": 0,
            "total_steps": len(WIZARD_STEPS),
            "question": step_info["question"],
            "field": step_info["field"],
            "type": step_info["type"],
            "options": step_info.get("options"),
            "disclaimer": DISCLAIMER,
        }


class IRPFWizardAnswerTool(BaseTool):
    name = "irpfWizardAnswer"
    description = (
        "Answer the current wizard question. Returns the next question or, "
        "if all questions are answered, the full IRPF calculation result."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Session ID from irpfWizardStart"},
            "answer": {"description": "The user's answer (string, number, or boolean depending on question type)"},
        },
        "required": ["session_id", "answer"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        sid = args["session_id"]
        if sid not in _sessions:
            return {"error": f"Session '{sid}' not found. Call irpfWizardStart first."}

        state = _sessions[sid]
        if state.completed:
            return {"error": "Session already completed.", "results": state.results}

        # Apply answer to current step
        step_info = WIZARD_STEPS[state.step]
        field_name = step_info["field"]
        answer = args["answer"]

        # Type coercion
        _INTEGER_FIELDS = {"hijos", "hijos_menores_3", "ascendientes_65", "ejercicio"}
        if step_info["type"] == "number":
            if field_name in _INTEGER_FIELDS:
                answer = int(float(answer)) if answer else 0
            else:
                answer = float(answer) if answer else 0.0
        elif step_info["type"] == "boolean":
            if isinstance(answer, str):
                answer = answer.lower() in ("true", "si", "yes", "1", "s")
        elif step_info["type"] == "choice":
            answer = str(answer).lower().strip()
            # Map "otra" to "default" for CCAA
            if field_name == "ccaa" and answer == "otra":
                answer = "default"

        setattr(state, field_name, answer)
        state.step += 1

        # Check if wizard is complete
        if state.step >= len(WIZARD_STEPS):
            state.completed = True
            state.results = calculate_irpf(state)
            return {
                "session_id": sid,
                "completed": True,
                "results": state.results,
            }

        # Return next question
        next_step = WIZARD_STEPS[state.step]
        return {
            "session_id": sid,
            "step": state.step,
            "total_steps": len(WIZARD_STEPS),
            "question": next_step["question"],
            "field": next_step["field"],
            "type": next_step["type"],
            "options": next_step.get("options"),
        }


class IRPFCalculateTool(BaseTool):
    name = "irpfCalculate"
    description = (
        "Direct IRPF calculation without the wizard flow. Provide all inputs "
        "at once and receive the full tax breakdown."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "ejercicio": {"type": "integer", "description": "Ejercicio fiscal (ej: 2025)", "default": 2025},
            "ccaa": {
                "type": "string",
                "description": (
                    "Comunidad Autonoma: andalucia, aragon, asturias, baleares, canarias, "
                    "cantabria, castilla_la_mancha, castilla_y_leon, cataluna, extremadura, "
                    "galicia, la_rioja, madrid, murcia, navarra, pais_vasco, valencia, ceuta, melilla, default"
                ),
            },
            "ingresos_brutos": {"type": "number", "description": "Ingresos brutos anuales (EUR)"},
            "retenciones_pagadas": {"type": "number", "description": "Retenciones IRPF ya pagadas"},
            "cotizaciones_ss": {"type": "number", "description": "Cotizaciones a la Seguridad Social", "default": 0},
            "hijos": {"type": "integer", "description": "Hijos menores de 25 anios", "default": 0},
            "hijos_menores_3": {"type": "integer", "description": "Hijos menores de 3 anios", "default": 0},
            "ascendientes_65": {"type": "integer", "description": "Ascendientes mayores de 65 convivientes", "default": 0},
            "discapacidad": {
                "type": "string",
                "enum": ["none", "33-65", "65+"],
                "default": "none",
            },
            "hipoteca_pre2013": {"type": "number", "description": "Pagos hipoteca pre-2013 anuales", "default": 0},
            "alquiler_anual": {"type": "number", "description": "Alquiler anual vivienda habitual", "default": 0},
            "plan_pensiones": {"type": "number", "description": "Aportacion plan de pensiones", "default": 0},
            "es_autonomo": {"type": "boolean", "default": False},
            "gastos_deducibles_autonomo": {
                "type": "number",
                "description": "Gastos deducibles de actividad autonoma",
                "default": 0,
            },
            "es_madre_trabajadora": {"type": "boolean", "default": False},
            "familia_numerosa": {
                "type": "string",
                "enum": ["none", "general", "especial"],
                "default": "none",
            },
            "donaciones": {"type": "number", "default": 0},
        },
        "required": ["ccaa", "ingresos_brutos", "retenciones_pagadas"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        state = IRPFWizardState(
            ejercicio=args.get("ejercicio", 2025),
            ccaa=args.get("ccaa", "default"),
            ingresos_brutos=args["ingresos_brutos"],
            retenciones_pagadas=args["retenciones_pagadas"],
            cotizaciones_ss=args.get("cotizaciones_ss", 0),
            hijos=args.get("hijos", 0),
            hijos_menores_3=args.get("hijos_menores_3", 0),
            ascendientes_65=args.get("ascendientes_65", 0),
            discapacidad=args.get("discapacidad", "none"),
            hipoteca_pre2013=args.get("hipoteca_pre2013", 0),
            alquiler_anual=args.get("alquiler_anual", 0),
            plan_pensiones=args.get("plan_pensiones", 0),
            es_autonomo=args.get("es_autonomo", False),
            gastos_deducibles_autonomo=args.get("gastos_deducibles_autonomo", 0),
            es_madre_trabajadora=args.get("es_madre_trabajadora", False),
            familia_numerosa=args.get("familia_numerosa", "none"),
            donaciones=args.get("donaciones", 0),
        )
        return calculate_irpf(state)


class IRPFDeduccionesCCAATool(BaseTool):
    name = "irpfDeduccionesCCAA"
    description = (
        "List all available IRPF deductions for a given Comunidad Autonoma, "
        "including both national and regional deductions."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "ccaa": {
                "type": "string",
                "description": (
                    "Comunidad Autonoma: andalucia, aragon, asturias, baleares, canarias, "
                    "cantabria, castilla_la_mancha, castilla_y_leon, cataluna, extremadura, "
                    "galicia, la_rioja, madrid, murcia, navarra, pais_vasco, valencia, ceuta, melilla"
                ),
            },
        },
        "required": ["ccaa"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        ccaa = args["ccaa"].lower().strip()

        # Check foral regime
        if ccaa in REGIMEN_FORAL:
            return {
                "ccaa": ccaa,
                "regimen": "foral",
                "message": (
                    f"La CCAA {ccaa} tiene regimen foral propio. "
                    "Consulta con la hacienda foral correspondiente."
                ),
                "deducciones_nacionales": [],
                "deducciones_autonomicas": [],
                "disclaimer": DISCLAIMER,
            }

        # National deductions always apply
        nacionales = []
        for key, info in DEDUCCIONES_ESTATALES.items():
            entry: dict[str, Any] = {"id": key, "description": info["description"]}
            if "amount" in info:
                entry["amount"] = info["amount"]
            if "percent" in info:
                entry["percent"] = info["percent"]
            if "max" in info:
                entry["max"] = info["max"]
            nacionales.append(entry)

        # Regional deductions
        regionales = DEDUCCIONES_CCAA.get(ccaa, [])

        has_tramos = ccaa in TRAMOS_AUTONOMICOS
        tramos = TRAMOS_AUTONOMICOS.get(ccaa, TRAMOS_AUTONOMICOS["default"])

        return {
            "ccaa": ccaa,
            "has_specific_brackets": has_tramos and ccaa != "default",
            "tramos_autonomicos": [{"desde": t[0], "hasta": t[1] if t[1] != float("inf") else "sin limite", "tipo": t[2]} for t in tramos],
            "deducciones_nacionales": nacionales,
            "deducciones_autonomicas": regionales,
            "nota": (
                "Estas deducciones son las mas comunes. Consulta la normativa autonomica "
                "vigente para deducciones adicionales o cambios recientes."
            ),
            "disclaimer": DISCLAIMER,
        }


class IRPFGuiaPresentacionTool(BaseTool):
    name = "irpfGuiaPresentacion"
    description = (
        "Return a step-by-step guide for presenting the IRPF declaration (Renta) "
        "in Spain, including deadlines, required documents, and common tips."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "ejercicio": {
                "type": "integer",
                "description": "Ejercicio fiscal (ej: 2025)",
                "default": 2025,
            },
        },
        "required": [],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        ejercicio = args.get("ejercicio", 2025)
        return {
            "ejercicio": ejercicio,
            "plazo": {
                "inicio": f"3 de abril de {ejercicio + 1}",
                "fin_online": f"30 de junio de {ejercicio + 1}",
                "fin_telefono": f"30 de junio de {ejercicio + 1}",
                "fin_presencial": f"30 de junio de {ejercicio + 1}",
                "domiciliacion": f"25 de junio de {ejercicio + 1} (si resultado a ingresar con domiciliacion bancaria)",
            },
            "como_presentar": [
                {
                    "via": "Renta Web (AEAT)",
                    "url": "https://sede.agenciatributaria.gob.es",
                    "acceso": "Cl@ve, certificado digital, o referencia (casilla 505 de la renta anterior)",
                },
                {
                    "via": "App AEAT",
                    "acceso": "Disponible en iOS/Android con Cl@ve PIN",
                },
                {
                    "via": "Telefono (plan Le Llamamos)",
                    "acceso": "Cita previa en sede AEAT o llamando al 91 535 73 26",
                },
                {
                    "via": "Presencial",
                    "acceso": "Cita previa obligatoria en oficina de la AEAT",
                },
            ],
            "documentos_necesarios": [
                "DNI/NIE del declarante (y conyuge si declaracion conjunta)",
                "Datos fiscales (descargables desde Renta Web)",
                "Certificado de retenciones del empleador",
                "Certificados bancarios (cuentas, depositos, hipotecas)",
                "Recibos de alquiler (si aplica deduccion)",
                "Justificantes de aportaciones a planes de pensiones",
                "Facturas de deducciones autonomicas (guarderia, material escolar, etc.)",
                "Referencia catastral de la vivienda habitual",
                "Numero IBAN para devolucion o domiciliacion",
            ],
            "consejos": [
                "Revisa el borrador: los datos fiscales pueden tener errores u omisiones",
                "Comprueba las deducciones autonomicas de tu CCAA — muchas no aparecen en el borrador",
                "Si te sale a devolver, presenta cuanto antes: la devolucion se tramita por orden de entrada",
                "Declaracion conjunta puede convenir si un conyuge no tiene ingresos",
                "Los autonomos deben incluir todos los gastos deducibles de su actividad",
                "Conserva justificantes durante 4 anios (plazo de prescripcion)",
            ],
            "obligados_a_declarar": [
                "Rendimientos del trabajo > 22.000 EUR (un pagador) o > 15.876 EUR (varios pagadores si 2o+ > 1.500 EUR)",
                "Rendimientos del capital mobiliario o ganancias patrimoniales > 1.600 EUR",
                "Rentas inmobiliarias imputadas, rendimientos de letras del tesoro, o subvenciones para vivienda > 1.000 EUR",
                "Autonomos: siempre obligados independientemente de ingresos",
            ],
            "reglas_aplicadas": [
                "Ley 35/2006 del IRPF",
                "RD 439/2007 Reglamento IRPF",
                f"Orden HAC de aprobacion del modelo de declaracion {ejercicio}",
            ],
            "disclaimer": DISCLAIMER,
        }
