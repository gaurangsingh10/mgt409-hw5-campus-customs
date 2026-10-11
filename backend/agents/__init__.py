"""The five Campus Customs agents. Each file declares one role's SPEC."""

from agents import accounting, boss, customer_service, facilities, inventory

SPECS = {s.name: s for s in (boss.SPEC, inventory.SPEC, accounting.SPEC, facilities.SPEC, customer_service.SPEC)}
