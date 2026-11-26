import pytest

from agent_platform.decision_routing import ROUTES, decision_request, recommend_route

ALLOWED = frozenset({"direct", "lookup", "agentic", "persistent"})


def answer(choice="lookup", probability=.96, confidence=.96):
    return {"answers": {"execution_route": {
        "type": "choice", "choice": choice, "confidence": confidence,
        "probabilities": {k: probability if k == choice else (1-probability)/4 for k in ROUTES},
    }}}


def test_request_uses_fixed_criteria_and_approved_model():
    request = decision_request(model="typesafe/jev-1.14",
        approved_models=frozenset({"typesafe/jev-1.14"}),
        sanitized_objective="List my workflows")
    assert request["questions"]["execution_route"]["criteria"] == ROUTES
    assert request["state"] == {"objective": "List my workflows"}
    with pytest.raises(ValueError):
        decision_request(model="unapproved", approved_models=frozenset(),
                         sanitized_objective="List workflows")


@pytest.mark.parametrize("objective", ["", "   ", "x" * 4001])
def test_objective_is_bounded(objective):
    with pytest.raises(ValueError):
        decision_request(model="approved", approved_models=frozenset({"approved"}),
                         sanitized_objective=objective)


@pytest.mark.parametrize("choice", list(ALLOWED))
def test_high_confidence_candidate(choice):
    assert recommend_route(answer(choice), eligible_routes=ALLOWED).route == choice


def test_ineligible_route_cannot_expand_scope():
    result = recommend_route(answer("persistent"), eligible_routes=frozenset({"agentic"}))
    assert result.route == "agentic"
    assert result.reason == "route_ineligible_or_uncertain"


@pytest.mark.parametrize("response", [
    None, {}, answer("uncertain"), answer(probability=.60),
    answer(confidence=.40), answer(probability=float("nan")),
    answer(probability=float("inf")), answer(probability=-.1),
])
def test_uncertain_or_invalid_decision_uses_existing_agent(response):
    assert recommend_route(response, eligible_routes=ALLOWED).route == "agentic"


def test_refusal_and_unknown_option():
    response = answer()
    response["answers"]["execution_route"]["refusal"] = "refused"
    assert recommend_route(response, eligible_routes=ALLOWED).route == "agentic"
    response = answer()
    response["answers"]["execution_route"]["choice"] = "invented"
    assert recommend_route(response, eligible_routes=ALLOWED).route == "agentic"


def test_probability_distribution_must_be_complete_and_consistent():
    response = answer()
    response["answers"]["execution_route"]["probabilities"].pop("direct")
    assert recommend_route(response, eligible_routes=ALLOWED).route == "agentic"
    response = answer()
    response["answers"]["execution_route"]["probabilities"]["direct"] = .9
    assert recommend_route(response, eligible_routes=ALLOWED).route == "agentic"


def test_missing_fallback_is_configuration_error():
    with pytest.raises(ValueError):
        recommend_route(answer(), eligible_routes=frozenset({"lookup"}))
