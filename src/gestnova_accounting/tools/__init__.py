"""Tool registry."""
from typing import Any
from ._base import BaseTool
from .payroll import (
    CalculatePayrollTool,
    SimulatePayrollChangeTool,
    ValidatePayrollConceptExemptionTool,
    GeneratePayslipTool,
)
from .time_tracking import (
    ClockInLegalTool,
    GetJornadaStatusTool,
    GetOvertimeBalanceTool,
)
from .leave import (
    CheckLeaveEntitlementTool,
    GetVacationBalanceTool,
    GetLeaveCalendarTool,
)
from .meta import (
    LookupLegalReferenceTool,
    GetApplicableRulesTool,
    ListSupportedCountriesTool,
    GetCountryFiscalProfileTool,
)
from .invoice import (
    CalculateInvoiceTool,
    CalculateIVATool,
    GetApplicableVATRateTool,
    ValidateInvoiceDataTool,
    ClassifyExpenseTool,
    CheckDietaExemptTool,
    ApplyKilometrageRateTool,
)


class PingTool(BaseTool):
    name = "ping"
    description = "Health check — returns server status and version."
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        from gestnova_accounting import __version__
        return {"status": "ok", "version": __version__}


def get_all_tools() -> list[BaseTool]:
    return [
        PingTool(),
        CalculatePayrollTool(),
        SimulatePayrollChangeTool(),
        ValidatePayrollConceptExemptionTool(),
        GeneratePayslipTool(),
        ClockInLegalTool(),
        GetJornadaStatusTool(),
        GetOvertimeBalanceTool(),
        CheckLeaveEntitlementTool(),
        GetVacationBalanceTool(),
        GetLeaveCalendarTool(),
        LookupLegalReferenceTool(),
        GetApplicableRulesTool(),
        ListSupportedCountriesTool(),
        GetCountryFiscalProfileTool(),
        CalculateInvoiceTool(),
        CalculateIVATool(),
        GetApplicableVATRateTool(),
        ValidateInvoiceDataTool(),
        ClassifyExpenseTool(),
        CheckDietaExemptTool(),
        ApplyKilometrageRateTool(),
    ]
