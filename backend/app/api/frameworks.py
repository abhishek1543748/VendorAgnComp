from fastapi import APIRouter
from app.rules.engine import load_rules_for_framework

router = APIRouter(prefix="/frameworks", tags=["frameworks"])

# Phase 8: Only advertise frameworks that actually have rule packs.
# ISO_27001 was removed because app/rules/packs/ has no iso_27001.yaml —
# selecting it caused a 400 from the evaluate endpoint.
# To re-add it: write a real iso_27001.yaml using the Phase-1 field names,
# then add "ISO_27001" back to this list.
_IMPLEMENTED_FRAMEWORKS = ["CIS", "NIST_800_53", "STIG"]


@router.get("")
def list_frameworks():
    """
    Return only frameworks that have at least one rule in their pack file.
    This prevents the frontend dropdown from offering frameworks that will
    always error on evaluate.
    """
    return [fw for fw in _IMPLEMENTED_FRAMEWORKS if load_rules_for_framework(fw)]
