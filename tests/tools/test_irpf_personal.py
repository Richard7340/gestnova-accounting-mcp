"""Tests for IRPF Personal income tax wizard and calculation engine."""
import pytest

from gestnova_accounting.tools.irpf_personal import (
    DEDUCCIONES_CCAA,
    DEDUCCIONES_ESTATALES,
    TRAMOS_AUTONOMICOS,
    TRAMOS_ESTATALES,
    WIZARD_STEPS,
    IRPFCalculateTool,
    IRPFDeduccionesCCAATool,
    IRPFGuiaPresentacionTool,
    IRPFWizardAnswerTool,
    IRPFWizardStartTool,
    IRPFWizardState,
    _apply_tramos,
    calculate_irpf,
)


# ── Unit tests for calculate_irpf ───────────────────────────────────────────


class TestIRPFCalculation:
    def test_basic_soltero_madrid(self):
        state = IRPFWizardState(
            ccaa="madrid",
            situacion_personal="soltero",
            ingresos_brutos=30000,
            retenciones_pagadas=4500,
            cotizaciones_ss=1900,
        )
        result = calculate_irpf(state)
        assert result["ingresos_brutos"] == 30000
        assert result["base_imponible"] > 0
        assert result["cuota_integra"] > 0
        assert "resultado" in result
        assert len(result["reglas_aplicadas"]) > 0

    def test_con_hijos_deducciones(self):
        state = IRPFWizardState(
            ccaa="madrid",
            ingresos_brutos=40000,
            retenciones_pagadas=7000,
            cotizaciones_ss=2500,
            hijos=2,
            hijos_menores_3=1,
        )
        result = calculate_irpf(state)
        # minimo_personal (5550) + hijo1 (2400) + hijo2 (2700) + menor3 (2800) = 13450
        assert result["minimo_personal_familiar"] == 13450

    def test_hipoteca_pre2013(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=35000,
            retenciones_pagadas=5000,
            cotizaciones_ss=2200,
            hipoteca_pre2013=6000,
        )
        result = calculate_irpf(state)
        assert any("vivienda" in d["concepto"].lower() for d in result["deducciones"])
        # 6000 * 0.15 = 900
        vivienda_ded = [d for d in result["deducciones"] if "vivienda" in d["concepto"].lower()][0]
        assert vivienda_ded["amount"] == 900.0

    def test_hipoteca_pre2013_capped(self):
        """Hipoteca deduction is capped at 9040 EUR base."""
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=50000,
            retenciones_pagadas=8000,
            cotizaciones_ss=3000,
            hipoteca_pre2013=15000,  # exceeds 9040 cap
        )
        result = calculate_irpf(state)
        vivienda_ded = [d for d in result["deducciones"] if "vivienda" in d["concepto"].lower()][0]
        assert vivienda_ded["amount"] == round(9040 * 0.15, 2)

    def test_autonomo(self):
        state = IRPFWizardState(
            ccaa="andalucia",
            es_autonomo=True,
            ingresos_brutos=50000,
            retenciones_pagadas=8000,
            cotizaciones_ss=3600,
            gastos_deducibles_autonomo=15000,
        )
        result = calculate_irpf(state)
        assert result["base_imponible"] == 50000 - 3600 - 15000

    def test_resultado_devolver(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=15000,
            retenciones_pagadas=3000,
            cotizaciones_ss=900,
        )
        result = calculate_irpf(state)
        assert result["a_devolver"] is True

    def test_resultado_a_pagar(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=80000,
            retenciones_pagadas=5000,
            cotizaciones_ss=2000,
        )
        result = calculate_irpf(state)
        assert result["a_devolver"] is False
        assert result["resultado"] > 0

    def test_deducciones_ccaa_madrid(self):
        assert "madrid" in DEDUCCIONES_CCAA
        assert len(DEDUCCIONES_CCAA["madrid"]) > 0

    def test_deducciones_ccaa_all_present(self):
        for ccaa in ["andalucia", "madrid", "cataluna", "valencia"]:
            assert ccaa in DEDUCCIONES_CCAA
            assert len(DEDUCCIONES_CCAA[ccaa]) >= 3

    def test_wizard_has_all_steps(self):
        assert len(WIZARD_STEPS) >= 10
        fields = [s["field"] for s in WIZARD_STEPS]
        assert "ccaa" in fields
        assert "ingresos_brutos" in fields
        assert "hijos" in fields

    def test_tipo_efectivo(self):
        state = IRPFWizardState(
            ccaa="madrid",
            ingresos_brutos=60000,
            retenciones_pagadas=12000,
            cotizaciones_ss=3800,
        )
        result = calculate_irpf(state)
        assert 0 < result["tipo_efectivo"] < 50

    def test_zero_income(self):
        state = IRPFWizardState(ccaa="default", ingresos_brutos=0, retenciones_pagadas=0)
        result = calculate_irpf(state)
        assert result["cuota_integra"] == 0
        assert result["resultado"] == 0
        assert result["tipo_efectivo"] == 0

    def test_plan_pensiones_capped(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=40000,
            retenciones_pagadas=6000,
            cotizaciones_ss=2500,
            plan_pensiones=5000,  # exceeds 1500 max
        )
        result = calculate_irpf(state)
        # Base liquidable should reflect only 1500 deduction, not 5000
        state2 = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=40000,
            retenciones_pagadas=6000,
            cotizaciones_ss=2500,
            plan_pensiones=1500,
        )
        result2 = calculate_irpf(state2)
        assert result["base_liquidable"] == result2["base_liquidable"]

    def test_maternidad_deduction(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=25000,
            retenciones_pagadas=3500,
            cotizaciones_ss=1500,
            hijos=1,
            hijos_menores_3=1,
            es_madre_trabajadora=True,
        )
        result = calculate_irpf(state)
        assert any("maternidad" in d["concepto"].lower() for d in result["deducciones"])

    def test_familia_numerosa_general(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=45000,
            retenciones_pagadas=7000,
            cotizaciones_ss=2800,
            hijos=3,
            familia_numerosa="general",
        )
        result = calculate_irpf(state)
        assert any("familia numerosa" in d["concepto"].lower() for d in result["deducciones"])

    def test_familia_numerosa_especial(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=45000,
            retenciones_pagadas=7000,
            cotizaciones_ss=2800,
            hijos=5,
            familia_numerosa="especial",
        )
        result = calculate_irpf(state)
        fn_ded = [d for d in result["deducciones"] if "familia numerosa especial" in d["concepto"].lower()]
        assert len(fn_ded) == 1
        assert fn_ded[0]["amount"] == 2400

    def test_discapacidad_33_65(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=30000,
            retenciones_pagadas=4500,
            cotizaciones_ss=1900,
            discapacidad="33-65",
        )
        result = calculate_irpf(state)
        assert result["minimo_personal_familiar"] == 5550 + 3000

    def test_discapacidad_65_plus(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=30000,
            retenciones_pagadas=4500,
            cotizaciones_ss=1900,
            discapacidad="65+",
        )
        result = calculate_irpf(state)
        assert result["minimo_personal_familiar"] == 5550 + 12000

    def test_ascendientes_65(self):
        state = IRPFWizardState(
            ccaa="default",
            ingresos_brutos=30000,
            retenciones_pagadas=4500,
            cotizaciones_ss=1900,
            ascendientes_65=2,
        )
        result = calculate_irpf(state)
        assert result["minimo_personal_familiar"] == 5550 + 1150 * 2

    def test_alquiler_deduction_madrid(self):
        state = IRPFWizardState(
            ccaa="madrid",
            ingresos_brutos=25000,
            retenciones_pagadas=4000,
            cotizaciones_ss=1500,
            alquiler_anual=9600,
        )
        result = calculate_irpf(state)
        alquiler_deds = [d for d in result["deducciones"] if "alquiler" in d["concepto"].lower()]
        assert len(alquiler_deds) == 1
        # Madrid: 30% of 9600 = 2880, capped at 1000
        assert alquiler_deds[0]["amount"] == 1000


# ── Tests for _apply_tramos ──────────────────────────────────────────────────


class TestApplyTramos:
    def test_zero_base(self):
        assert _apply_tramos(0, TRAMOS_ESTATALES) == 0

    def test_first_bracket_only(self):
        # 10000 EUR at 9.5% = 950
        assert round(_apply_tramos(10000, TRAMOS_ESTATALES), 2) == 950.0

    def test_two_brackets(self):
        # 15000: 12450 * 0.095 + (15000-12450) * 0.12
        expected = 12450 * 0.095 + 2550 * 0.12
        assert round(_apply_tramos(15000, TRAMOS_ESTATALES), 2) == round(expected, 2)

    def test_pais_vasco_higher_rates(self):
        """Pais Vasco has notably higher rates."""
        base = 50000
        pv = _apply_tramos(base, TRAMOS_AUTONOMICOS["pais_vasco"])
        default = _apply_tramos(base, TRAMOS_AUTONOMICOS["default"])
        assert pv > default

    def test_madrid_lower_rates(self):
        """Madrid has lower autonomic rates than default."""
        base = 50000
        madrid = _apply_tramos(base, TRAMOS_AUTONOMICOS["madrid"])
        default = _apply_tramos(base, TRAMOS_AUTONOMICOS["default"])
        assert madrid < default


# ── Tests for MCP tool classes ───────────────────────────────────────────────


class TestIRPFWizardStartTool:
    @pytest.mark.asyncio
    async def test_start_returns_session(self):
        tool = IRPFWizardStartTool()
        result = await tool.execute({})
        assert "session_id" in result
        assert result["step"] == 0
        assert result["total_steps"] == len(WIZARD_STEPS)
        assert "question" in result

    @pytest.mark.asyncio
    async def test_start_first_question_is_ejercicio(self):
        tool = IRPFWizardStartTool()
        result = await tool.execute({})
        assert result["field"] == "ejercicio"


class TestIRPFWizardAnswerTool:
    @pytest.mark.asyncio
    async def test_invalid_session(self):
        tool = IRPFWizardAnswerTool()
        result = await tool.execute({"session_id": "nonexistent", "answer": "madrid"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_full_wizard_flow(self):
        start = IRPFWizardStartTool()
        answer = IRPFWizardAnswerTool()

        r = await start.execute({})
        sid = r["session_id"]

        answers = [
            2025,        # ejercicio
            "madrid",    # ccaa
            "soltero",   # situacion_personal
            30000,       # ingresos_brutos
            4500,        # retenciones_pagadas
            1900,        # cotizaciones_ss
            False,       # es_autonomo
            0,           # hijos
            0,           # hijos_menores_3
            0,           # hipoteca_pre2013
            0,           # alquiler_anual
            0,           # plan_pensiones
            0,           # donaciones
        ]

        for i, ans in enumerate(answers):
            r = await answer.execute({"session_id": sid, "answer": ans})
            if i < len(answers) - 1:
                assert "question" in r
            else:
                assert r["completed"] is True
                assert "results" in r
                assert r["results"]["ingresos_brutos"] == 30000

    @pytest.mark.asyncio
    async def test_completed_session_returns_error(self):
        start = IRPFWizardStartTool()
        answer = IRPFWizardAnswerTool()

        r = await start.execute({})
        sid = r["session_id"]

        answers = [2025, "madrid", "soltero", 30000, 4500, 1900, False, 0, 0, 0, 0, 0, 0]
        for ans in answers:
            r = await answer.execute({"session_id": sid, "answer": ans})

        # Try answering again
        r = await answer.execute({"session_id": sid, "answer": "something"})
        assert "error" in r


class TestIRPFCalculateTool:
    @pytest.mark.asyncio
    async def test_direct_calculation(self):
        tool = IRPFCalculateTool()
        result = await tool.execute({
            "ccaa": "madrid",
            "ingresos_brutos": 35000,
            "retenciones_pagadas": 5500,
            "cotizaciones_ss": 2200,
        })
        assert result["ingresos_brutos"] == 35000
        assert result["cuota_integra"] > 0
        assert "resultado" in result

    @pytest.mark.asyncio
    async def test_with_all_options(self):
        tool = IRPFCalculateTool()
        result = await tool.execute({
            "ccaa": "andalucia",
            "ingresos_brutos": 50000,
            "retenciones_pagadas": 9000,
            "cotizaciones_ss": 3200,
            "hijos": 2,
            "hijos_menores_3": 1,
            "hipoteca_pre2013": 5000,
            "plan_pensiones": 1000,
            "es_madre_trabajadora": True,
            "familia_numerosa": "none",
        })
        assert result["minimo_personal_familiar"] > 5550
        assert len(result["deducciones"]) > 0


class TestIRPFDeduccionesCCAATool:
    @pytest.mark.asyncio
    async def test_madrid_deducciones(self):
        tool = IRPFDeduccionesCCAATool()
        result = await tool.execute({"ccaa": "madrid"})
        assert result["ccaa"] == "madrid"
        assert result["has_specific_brackets"] is True
        assert len(result["deducciones_nacionales"]) > 0
        assert len(result["deducciones_autonomicas"]) > 0
        assert len(result["tramos_autonomicos"]) > 0

    @pytest.mark.asyncio
    async def test_unknown_ccaa(self):
        tool = IRPFDeduccionesCCAATool()
        result = await tool.execute({"ccaa": "unknown_region"})
        assert result["has_specific_brackets"] is False
        assert result["deducciones_autonomicas"] == []
        assert len(result["deducciones_nacionales"]) > 0


class TestIRPFGuiaPresentacionTool:
    @pytest.mark.asyncio
    async def test_default_year(self):
        tool = IRPFGuiaPresentacionTool()
        result = await tool.execute({})
        assert result["ejercicio"] == 2025
        assert "plazo" in result
        assert "como_presentar" in result
        assert "documentos_necesarios" in result
        assert "consejos" in result
        assert "obligados_a_declarar" in result
        assert len(result["reglas_aplicadas"]) > 0

    @pytest.mark.asyncio
    async def test_specific_year(self):
        tool = IRPFGuiaPresentacionTool()
        result = await tool.execute({"ejercicio": 2025})
        assert result["ejercicio"] == 2025
        assert "2026" in result["plazo"]["inicio"]


# ── Data integrity tests ────────────────────────────────────────────────────


class TestDataIntegrity:
    def test_tramos_estatales_sorted(self):
        for i in range(len(TRAMOS_ESTATALES) - 1):
            assert TRAMOS_ESTATALES[i][1] == TRAMOS_ESTATALES[i + 1][0]

    def test_tramos_autonomicos_sorted(self):
        for ccaa, tramos in TRAMOS_AUTONOMICOS.items():
            for i in range(len(tramos) - 1):
                assert tramos[i][1] == tramos[i + 1][0], f"Gap in {ccaa} tramos at index {i}"

    def test_all_ccaa_have_tramos(self):
        for ccaa in ["andalucia", "madrid", "cataluna", "valencia", "pais_vasco", "default"]:
            assert ccaa in TRAMOS_AUTONOMICOS

    def test_deducciones_estatales_complete(self):
        required = ["minimo_personal", "minimo_descendientes_1", "plan_pensiones", "maternidad"]
        for key in required:
            assert key in DEDUCCIONES_ESTATALES

    def test_wizard_steps_have_required_fields(self):
        for step in WIZARD_STEPS:
            assert "field" in step
            assert "question" in step
            assert "type" in step
            assert step["type"] in ("choice", "number", "boolean")
