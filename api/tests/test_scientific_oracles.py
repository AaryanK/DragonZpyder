"""No-network executable numerical verifier regression tests."""
from decimal import Decimal
import pytest
from agent_platform.scientific_oracles import (
    quadratic_gradient_audit, trilinear_audit,
    check_quadratic_gradient_step,
)


def test_f08_false_positive_gradient_is_refuted():
    result = quadratic_gradient_audit(x=5, slope=2, intercept=-20,
                                      learning_rate=0.1, proposed_next=6)
    assert result["arithmetic_valid"] is True
    assert result["objective_improves"] is True
    assert result["expected_next"] == "6.0"
    assert result["optimum"] == "10"
    assert result["correction_needed"] is False


def test_real_step_errors_are_detected():
    result = quadratic_gradient_audit(x=5, slope=2, intercept=10,
                                      learning_rate=0.1, proposed_next=6)
    assert result["arithmetic_valid"] is False
    assert result["expected_next"] == "3.0"


@pytest.mark.parametrize("bad", ["NaN", "Infinity", 1e12, True])
def test_nonfinite_or_invalid_scalars_rejected(bad):
    with pytest.raises(ValueError):
        quadratic_gradient_audit(x=bad, slope=2, intercept=-20,
                                 learning_rate=0.1, proposed_next=6)


def test_trilinear_midpoint_and_corner_arithmetic():
    corners = [[(i>>2)&1, (i>>1)&1, i&1] for i in range(8)]
    result = trilinear_audit(weights=[0.5, 0.5, 0.5],
                             corner_values=corners)
    assert [Decimal(x) for x in result["interpolated_vector"]] == [
        Decimal("0.5"), Decimal("0.5"), Decimal("0.5")]
    corner = trilinear_audit(weights=[1,0,1], corner_values=corners)
    assert [Decimal(x) for x in corner["interpolated_vector"]] == [
        Decimal("1"),Decimal("0"),Decimal("1")]


@pytest.mark.parametrize("bad", [[-0.1,0,0],[1.01,0,0],[float("nan"),0,0]])
def test_trilinear_out_of_bounds_refused(bad):
    with pytest.raises(ValueError):
        trilinear_audit(weights=bad,corner_values=[[0,0,0]]*8)


def test_langchain_tool_runs_without_model_or_shell():
    result = check_quadratic_gradient_step.invoke({
        "x":5, "slope":2, "intercept":-20,
        "learning_rate":0.1, "proposed_next":6,
    })
    assert '"arithmetic_valid": true' in result
    assert '"correction_needed": false' in result
