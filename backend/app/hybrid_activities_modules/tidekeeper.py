"""Deterministic updating and selective-attention stream for HY-02."""
from __future__ import annotations
import hashlib, random
from typing import Any

VERSION="hy-02-v1"; EVALUATION_VERSION="hy-02-eval-v1"
LIMITATIONS=["Descriptive activity outcomes only; not one of the five fixed baseline indices.","Match and non-match decisions are summarized separately for position and symbol channels."]
SYMBOLS=("◈","✦","⬡","✿","⬟")
def generate(seed:str,mode:str,tier:str)->dict[str,Any]:
 n=1 if tier in {"tutorial","tier-1"} else 2
 count=8 if mode=="tutorial" else 12 if tier=="tier-1" else 16
 rng=random.Random(int(hashlib.sha256(f"{seed}|{VERSION}|{tier}".encode()).hexdigest()[:16],16))
 stream=[]; pos=rng.randrange(9); sym=rng.randrange(len(SYMBOLS))
 for i in range(count):
  if i<n or rng.random()<.55: pos=rng.randrange(9)
  else: pos=stream[i-n]["position"]
  if i<n or rng.random()<.55: sym=rng.randrange(len(SYMBOLS))
  else: sym=stream[i-n]["symbol_index"]
  stream.append({"cue_id":f"cue-{i+1}","position":pos,"symbol_index":sym,"symbol":SYMBOLS[sym]})
 return {"activity_id":"HY-02","activity_version":VERSION,"config_version":"1","mode":mode,"tier":tier,"seed":seed,"n_back":n,"trial_count":count,"response_window_ms":2100,"symbols":list(SYMBOLS),"_oracle_stream":stream,"assistance_windows":["pre_block","post_window"]}
def public_config(config:dict[str,Any])->dict[str,Any]:return {k:v for k,v in config.items() if not k.startswith("_")}
def stimulus(config:dict[str,Any],index:int)->dict[str,Any]|None:
 stream=config["_oracle_stream"]
 if index<0 or index>=len(stream):return None
 return {"index":index,"cue_id":stream[index]["cue_id"],"position":stream[index]["position"],"symbol":stream[index]["symbol"],"response_window_ms":config["response_window_ms"],"n_back":config["n_back"]}
def evaluate(config:dict[str,Any],actions:list[dict[str,Any]])->dict[str,Any]:
 stream=config["_oracle_stream"]; n=config["n_back"]; rows=[]
 for a in actions:
  if a.get("action_type")!="respond":continue
  p=a.get("payload") or {}; i=int(p.get("trial_index",-1))
  if i<0 or i>=len(stream):continue
  cue=stream[i]; prior=stream[i-n] if i>=n else None
  pos_match=prior is not None and cue["position"]==prior["position"]
  sym_match=prior is not None and cue["symbol_index"]==prior["symbol_index"]
  rows.append({"trial_index":i,"cue_event_id":cue["cue_id"],"position_match_expected":pos_match,"symbol_match_expected":sym_match,"position_match_response":bool(p.get("position_match")),"symbol_match_response":bool(p.get("symbol_match")),"position_correct":bool(p.get("position_match"))==pos_match,"symbol_correct":bool(p.get("symbol_match"))==sym_match,"response_time_ms":a.get("elapsed_ms")})
 return {"activity_id":"HY-02","evaluation_version":EVALUATION_VERSION,"n_back":n,"trials_presented":len(rows),"trials_expected":len(stream),"position_correct":sum(r["position_correct"] for r in rows),"position_total":len(rows),"symbol_correct":sum(r["symbol_correct"] for r in rows),"symbol_total":len(rows),"false_alarms":{"position":sum(r["position_match_response"] and not r["position_match_expected"] for r in rows),"symbol":sum(r["symbol_match_response"] and not r["symbol_match_expected"] for r in rows)},"misses":{"position":sum(r["position_match_expected"] and not r["position_match_response"] for r in rows),"symbol":sum(r["symbol_match_expected"] and not r["symbol_match_response"] for r in rows)},"responses":rows}
