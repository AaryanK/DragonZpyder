"""Bounded privacy-minimal agent callback telemetry.

No prompts, tool arguments/results, provider credentials, identities, raw
exception messages or account-derived names are retained. Callback observations
are not independent outcome receipts or authoritative billing records.
"""
from __future__ import annotations

from collections import Counter
from threading import Lock
from time import monotonic_ns

from langchain_core.callbacks import BaseCallbackHandler

from .tool_outcomes import tool_outcome

_MAX_ACTIVE = 256
_NATIVE = frozenset({"ls","read_file","write_file","edit_file","glob","grep",
                     "write_todos","task","eval","web_search",
                     "check_quadratic_gradient_step","check_trilinear_interpolation"})
_REASONS = frozenset({"graph_recursion_limit","model_call_limit","tool_call_limit",
                      "execution_deadline","repeated_tool_cycle","external_approval_required",
                      "external_outcome_unconfirmed","inference_limit_reached",
                      "no_progress","turn_limit","cancelled"})


def tool_family(name):
    if not isinstance(name,str):
        return "other"
    if name in _NATIVE:
        return name
    if name in {"search_tools","describe_tool","invoke_tool","operly_search","operly_execute"}:
        return name
    if name.startswith(("computer_","mcp_read_","operly_")):
        return name.split("_",1)[0]+"_capability"
    if name.startswith(("goal_","graph_","native_canary_")):
        return "persistent_capability"
    return "other"


class RunTelemetry(BaseCallbackHandler):
    def __init__(self, *, clock=monotonic_ns):
        super().__init__()
        self._clock=clock
        self._origin=clock()
        self._lock=Lock()
        self._active={}
        self._counts=Counter()
        self._tool_counts=Counter()
        self._latencies=Counter()
        self._input_tokens=0
        self._output_tokens=0
        self._missing_usage=0
        self._overflow=False

    def _start(self,run_id,kind,family):
        with self._lock:
            if run_id in self._active:
                self._overflow=True
                return
            self._counts[kind+"_started"]+=1
            if len(self._active)>=_MAX_ACTIVE:
                self._overflow=True
                return
            self._active[run_id]=(kind,family,self._clock())

    def on_chat_model_start(self,serialized,messages,*,run_id,**kwargs):
        self._start(run_id,"model","model")

    def on_llm_start(self,serialized,prompts,*,run_id,**kwargs):
        self._start(run_id,"model","model")

    def on_tool_start(self,serialized,input_str,*,run_id,**kwargs):
        name=(serialized or {}).get("name") or kwargs.get("name")
        self._start(run_id,"tool",tool_family(name))

    def _finish(self,run_id,status,usage=None):
        with self._lock:
            started=self._active.pop(run_id,None)
            if started is None:
                self._overflow=True
                return
            kind,family,start=started
            self._counts[kind+"_"+status]+=1
            self._latencies[kind]+=max(0,self._clock()-start)
            if kind=="tool":
                self._tool_counts[(family,status)]+=1
            elif status=="returned":
                if usage is None:
                    self._missing_usage+=1
                else:
                    self._input_tokens+=usage[0]
                    self._output_tokens+=usage[1]

    def on_llm_end(self,response,*,run_id,**kwargs):
        # Only aggregate a single known generation per input. Missing or
        # ambiguous metadata is unknown, never free inference.
        usage=None
        try:
            rows=response.generations
            if isinstance(rows,list) and rows and all(len(row)==1 for row in rows):
                pairs=[]
                for row in rows:
                    u=getattr(getattr(row[0],"message",None),"usage_metadata",None)
                    a,b=u.get("input_tokens"),u.get("output_tokens")
                    if type(a) is not int or type(b) is not int or min(a,b)<0:
                        raise ValueError()
                    pairs.append((a,b))
                usage=(sum(a for a,b in pairs),sum(b for a,b in pairs))
        except (AttributeError,TypeError,ValueError,IndexError):
            pass
        self._finish(run_id,"returned",usage)

    def on_llm_error(self,error,*,run_id,**kwargs):
        self._finish(run_id,"failed")

    def on_tool_end(self,output,*,run_id,**kwargs):
        outcome=tool_outcome(output)
        self._finish(run_id,outcome)

    def on_tool_error(self,error,*,run_id,**kwargs):
        self._finish(run_id,"failed")

    def snapshot(self,*,status,termination_reason=None):
        with self._lock:
            incomplete=bool(self._active) or self._overflow
            counts={k:self._counts.get(k,0) for k in (
                "model_started","model_returned","model_failed","tool_started",
                "tool_returned","tool_failed","tool_unknown","tool_approval_required")}
            return {
                "status":status if status in {"completed","incomplete","failed","cancelled"} else "unknown",
                "termination_reason":termination_reason if termination_reason in _REASONS else
                    ("other" if termination_reason is not None else None),
                "elapsed_ms":round(max(0,self._clock()-self._origin)/1_000_000,3),
                **counts,"unfinished_callbacks":len(self._active),
                "callback_observation_complete":not incomplete,
                "model_latency_ms_sum":round(self._latencies["model"]/1_000_000,3),
                "tool_latency_ms_sum":round(self._latencies["tool"]/1_000_000,3),
                "tool_outcomes_by_family":[{"family":f,"outcome":s,"count":n}
                                           for (f,s),n in sorted(self._tool_counts.items())],
                "observed_input_tokens":self._input_tokens,
                "observed_output_tokens":self._output_tokens,
                "successful_models_missing_usage":self._missing_usage,
                "token_usage_complete":not incomplete and self._missing_usage==0
                    and counts["model_failed"]==0,
                "cost_usd":None, # Only the metered gateway can settle authoritative cost.
                "objective_verified":False,
            }
