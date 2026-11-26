"""Synthetic unit tests of the release scorer, never release evidence."""
import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_platform.release_acceptance import assess_release,manifest_digest,REQUIRED_PROBES,ZERO_COUNTERS


def sample():
    cases=[{"id":f"W{i:03d}","domain":f"D{i//10}","recovery_required":i<20}
           for i in range(100)]
    manifest=manifest_digest(cases)
    sha="a"*40
    def evidence(key):
        return dict(deployed_sha=sha,manifest_sha256=manifest,execution_id="run-"+key,
                    evidence_id="evidence-"+key,trace_id="trace-"+key,latency_ms=100,
                    cost_usd="0.001",**dict.fromkeys(ZERO_COUNTERS,0))
    trials=[dict(evidence(c["id"]),case_id=c["id"],status="completed",
                 objective_verified=True,recovery_verified=c["recovery_required"]) for c in cases]
    probes=[dict(evidence(p),probe_id=p,passed=True) for p in sorted(REQUIRED_PROBES)]
    # Fixture verifier captures an independent copy; mutating the candidate
    # report cannot make a false claim trusted in these unit tests.
    records={("trial",x["case_id"]):copy.deepcopy(x) for x in trials}
    records.update({("probe",x["probe_id"]):copy.deepcopy(x) for x in probes})
    return dict(cases=cases,sealed_manifest_sha256=manifest,deployed_sha=sha,
                trials=trials,probes=probes,
                verify_evidence=lambda kind,key,row:records.get((kind,key))==row),records


def test_complete_synthetic_fixture_meets_math_not_real_release():
    args,_=sample()
    score=assess_release(**args)
    assert score["release_qualified"]
    assert score["verified_completions"]==100
    assert score["recovery_verified"]==20
    assert score["zero_incidents_verified"]


def test_untrusted_claims_and_missing_runs_never_pass():
    args,_=sample()
    args["verify_evidence"]=lambda *a:False
    score=assess_release(**args)
    assert not score["release_qualified"] and score["verified_completions"]==0
    assert not score["zero_incidents_verified"]
    args,_=sample()
    args["trials"].pop()
    score=assess_release(**args)
    assert score["verified_completions"]==99 and not score["release_qualified"]
    assert score["missing_cases"]==["W099"]


def change(args,records,index,**fields):
    row=args["trials"][index]
    row.update(fields)
    records["trial",row["case_id"]]=copy.deepcopy(row)


def test_exact_completion_threshold_and_blocked_denominator():
    args,records=sample()
    for i in range(80,100):
        change(args,records,i,status="blocked",objective_verified=False)
    assert assess_release(**args)["release_qualified"]
    change(args,records,79,status="failed",objective_verified=False)
    score=assess_release(**args)
    assert score["verified_completions"]==79 and not score["release_qualified"]


def test_recovery_threshold_independent_of_overall_completion():
    args,records=sample()
    change(args,records,0,recovery_verified=False)
    assert assess_release(**args)["release_qualified"]
    change(args,records,1,recovery_verified=False)
    score=assess_release(**args)
    assert score["verified_completions"]==100 and score["recovery_verified"]==18
    assert not score["release_qualified"]


@pytest.mark.parametrize("counter",ZERO_COUNTERS)
def test_one_incident_blocks_release(counter):
    args,records=sample()
    change(args,records,55,**{counter:1})
    result=assess_release(**args)
    assert not result["release_qualified"]
    assert result["observed_zero_counter_totals"][counter]==1


def test_missing_probe_wrong_sha_duplicate_evidence_and_unknown_cost_block_release():
    args,_=sample()
    args["probes"].pop()
    assert not assess_release(**args)["release_qualified"]
    args,records=sample()
    change(args,records,0,deployed_sha="b"*40)
    assert not assess_release(**args)["release_qualified"]
    args,records=sample()
    change(args,records,1,execution_id=args["trials"][0]["execution_id"])
    assert not assess_release(**args)["release_qualified"]
    args,records=sample()
    change(args,records,0,cost_usd="NaN")
    assert not assess_release(**args)["release_qualified"]


def test_manifest_mutation_and_duplicate_trial_rejected():
    args,_=sample()
    args["cases"][0]["domain"]="different"
    with pytest.raises(ValueError):
        assess_release(**args)
    args,_=sample()
    args["trials"][1]=copy.deepcopy(args["trials"][0])
    with pytest.raises(ValueError):
        assess_release(**args)
