"""Discrete paced multi-wave attention, manifest and rule-switch game HY-04."""
from __future__ import annotations
import hashlib,random
from typing import Any
VERSION="hy-04-v1";EVALUATION_VERSION="hy-04-eval-v1"
LIMITATIONS=["Descriptive activity outcomes only; not one of the five fixed baseline indices.","Arrivals advance only after a recorded response; network and paint delays do not count as missed targets."]
DESTINATIONS=("north-pier","east-dock","lighthouse")
def generate(seed:str,mode:str,tier:str)->dict[str,Any]:
 rng=random.Random(int(hashlib.sha256(f"{seed}|{VERSION}|{tier}".encode()).hexdigest()[:16],16));waves=2 if tier in {"tutorial","tier-1"} else 3;per_wave=4 if tier in {"tutorial","tier-1"} else 5
 manifest={f"cargo-{i+1}":DESTINATIONS[rng.randrange(len(DESTINATIONS))] for i in range(3 if waves==2 else 4)}
 arrivals=[]
 for w in range(waves):
  for j in range(per_wave):
   distractor=(j==per_wave-1); cargo=f"cargo-{rng.randrange(len(manifest))+1}" if not distractor else f"decoy-{w+1}"
   arrivals.append({"arrival_id":f"arrival-{w+1}-{j+1}","wave":w+1,"cargo_id":cargo,"distractor":distractor,"old_route":manifest.get(cargo,DESTINATIONS[rng.randrange(3)]),"new_route":DESTINATIONS[rng.randrange(3)]})
 return {"activity_id":"HY-04","activity_version":VERSION,"config_version":"1","mode":mode,"tier":tier,"seed":seed,"wave_count":waves,"arrivals_per_wave":per_wave,"manifest_length":len(manifest),"response_window_ms":1800,"manifest":manifest,"destinations":list(DESTINATIONS),"rule_switch":{"from":"direct","to":"marked","cue":"At the new wave, route each cargo to its marked destination."},"_oracle_arrivals":arrivals,"assistance_windows":["pre_wave","between_waves"]}
def public_config(config:dict[str,Any])->dict[str,Any]:return {k:v for k,v in config.items() if not k.startswith("_")}
def stimulus(config:dict[str,Any],index:int)->dict[str,Any]|None:
 rows=config["_oracle_arrivals"]
 if index<0 or index>=len(rows):return None
 row=rows[index];return {"index":index,"cue_id":row["arrival_id"],"wave":row["wave"],"cargo_id":row["cargo_id"],"distractor":row["distractor"],"route_options":list(DESTINATIONS),"rule":"direct" if row["wave"]==1 else "marked","marked_destination":row["new_route"] if row["wave"]>1 and not row["distractor"] else None,"response_window_ms":config["response_window_ms"]}
def evaluate(config:dict[str,Any],actions:list[dict[str,Any]])->dict[str,Any]:
 stream=config["_oracle_arrivals"];manifest=config["manifest"];rows=[]
 for a in actions:
  if a.get("action_type")!="respond":continue
  p=a.get("payload") or {};i=int(p.get("arrival_index",-1))
  if not 0<=i<len(stream):continue
  cue=stream[i];selected=p.get("destination_id");ignored=bool(p.get("ignore"));expected=None if cue["distractor"] else (cue["old_route"] if cue["wave"]==1 else cue["new_route"])
  rows.append({"arrival_id":cue["arrival_id"],"wave":cue["wave"],"cargo_id":cue["cargo_id"],"distractor":cue["distractor"],"selected_destination":selected,"ignored":ignored,"correct":(ignored if cue["distractor"] else selected==expected and not ignored),"expected_destination":expected,"response_time_ms":a.get("elapsed_ms")})
 return {"activity_id":"HY-04","evaluation_version":EVALUATION_VERSION,"arrivals_presented":len(rows),"arrivals_expected":len(stream),"correct_dispatches":sum(r["correct"] for r in rows),"dispatch_total":len(rows),"ignored_distractors":sum(r["distractor"] and r["ignored"] for r in rows),"manifest_matches":sum((not r["distractor"]) and r["selected_destination"]==manifest.get(r["cargo_id"]) for r in rows),"wave_results":[{"wave":wave,"correct":sum(r["correct"] for r in rows if r["wave"]==wave),"presented":sum(r["wave"]==wave for r in rows)} for wave in range(1,config["wave_count"]+1)],"dispatch_history":rows}
