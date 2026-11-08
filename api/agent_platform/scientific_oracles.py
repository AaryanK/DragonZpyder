"""Pure bounded numerical oracles; no shell, network, or dynamic code."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation, localcontext
import json
from langchain_core.tools import tool

def number(raw):
    if type(raw) not in (int, float, str, Decimal):
        raise ValueError("Scalar numeric input required")
    try:
        n = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid numeric input") from exc
    if not n.is_finite() or abs(n) > Decimal("1e9"):
        raise ValueError("Nonfinite or out-of-range numeric input")
    return n

def quadratic_gradient_audit(*, x, slope, intercept, learning_rate, proposed_next):
    """For f(x)=slope*x²/2 + intercept*x; derivative=slope*x+intercept."""
    with localcontext() as ctx:
        ctx.prec = 36
        x,a,b,lr,given = [number(v) for v in (x,slope,intercept,learning_rate,proposed_next)]
        if a <= 0 or lr <= 0 or lr > 1:
            raise ValueError("Requires convex quadratic and positive bounded step")
        gradient = a*x+b
        expected = x-lr*gradient
        original = a*x*x/2 + b*x
        final = a*expected*expected/2+b*expected
        valid = abs(given-expected) <= Decimal("0.000000001")
        return {"arithmetic_valid":valid,"objective_improves":final < original,
                "gradient":str(gradient),"expected_next":str(expected),
                "optimum":str(-b/a),"correction_needed":not valid,
                "scope":"one convex quadratic gradient step only"}

def trilinear_audit(*, weights, corner_values):
    """Interpolate eight 3-vectors; corner order 000,001,010,011,100,101,110,111."""
    if not isinstance(weights,(list,tuple)) or len(weights)!=3:
        raise ValueError("Three normalized coordinates required")
    if not isinstance(corner_values,(list,tuple)) or len(corner_values)!=8:
        raise ValueError("Eight corners required")
    with localcontext() as ctx:
        ctx.prec=36
        xyz=[number(x) for x in weights]
        if any(x<0 or x>1 for x in xyz):
            raise ValueError("Location outside unit cube")
        values=[]
        for corner in corner_values:
            if not isinstance(corner,(list,tuple)) or len(corner)!=3:
                raise ValueError("Each corner must be a 3-vector")
            values.append([number(x) for x in corner])
        out=[Decimal(0)]*3
        for i,vec in enumerate(values):
            bits=((i>>2)&1,(i>>1)&1,i&1)
            wt=Decimal(1)
            for coord,bit in zip(xyz,bits):
                wt*=coord if bit else 1-coord
            for j in range(3):
                out[j]+=wt*vec[j]
        return {"interpolated_vector":[str(x) for x in out],
                "scope":"interpolation arithmetic only; no Geant4 or physical units proof"}

@tool
def check_quadratic_gradient_step(x: float, slope: float, intercept: float,
                                  learning_rate: float, proposed_next: float) -> str:
    """Independently check a disputed convex-quadratic gradient step f'(x)=slope*x+intercept. Mandatory before accusing a correct numerical step of being wrong."""
    try:
        return json.dumps(quadratic_gradient_audit(x=x,slope=slope,
            intercept=intercept,learning_rate=learning_rate,
            proposed_next=proposed_next),sort_keys=True)
    except ValueError:
        return json.dumps({"status":"unsupported_or_invalid_numeric_claim"})

@tool
def check_trilinear_interpolation(weights: list[float],
                                  corner_values: list[list[float]]) -> str:
    """Verify scalar trilinear interpolation of eight 3D vector corners inside a unit cube, not coordinate physics."""
    try:
        return json.dumps(trilinear_audit(weights=weights,
                          corner_values=corner_values),sort_keys=True)
    except ValueError:
        return json.dumps({"status":"unsupported_or_invalid_numeric_claim"})
