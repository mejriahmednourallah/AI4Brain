import {useCallback,useEffect,useRef,useState,type ReactNode} from 'react';
import {ArrowLeft,LoaderCircle} from 'lucide-react';
import { emitCompanionCheckpoint, type CompanionCheckpointHandler, type TimedWindowHandler } from '../../companionCheckpoint';
import {completeHybridAttempt,fetchHybridAttempt,fetchHy02ReviewHistory,hybridUid,recordHybridAction,recordHybridAssistance,startHybridAttempt,type HybridActivity,type Hy02ReviewCue,type Hy02ReviewHistory} from './hybridClient';
import tideScene from '../games/assets/scene36.png';
import marketScene from '../games/assets/scene37.png';
import harborScene from '../games/assets/scene36.png';
import bridgeScene from '../games/assets/scene38.png';
import memoryTile from '../games/assets/prepared/memory-tile-teal.png';
import memoryLantern from '../games/assets/prepared/memory-lantern.png';
import flexibilityPlaqueBase from '../games/assets/prepared/flexibility-plaque-a.png';
import flexibilityPlaqueTile from '../games/assets/prepared/flexibility-plaque-b.png';
import planningPawn from '../games/assets/prepared/planning-pawn.png';
import bridgeArt from '../games/assets/prepared/harbor-bridge-straight.png';
import bridgePaver from '../games/assets/prepared/planning-paver-4.png';
import harborGate from '../games/assets/prepared/harbor-gate.png';
import harborBuoy from '../games/assets/prepared/harbor-buoy.png';
import harborBoatBlue from '../games/assets/prepared/harbor-boat-blue.png';
import harborCrate from '../games/assets/prepared/harbor-crate.png';
import harborPlaque from '../games/assets/prepared/harbor-plaque.png';
import hybridKey from '../games/assets/prepared/hybrid-key.png';
import hybridTray from '../games/assets/prepared/hybrid-tray.png';
import hybridParcel from '../games/assets/prepared/hybrid-parcel.png';
import attentionDais from '../games/assets/prepared/attention-dais.png';
import attentionRail from '../games/assets/prepared/attention-railing.png';
import hybridTablet from '../games/assets/prepared/hybrid-tablet.png';

type Props={activity:HybridActivity;sessionId:string;onExit:()=>void;onRecorded?:()=>void;initialAttemptId?:string|null;onCheckpoint?:CompanionCheckpointHandler;onTimedWindowChange?:TimedWindowHandler};
type Started={attempt_id:string;config:any;next_sequence?:number;events?:any[];recovered?:boolean;completion_event_id?:string};
function EvidenceReceipt({attempt}:{attempt:Started}){const out=attempt.config.__outcome;if(!out)return null;const ids: string[]=out.evidence_ids??[];const events=attempt.events??[];return <details className="hy-evidence"><summary>Recorded evidence ({ids.length} event records)</summary><ol>{ids.map(id=>{const event=events.find(e=>e.event_id===id);return <li id={`hy-evidence-${id}`} key={id}><a href={`#hy-evidence-${id}`}><code>{id}</code></a>{event&&<> · event {event.sequence} · {event.type}<details><summary>Payload</summary><pre>{JSON.stringify(event.payload,null,2)}</pre></details></>}</li>})}</ol><a href={`/api/hybrid/attempts/${attempt.attempt_id}`} target="_blank" rel="noreferrer">Open canonical attempt record</a></details>}

function TideCueBoard({cue,label,comparison}:{cue:Hy02ReviewCue;label:string;comparison:boolean}){
 const validPosition=Number.isInteger(cue.position)&&cue.position>=0&&cue.position<9;
 return <figure className={`tide-replay-cue${comparison?' is-comparison':''}`}>
  <figcaption><strong>{label}</strong>{comparison&&<span>Compared cue</span>}</figcaption>
  <div className="tide-replay-grid" role="img" aria-label={`${label}: ${validPosition?`position ${cue.position+1} of 9`:'position unavailable'}, symbol ${cue.symbol||'unavailable'}`}>
   {Array.from({length:9},(_,cell)=><span className={validPosition&&cell===cue.position?'is-active':''} key={cell}>{validPosition&&cell===cue.position?cue.symbol:''}</span>)}
  </div>
 </figure>
}

function TidekeeperCueReplay({attempt,sessionId}:{attempt:Started;sessionId:string}){
 const [history,setHistory]=useState<Hy02ReviewHistory|null>(null),[selectedTrial,setSelectedTrial]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(''),[progress,setProgress]=useState('');
 const inFlight=useRef(false);
 const replay=async()=>{
  if(inFlight.current)return;
  inFlight.current=true;setBusy(true);setError('');setProgress('Saving replay permission before opening saved cues.');
  try{
   const sourceEventId=attempt.completion_event_id??(attempt.events??[]).find(event=>event.type==='hybrid_attempt_completed')?.event_id;
   if(!sourceEventId)throw new Error('The saved completion reference is unavailable. Your recorded result is unchanged.');
   const key=`hy-cue-replay:${sessionId}:${attempt.attempt_id}`;
   let request:{event_id:string;exposure_kind:'cue_replay';checkpoint:'post_window';source_event_id:string};
   const pending=localStorage.getItem(key);
   if(pending){
    try{request=JSON.parse(pending)}catch{throw new Error('The saved replay request is unreadable. Your recorded result is unchanged.')}
    if(request.exposure_kind!=='cue_replay'||request.checkpoint!=='post_window'||request.source_event_id!==sourceEventId||!request.event_id)throw new Error('A different replay request is already saved for this attempt. Your recorded result is unchanged.');
   }else{
    request={event_id:hybridUid(),exposure_kind:'cue_replay',checkpoint:'post_window',source_event_id:sourceEventId};
    localStorage.setItem(key,JSON.stringify(request));
   }
   const accepted=await recordHybridAssistance(attempt.attempt_id,request);
   if(!accepted.accepted||!accepted.event_id)throw new Error('Replay permission was not recorded. No cue history was opened.');
   setProgress('Replay permission recorded; loading the saved cue history.');
   const result=await fetchHy02ReviewHistory(attempt.attempt_id,sessionId,accepted.event_id);
   if(result.attempt_id!==attempt.attempt_id||result.assistance_event_id!==accepted.event_id||result.activity_id!=='HY-02'||!Array.isArray(result.trials)||result.trials.length===0)throw new Error('The saved cue history did not match this replay request. Your recorded result is unchanged.');
   setSelectedTrial(0);setHistory(result);setProgress(`Replay permission ${result.assistance_event_id} is recorded.`);
  }catch(cause){setError(cause instanceof Error?cause.message:'The saved cue replay is unavailable. Your recorded result is unchanged.');}
  finally{inFlight.current=false;setBusy(false)}
 };
 const row=history?.trials[Math.min(selectedTrial,Math.max(0,(history?.trials.length??1)-1))];
 return <section className="tide-replay" aria-labelledby={`tide-replay-title-${attempt.attempt_id}`}>
  <div className="tide-replay-intro"><p className="tide-review-kicker">POST-ROUND ASSISTANCE · SAVED CUES</p><h3 id={`tide-replay-title-${attempt.attempt_id}`}>Replay evidence</h3><p>This optional replay is recorded assistance and does not change the saved result.</p>
   <button className="hy-primary tide-replay-trigger" type="button" disabled={busy} onClick={()=>history?setHistory(null):void replay()}>{busy?'Recording replay…':history?'Hide cue replay':'Replay saved cues'}</button>
   <p className="tide-replay-status" role="status">{busy?progress:history?`Saved cue history opened for ${history.trials.length} completed trials. ${progress}`:progress}</p>
   {error&&<p className="hy-error" role="alert">{error}</p>}
  </div>
  {history&&row&&<div className="tide-replay-detail">
   <div className="tide-replay-toolbar"><label htmlFor={`tide-replay-trial-${attempt.attempt_id}`}>Completed cue</label><select id={`tide-replay-trial-${attempt.attempt_id}`} value={selectedTrial} onChange={event=>setSelectedTrial(Number(event.target.value))}>{history.trials.map((trial,index)=><option key={trial.cue_event_id} value={index}>Trial {trial.trial_index+1} of {history.stream_count}</option>)}</select><span>{history.n_back}-back comparison</span></div>
   <div className="tide-replay-cues" role="group" aria-label={`Saved cues for trial ${row.trial_index+1}`}>
    {row.history_cues.map((cue,index)=><TideCueBoard key={cue.cue_id} cue={cue} label={`${row.history_cues.length-index} step${row.history_cues.length-index===1?'':'s'} ago`} comparison={row.comparison_cue?.cue_id===cue.cue_id}/>)}
    <TideCueBoard cue={row.current_cue} label="Current cue" comparison={false}/>
   </div>
   {!row.comparison_cue&&<p className="tide-replay-note">This cue has no {history.n_back}-back comparison yet; earlier stream history is not available for it.</p>}
   <p className="tide-replay-note">Saved {history.activity_version} cue stream · replay event <code>{history.assistance_event_id}</code>.</p>
   <p className="tide-replay-note">Saved response: position {row.position_match_response?'match':'no match'}; symbol {row.symbol_match_response?'match':'no match'}. Cue record <code>{row.cue_event_id}</code>.</p>
  </div>}
 </section>
}

function useAttempt(activity:HybridActivity,sessionId:string,initialAttemptId?:string|null){
 const [attempt,setAttempt]=useState<Started|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{let live=true;setAttempt(null);setError('');void(async()=>{try{const key=`hy-active:${sessionId}:${activity.activity_id}`,startKey=`${key}:start`,saved=initialAttemptId||localStorage.getItem(key);if(saved){const a=await fetchHybridAttempt(saved);if(!live)return;if(initialAttemptId)localStorage.setItem(key,saved);const pendingKey=`hy-pending-action:${saved}`,pending=localStorage.getItem(pendingKey);if(pending&&a.events.some(e=>e.event_id===JSON.parse(pending).event_id))localStorage.removeItem(pendingKey);const completionKey=`hy-pending-completion:${saved}`,completionRaw=localStorage.getItem(completionKey);if(a.outcome&&completionRaw){try{const completion=JSON.parse(completionRaw),event=a.events.find(e=>e.type==='hybrid_attempt_completed');if(event&&event.event_id===completion.event_id&&Boolean(event.payload.interrupted)===Boolean(completion.interrupted)&&Boolean(event.payload.visibility_interrupted)===Boolean(completion.visibility_interrupted)&&event.payload.response_time_ms===(completion.response_time_ms??null))localStorage.removeItem(completionKey);}catch{/* Keep malformed or nonmatching completion evidence for inspection. */}}const completionEvent=a.events.find(e=>e.type==='hybrid_attempt_completed');setAttempt({attempt_id:saved,config:{...a.config,__outcome:a.outcome},next_sequence:a.events.filter(e=>e.type==='hybrid_action_recorded').length+1,events:a.events,recovered:true,completion_event_id:completionEvent?.event_id});if(a.outcome&&localStorage.getItem(key)===saved)localStorage.removeItem(key);return;}let pending=localStorage.getItem(startKey);if(!pending){pending=JSON.stringify({event_id:hybridUid(),session_id:sessionId,activity_id:activity.activity_id,activity_version:activity.activity_version,mode:'training',difficulty_tier:'tier-1'});localStorage.setItem(startKey,pending);}const a=await startHybridAttempt(JSON.parse(pending));if(live){setAttempt({...a,next_sequence:1,events:[],recovered:false});localStorage.setItem(key,a.attempt_id);localStorage.removeItem(startKey);}}catch(e){if(live)setError(e instanceof Error?e.message:'Could not start activity.');}})();return()=>{live=false}},[activity.activity_id,activity.activity_version,sessionId,retry,initialAttemptId]);
 return {attempt,setAttempt,busy,setBusy,error,setError,retryStart:()=>{setError('');setRetry(value=>value+1)}};
}
function ActionGame({activity,sessionId,onExit,onRecorded,initialAttemptId,onCheckpoint,onTimedWindowChange,children}:{activity:HybridActivity;sessionId:string;onExit:()=>void;onRecorded?:()=>void;initialAttemptId?:string|null;onCheckpoint?:CompanionCheckpointHandler;onTimedWindowChange?:TimedWindowHandler;children:(attempt:Started,act:(type:'select'|'commit'|'advise'|'respond',payload:Record<string,unknown>,cueEventId?:string)=>Promise<void>,finish:()=>Promise<void>)=>ReactNode}){
 const {attempt,setAttempt,busy,setBusy,error,setError,retryStart}=useAttempt(activity,sessionId,initialAttemptId);const [readyAttempt,setReadyAttempt]=useState<string|null>(null);const seq=useState(()=>({n:1}))[0],inflight=useRef(false),interruptionRequested=useRef(false),finishRef=useRef<((interrupted?:boolean)=>Promise<void>)|null>(null);
 useEffect(()=>{if(attempt)seq.n=attempt.next_sequence??1},[attempt,seq]);
 useEffect(()=>{if(attempt&&!attempt.config.__outcome)emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:ready`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'ready',text:`${activity.title} is ready. Begin when you are comfortable.`});return()=>onTimedWindowChange?.(false)},[attempt?.attempt_id,attempt?.config.__outcome,sessionId,activity.activity_id,activity.title,onCheckpoint,onTimedWindowChange]);
 const act=useCallback(async(type:'select'|'commit'|'advise'|'respond',payload:Record<string,unknown>,cueEventId?:string,elapsedMs?:number)=>{if(!attempt)throw new Error('Attempt is not ready.');if(inflight.current)throw new Error('Another save is in progress; retry this action.');inflight.current=true;setBusy(true);const key=`hy-pending-action:${attempt.attempt_id}`;let pending=localStorage.getItem(key);if(pending){const old=JSON.parse(pending);if(old.action_type!==type||JSON.stringify(old.payload)!==JSON.stringify(payload)||old.cue_event_id!==cueEventId||old.elapsed_ms!==(elapsedMs??0)){setError('A previous action still needs its exact retry.');inflight.current=false;setBusy(false);throw new Error('Retry the pending action.');}}else{pending=JSON.stringify({event_id:hybridUid(),sequence:seq.n,action_type:type,payload,cue_event_id:cueEventId,elapsed_ms:elapsedMs??0});localStorage.setItem(key,pending);}try{const request=JSON.parse(pending);await recordHybridAction(attempt.attempt_id,{...request});localStorage.removeItem(key);seq.n++;setError('');emitCompanionCheckpoint(onCheckpoint,{id:request.event_id,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'checkpoint',text:'That game action was saved. Continue when you are ready.'});}catch(e){setError(e instanceof Error?e.message:'Action did not save.');throw e}finally{inflight.current=false;setBusy(false);if(interruptionRequested.current){interruptionRequested.current=false;void finishRef.current?.(true)}}},[attempt,seq,setBusy,setError,onCheckpoint,sessionId,activity.activity_id]);
 const finish=useCallback(async(interrupted=false)=>{if(!attempt)return;if(inflight.current){if(interrupted)interruptionRequested.current=true;return;}inflight.current=true;setBusy(true);const key=`hy-pending-completion:${attempt.attempt_id}`;let request=localStorage.getItem(key);if(request){const old=JSON.parse(request);if(Boolean(old.interrupted)!==interrupted){setError('A completion is already pending; retry its exact saved request.');inflight.current=false;setBusy(false);return;}}else{request=JSON.stringify({event_id:hybridUid(),interrupted});localStorage.setItem(key,request)}try{const out=await completeHybridAttempt(attempt.attempt_id,JSON.parse(request));localStorage.removeItem(key);localStorage.removeItem(`hy-active:${sessionId}:${activity.activity_id}`);if(activity.activity_id==='HY-02')localStorage.removeItem(`hy-block-active:${attempt.attempt_id}`);onRecorded?.();setAttempt({...attempt,config:{...attempt.config,__outcome:out},completion_event_id:JSON.parse(request).event_id});if(!interrupted)emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:completed`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'completed',text:'The activity is complete. Its saved outcome is ready to review.'});setError('')}catch(e){setError(e instanceof Error?e.message:'Could not complete attempt.');}finally{inflight.current=false;setBusy(false)}},[attempt,sessionId,activity.activity_id,onRecorded,setAttempt,setBusy,setError,onCheckpoint]);
 finishRef.current=finish;
 const scene=activity.activity_id==='HY-02'?tideScene:activity.activity_id==='HY-03'?marketScene:activity.activity_id==='HY-04'?harborScene:bridgeScene;
  const explicitReady = activity.activity_id === 'HY-03' || activity.activity_id === 'HY-04' || activity.activity_id === 'HY-06';
  const intro = activity.activity_id === 'HY-03' ? 'Study the shipment order, route each parcel by the current market rule, and switch rules when the market changes. The memorization timer starts when you begin.' : activity.activity_id === 'HY-04' ? 'Remember the cargo manifest, then route marked arrivals and ignore decoys across the harbor waves. The manifest timer starts when you begin.' : 'Propose a route, inspect the cited evidence, decide how to handle council advice, then commit your resolution.';
  return <section className={`hy-game hy-activity-${activity.activity_id.toLowerCase()}`}><div className="hy-scene-banner" style={{backgroundImage:`linear-gradient(90deg,rgba(15,24,42,.18),rgba(15,24,42,.8)),url(${scene})`}} aria-hidden="true"><span>{activity.world.toUpperCase()} · {activity.title.toUpperCase()}</span></div><button className="hy-ghost" onClick={onExit}><ArrowLeft size={16}/> Back to Original activities</button><div className="hy-panel"><p className="hy-eyebrow">{activity.activity_id} · {activity.activity_version}</p><h1>{activity.title}</h1>{error&&<p className="hy-error" role="alert">{error}</p>}{!attempt&&<div role={error?'alert':'status'}>{error?<><p>The activity could not be prepared. Your exact saved start request is retained.</p><button className="hy-primary" type="button" onClick={retryStart}>Retry activity preparation</button></>:<><LoaderCircle className="spin"/><p>Preparing your saved activity…</p></>}</div>}{attempt?.recovered&&readyAttempt!==attempt.attempt_id&&<p className="hy-tip" role="status">Saved attempt restored. Continue from its recorded activity state; past actions are not replayed.</p>}{attempt?.config.__outcome?<div className={activity.activity_id==='HY-02'?'tide-review-shell':undefined}><h2>Attempt recorded</h2><p role="status">{attempt.config.__outcome.completion_state === 'interrupted' ? 'Interrupted attempt. These partial results are excluded from unassisted summaries.' : attempt.config.__outcome.excluded_from_unassisted ? 'Assisted attempt. These results are excluded from unassisted summaries.' : 'Completed unassisted attempt.'}</p><OutcomeSummary activityId={activity.activity_id} outcomes={attempt.config.__outcome.outcomes}/><EvidenceReceipt attempt={attempt}/>{activity.activity_id==='HY-02'&&attempt.config.__outcome.completion_state==='completed'&&<TidekeeperCueReplay attempt={attempt} sessionId={sessionId}/>}<button className="hy-primary" onClick={onExit}>Return</button></div>:attempt&&explicitReady&&readyAttempt!==attempt.attempt_id?<section className="hy-panel hy-ready-gate"><h2>Ready when you are</h2><p>{intro}</p><button className="hy-primary" type="button" onClick={()=>setReadyAttempt(attempt.attempt_id)}>{attempt.recovered?'Resume saved attempt':'Begin activity'}</button></section>:attempt&&children(attempt,act,finish)}{busy&&<span role="status">Saving…</span>}</div></section>
}
function TideChannelReview({name,expected,response,correct}:{name:string;expected:boolean;response:boolean;correct:boolean}){const result=correct?(expected?'Correct match':'Correct rejection'):(expected?'Missed match':'False alarm');return <section className="tide-review-channel" aria-label={`${name} comparison`}><h4>{name}</h4><p><span>Expected</span><strong>{expected?'Match':'No match'}</strong></p><p><span>Recorded</span><strong>{response?'Match':'No match'}</strong></p><span className={`tide-review-result${correct?' is-correct':' is-incorrect'}`}>{result}</span></section>}
function OutcomeSummary({activityId,outcomes}:{activityId:string;outcomes:any}){
 if(activityId==='HY-02')return <>
  <div className="tide-review-layout">
   <aside className="tide-review-overview" aria-label="Saved channel summary">
    <p className="tide-review-kicker">COACH REVIEW · SAVED RECORD</p>
    <section className="tide-review-summary" aria-label="Recorded channel summary">
     <article><h3>Position</h3><strong>{outcomes.position_correct}/{outcomes.position_total} correct</strong><p>{outcomes.false_alarms?.position??0} false alarms · {outcomes.misses?.position??0} missed matches</p></article>
     <article><h3>Symbol</h3><strong>{outcomes.symbol_correct}/{outcomes.symbol_total} correct</strong><p>{outcomes.false_alarms?.symbol??0} false alarms · {outcomes.misses?.symbol??0} missed matches</p></article>
    </section>
    <p className="tide-review-context">Each trial compares position and symbol with the cue {outcomes.n_back} step{outcomes.n_back===1?'':'s'} earlier. {outcomes.trials_presented} of {outcomes.trials_expected} trials have recorded responses.</p>
    <p className="tide-review-limit">This summary shows saved comparisons and decisions. Use the separate “Replay saved cues” control below to open recorded cue boards after replay assistance is saved. A recorded “No match” does not distinguish an explicit choice from the window-end default.</p>
   </aside>
   <details className="tide-review" open><summary>Review recorded cue responses</summary>
    <ol className="tide-review-list">{outcomes.responses.map((row:any)=><li key={row.trial_index}>
     <header><div><strong>Trial {row.trial_index+1}</strong><small>{row.cue_event_id}</small></div><span>{row.response_time_ms==null?'Time not recorded':`${row.response_time_ms} ms recorded`}</span></header>
     <div className="tide-review-channels"><TideChannelReview name="Position" expected={Boolean(row.position_match_expected)} response={Boolean(row.position_match_response)} correct={Boolean(row.position_correct)}/><TideChannelReview name="Symbol" expected={Boolean(row.symbol_match_expected)} response={Boolean(row.symbol_match_response)} correct={Boolean(row.symbol_correct)}/></div>
    </li>)}</ol>
   </details>
  </div>
 </>;
 if(activityId==='HY-03')return <p>{outcomes.shipment_order_matches}/{outcomes.shipment_order_total} shipment positions and {outcomes.routing_matches}/{outcomes.routing_total} routes matched the recorded rules.</p>;
 if(activityId==='HY-04')return <p>{outcomes.correct_dispatches}/{outcomes.dispatch_total} dispatch decisions matched; {outcomes.ignored_distractors} distractors ignored.</p>;
 if(activityId==='HY-06')return <p>Final route {outcomes.final_route?.feasible?'was feasible':'was not feasible'}; advice decision: {outcomes.advice_decision??'none'}; supported by inspected evidence: {outcomes.decision_justified_by_recorded_evidence?'yes':'no'}.</p>;
 return <p>{JSON.stringify(outcomes)}</p>
}
export function ShiftingMarketGame(props:Props){return <ActionGame {...props}>{(a,act,finish)=><MarketBoard attempt={a} act={act} finish={finish} sessionId={props.sessionId} onCheckpoint={props.onCheckpoint} onTimedWindowChange={props.onTimedWindowChange}/>}</ActionGame>}
function MarketBoard({attempt,act,finish,sessionId,onCheckpoint,onTimedWindowChange}:{attempt:Started;act:(t:'select'|'commit'|'advise',p:Record<string,unknown>)=>Promise<void>;finish:()=>Promise<void>;sessionId:string;onCheckpoint?:CompanionCheckpointHandler;onTimedWindowChange?:TimedWindowHandler}){
 const c=attempt.config,attemptKey=`hy-active:${attempt.attempt_id}`,timestampKey=`${attemptKey}:encode-start`;
 const pendingRoute=(()=>{try{const value=JSON.parse(localStorage.getItem(`hy-pending-action:${attempt.attempt_id}`)??'null');return value?.action_type==='select'&&value?.payload?.cargo_id&&value?.payload?.bin_id?value:null}catch{return null}})();
 const recorded=(attempt.events??[]).filter(e=>e.type==='hybrid_action_recorded'&&e.payload?.action_type==='select').map(e=>e.payload.action?.cargo_id).filter(Boolean) as string[];
 const [index,setIndex]=useState(recorded.length),[used,setUsed]=useState<string[]>(recorded),[selected,setSelected]=useState<string|null>(pendingRoute?.payload.cargo_id??null),[encoding,setEncoding]=useState(()=>recorded.length===0&&!pendingRoute);
 const introActive=useRef(recorded.length===0&&!pendingRoute);
 useEffect(()=>{onTimedWindowChange?.(encoding);if(!encoding){if(introActive.current){introActive.current=false;emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:play-open`,sessionId,activityId:'HY-03',attemptId:attempt.attempt_id,kind:'checkpoint',text:'The study period has ended. Continue with the activity when you are ready.'});}return;}let start=Number(localStorage.getItem(timestampKey));if(!start){start=Date.now();localStorage.setItem(timestampKey,String(start));}const remaining=Math.max(0,(c.encode_ms??6000)-(Date.now()-start));if(remaining===0&&recorded.length===0){const eventKey=`${attemptKey}:encode-help`;let pending=localStorage.getItem(eventKey);if(!pending){pending=JSON.stringify({event_id:hybridUid(),exposure_kind:'hidden_information_replay',checkpoint:'pre_play'});localStorage.setItem(eventKey,pending);}void recordHybridAssistance(attempt.attempt_id,JSON.parse(pending)).then(()=>{localStorage.removeItem(eventKey);setEncoding(false)}).catch(()=>undefined);return;}const timer=window.setTimeout(()=>setEncoding(false),remaining);return()=>window.clearTimeout(timer)},[attempt.attempt_id,c.encode_ms,encoding,attemptKey,timestampKey,recorded.length,onTimedWindowChange,onCheckpoint,sessionId]);
 const remaining=c.cargo.filter((p:any)=>!used.includes(p.cargo_id)),rule=index<c.switch.after_step?'color':'shape';
 if(encoding)return <section className="market-world market-study-world" style={{backgroundImage:`linear-gradient(180deg,rgba(16,34,57,.08),rgba(16,34,57,.20)),url(${marketScene})`}} aria-label="Shipment study phase"><header className="market-rule-sign market-study-sign"><img src={hybridTablet} alt=""/><div><span>Shipment order</span><strong>Memorize the delivery sequence</strong><small>The active sorting rule stays visible during play.</small></div></header><div className="market-study-tiles">{c.study_sequence.map((id:string,i:number)=>{const parcel=c.cargo.find((x:any)=>x.cargo_id===id);return <figure key={`${id}-${i}`}><img className="market-study-stone" src={memoryTile} alt=""/><span className={`market-symbol is-${parcel?.color} is-${parcel?.shape}`} aria-hidden="true"/><figcaption>{parcel?.label}</figcaption><small>Stop {i+1}</small></figure>})}</div><p className="market-study-timer">The sequence hides after {Math.ceil((c.encode_ms??6000)/1000)} seconds.</p></section>;
 if(!remaining.length)return <div><p>Every parcel has been routed.</p><button className="hy-primary" onClick={()=>void finish()}>Review outcome</button></div>;
 async function routeCargo(bin:string){if(!selected)return;try{await act('select',{cargo_id:selected,bin_id:bin});setUsed([...used,selected]);setIndex(index+1);setSelected(null)}catch{}}
  const activeBins=Object.values(c.rules[`${rule}_bins`]) as string[];
  const selectedParcel=c.cargo.find((p:any)=>p.cargo_id===selected);
  return <section className="market-world" style={{backgroundImage:`linear-gradient(180deg,rgba(15,29,47,.06),rgba(15,29,47,.22)),url(${marketScene})`}} aria-label="Shifting Market sorting board">
   <header className="market-rule-sign"><img className="market-rule-sign-art" src={hybridTablet} alt=""/><div><span>Shipment {index+1} / {c.cargo.length} · {index<c.switch.after_step?'COLOR SORT':'SHAPE SORT'}</span><strong>{index<c.switch.after_step?'Sort by color':'Sort by shape'}</strong><small>{index===c.switch.after_step?'Rule changed. Apply the new rule from this delivery.':`After ${c.switch.after_step} deliveries, switch to shape.`}</small></div><img className="market-rule-medallion" src={harborPlaque} alt=""/></header>
   <div className="market-sorting-deck"><div className="market-deck-heading"><strong>Sorting trays</strong><span>{selectedParcel?`Route ${selectedParcel.label} by ${rule}.`:'Select the next parcel in the remembered order.'}</span></div><div className="market-bin-grid">{activeBins.map((bin:string)=>{const value=bin.split('-')[0];const glyphClass=rule==='color'?`is-color-${value}`:`is-shape-${value}`;return <button type="button" className="market-stone-bin" key={bin} aria-label={`Route to ${value}`} disabled={!selected||Boolean(pendingRoute)&&bin!==pendingRoute.payload.bin_id} onClick={()=>void routeCargo(bin)}><img src={hybridTray} alt=""/><span className={`market-bin-glyph ${glyphClass}`} aria-hidden="true"/><strong>{value}</strong></button>})}</div></div>
   <div className="market-cargo-tray"><div className="market-cargo-heading"><strong>Next parcels</strong><span>{remaining.length} remaining</span></div>{remaining.map((parcel:any)=><button type="button" className={`market-cargo-token ${selected===parcel.cargo_id?'is-selected':''}`} key={parcel.cargo_id} aria-pressed={selected===parcel.cargo_id} disabled={Boolean(pendingRoute)} onClick={()=>setSelected(parcel.cargo_id)}><img src={hybridParcel} alt=""/><span className={`market-symbol is-${parcel.color} is-${parcel.shape}`} aria-hidden="true"/><strong>{parcel.label}</strong></button>)}</div>
   {pendingRoute&&<div role="alert" className="hy-error market-action-error">This route did not save. Retry the same parcel and route.<button className="hy-primary" type="button" onClick={()=>void routeCargo(String(pendingRoute.payload.bin_id))}>Retry exact saved route action</button></div>}
  </section>
}
export function BridgeCouncilGame(props:Props){return <ActionGame {...props}>{(a,act,finish)=><BridgeBoard attempt={a} act={act} finish={finish}/>}</ActionGame>}
function BridgeBoard({attempt,act,finish}:{attempt:Started;act:(t:'select'|'commit'|'advise',p:Record<string,unknown>)=>Promise<void>;finish:()=>Promise<void>}){
 const c=attempt.config,actions=(attempt.events??[]).filter(e=>e.type==='hybrid_action_recorded').map(e=>e.payload);
 const mapPoints:Record<string,[number,number]>={harbor:[120,270],'key-island':[350,125],'old-bridge':[590,285],northbank:[390,470],lighthouse:[850,185]};
 const [mapSize,setMapSize]=useState({width:700,height:480}),mapRef=useRef<HTMLDivElement>(null);
 useEffect(()=>{const element=mapRef.current;if(!element)return;const observer=new ResizeObserver(entries=>{const box=entries[0]?.contentRect;if(box?.width&&box?.height)setMapSize({width:box.width,height:box.height})});observer.observe(element);return()=>observer.disconnect()},[]);
 const edgeLabels:any[]=[];c.edges.forEach((edge:any,index:number)=>{const [x1,y1]=mapPoints[edge.from_node],[x2,y2]=mapPoints[edge.to_node],dx=(x2-x1)*mapSize.width/1000,dy=(y2-y1)*mapSize.height/600,length=Math.max(1,Math.hypot(dx,dy)),mx=(x1+x2)/2*mapSize.width/1000,my=(y1+y2)/2*mapSize.height/600,nx=-dy/length,ny=dx/length,hasState=Boolean(edge.closed||edge.requires_key),mobile=mapSize.width<600,halfW=hasState?(mobile?47:44):(mobile?27:28),halfH=hasState?20:16,nodeW=mobile?42:71,nodeH=mobile?38:59,prior=edgeLabels.map(item=>({x:item.x,y:item.y,halfW:item.halfW,halfH:item.halfH}));const safe=(x:number,y:number)=>{if(x<halfW+4||x>mapSize.width-halfW-4||y<halfH+4||y>mapSize.height-halfH-4)return false;for(const node of c.nodes){const [px,py]=mapPoints[node.node_id]??[500,300],cx=px*mapSize.width/1000,cy=py*mapSize.height/600;if(Math.abs(x-cx)<halfW+nodeW+5&&Math.abs(y-cy)<halfH+nodeH+5)return false}return !prior.some(item=>Math.abs(x-item.x)<halfW+item.halfW+8&&Math.abs(y-item.y)<halfH+item.halfH+8)};const signs=index%2?[1,-1]:[-1,1];let point:any=null;for(const offset of [34,46,60,76,96,120,148,180]){for(const sign of signs){const x=mx+nx*offset*sign,y=my+ny*offset*sign;if(safe(x,y)){point={x,y};break}}if(point)break}if(!point){let best=Infinity;for(let y=halfH+6;y<=mapSize.height-halfH-6;y+=14)for(let x=halfW+6;x<=mapSize.width-halfW-6;x+=14)if(safe(x,y)){const score=Math.hypot(x-mx,y-my);if(score<best){best=score;point={x,y}}}}if(!point)point={x:Math.max(halfW+4,Math.min(mapSize.width-halfW-4,mx)),y:Math.max(halfH+4,Math.min(mapSize.height-halfH-4,my))};edgeLabels.push({...point,hasState,halfW,halfH})});
 let recoveredStage:'proposal'|'advice'|'resolution'|'done'='proposal',recoveredDecision='';const priorRefs:string[]=[];
 for(const a of actions){const kind=a.action_type,p=a.action??{};if(kind==='commit'&&p.stage==='proposal')recoveredStage='advice';if(kind==='advise'){recoveredStage='resolution';recoveredDecision=p.decision??'';priorRefs.push(...(p.inspected_refs??[]));}if(kind==='commit'&&p.stage==='resolution')recoveredStage='done';}
 const stageRoute=(name:string)=>[c.start_node,...actions.filter(a=>a.action_type==='select'&&a.action?.stage===name).map(a=>a.action.node_id)];const proposed=stageRoute('proposal'),resolved=stageRoute('resolution');
 const [stage,setStage]=useState<'proposal'|'advice'|'resolution'|'done'>(recoveredStage),[route,setRoute]=useState<string[]>(recoveredStage==='resolution'||recoveredStage==='done'?resolved:proposed),[decision,setDecision]=useState(recoveredDecision),[inspected,setInspected]=useState<string[]>([...new Set(priorRefs)]);
 const adjacent=(node:string)=>c.edges.filter((e:any)=>(e.from_node===node||e.to_node===node)&&!route.includes(e.from_node===node?e.to_node:e.from_node));
 const next=async(node:string)=>{try{await act('select',{stage:stage==='resolution'?'resolution':'proposal',node_id:node});setRoute([...route,node])}catch{}};
 async function decide(choice:'accept'|'reject'|'hold'){const constraint=choice==='reject'?'constraint-key-before-gate':'';try{await act('advise',{decision:choice,constraint_id:constraint,inspected_refs:inspected});setDecision(choice);setStage('resolution');setRoute([c.start_node])}catch{}}
 return <><p>{stage==='proposal'?'Inspect the chart, then propose a connected route from Harbor to the Lighthouse.':stage==='advice'?c.advice.text:stage==='resolution'?'Use the graph evidence to assess the advice, then record a final route.':'Route saved.'}</p>
 <div className="bridge-council-layout"><div ref={mapRef} className="bridge-map" role="group" aria-label="Island graph. Select a connected island to extend the route. Bridge costs and gate states are shown on each configured connection."><svg viewBox="0 0 1000 600" preserveAspectRatio="none" aria-hidden="true">
  {c.edges.map((edge:any,index:number)=>{const [x1,y1]=mapPoints[edge.from_node],[x2,y2]=mapPoints[edge.to_node],mx=(x1+x2)/2,my=(y1+y2)/2,length=Math.hypot(x2-x1,y2-y1),angle=Math.atan2(y2-y1,x2-x1)*180/Math.PI-23,artWidth=Math.max(104,Math.min(220,length*.68)),artHeight=artWidth/1.2,point=edgeLabels[index],labelX=point.x*1000/mapSize.width,labelY=point.y*600/mapSize.height;return <g key={edge.edge_id} className={`bridge-edge ${edge.closed?'is-closed':''} ${edge.requires_key?'needs-key':''}`}><line x1={x1} y1={y1} x2={x2} y2={y2}/><image href={bridgeArt} x={mx-artWidth/2} y={my-artHeight/2} width={artWidth} height={artHeight} preserveAspectRatio="none" transform={`rotate(${angle} ${mx} ${my})`}/><line className="bridge-cost-leader" x1={mx} y1={my} x2={labelX} y2={labelY}/></g>})}
  <polyline className="bridge-route-line" points={route.map((id:string)=>mapPoints[id]?.join(',')).filter(Boolean).join(' ')}/>
 </svg>{c.edges.map((edge:any,index:number)=>{const point=edgeLabels[index],status=edge.closed?'CLOSED':edge.requires_key?'KEY REQUIRED':'';return <div key={`label-${edge.edge_id}`} data-edge-id={edge.edge_id} className={`bridge-cost-label ${edge.closed?'is-closed':edge.requires_key?'needs-key':''}`} style={{left:`${point.x}px`,top:`${point.y}px`}} aria-hidden="true" title={`${edge.weight} cost${status?`, ${status.toLowerCase()}`:''}`}><strong>{edge.weight}</strong>{status&&<span>{status}</span>}</div>})}{c.nodes.map((node:any)=>{const [x,y]=mapPoints[node.node_id]??[500,300],tail=route.at(-1)??c.start_node,edge=adjacent(tail).find((item:any)=>item.from_node===node.node_id||item.to_node===node.node_id),enabled=(stage==='proposal'||stage==='resolution')&&node.node_id!==tail&&Boolean(edge);return <button type="button" key={node.node_id} className={`bridge-island ${route.includes(node.node_id)?'is-on-route':''} ${node.kind==='goal'?'is-goal':''}`} style={{left:`${x/10}%`,top:`${y/6}%`}} disabled={!enabled} onClick={()=>void next(node.node_id)} aria-label={`${node.label}${enabled?', add to route':''}`}><img className="bridge-island-stone" src={bridgePaver} alt=""/><img className="bridge-island-icon" src={node.kind==='key'?hybridKey:node.kind==='goal'?attentionDais:planningPawn} alt=""/><strong>{node.label}</strong></button>})}</div>
 <aside className="bridge-council-panel"><div className="bridge-council-panel-heading"><span>BRIDGE COUNCIL</span><h3>{stage==='advice'?'Council advice':stage==='done'?'Decision recorded':'Route planning'}</h3></div>{stage==='advice'?<div className="bridge-advice-plaque"><img src={hybridTablet} alt=""/><p>{c.advice.text}</p><small>Advice evidence: {c.advice.evidence_refs.join(' · ')}</small><p>Inspect each cited item in the evidence panel before deciding.</p><div className="hy-actions"><button className="hy-primary" disabled={!c.advice.evidence_refs.every((id:string)=>inspected.includes(id))} onClick={()=>void decide('accept')}>Accept / modify</button><button className="hy-primary" disabled={!c.advice.evidence_refs.every((id:string)=>inspected.includes(id))} onClick={()=>void decide('reject')}>Reject with constraint</button><button className="hy-ghost" disabled={!c.advice.evidence_refs.every((id:string)=>inspected.includes(id))} onClick={()=>void decide('hold')}>Hold for uncertainty</button></div></div>:<p>{stage==='proposal'?'Select connected islands to propose a route.':stage==='resolution'?'Review the inspected evidence, then choose a final route.':`Decision saved: ${decision}`}</p>}</aside>
 <section className="bridge-route-dock" aria-label="Current route and route actions"><div><h3>{stage==='resolution'?'Resolution route':stage==='done'?'Recorded route':'My proposed route'}</h3><div className="bridge-route-pills">{route.map((node:string,i:number)=><span key={`${node}-${i}`}><img src={planningPawn} alt=""/>{c.nodes.find((n:any)=>n.node_id===node)?.label??node}</span>)}</div></div>{stage==='proposal'||stage==='resolution'?<div className="bridge-dock-actions"><p>Choose adjacent islands. Costs and gate states are shown on configured bridges.</p><button className="hy-primary" onClick={async()=>{try{await act('commit',{stage});if(stage==='proposal'){setStage('advice');setRoute([...route])}else setStage('done')}catch{}}}>Commit {stage}</button></div>:stage==='done'?<div className="bridge-dock-actions"><p>Decision saved: {decision}</p><button className="hy-primary" onClick={()=>void finish()}>Review outcome</button></div>:<p className="bridge-dock-advice-status">Inspect each cited item to enable a council decision.</p>}</section></div>
 <details className="hy-evidence bridge-inspector"><summary>Inspect edge weights and constraints</summary><table className="bridge-edges"><thead><tr><th>Bridge</th><th>Cost</th><th>State</th></tr></thead><tbody>{c.edges.map((e:any)=><tr key={e.edge_id}><td>{c.nodes.find((n:any)=>n.node_id===e.from_node)?.label} ↔ {c.nodes.find((n:any)=>n.node_id===e.to_node)?.label}</td><td>{e.weight}</td><td>{e.closed?'Closed':e.requires_key?'Requires key':'Open'}</td></tr>)}</tbody></table><ul>{c.constraints.map((item:any)=><li key={item.constraint_id}><label><input type="checkbox" checked={inspected.includes(item.constraint_id)} onChange={ev=>setInspected(ev.target.checked?[...inspected,item.constraint_id]:inspected.filter(id=>id!==item.constraint_id))}/> {item.text}</label></li>)}</ul></details></>
}

type StreamCue={complete:boolean;index:number;cue_id:string;position?:number;symbol?:string;n_back?:number;response_window_ms:number;wave?:number;cargo_id?:string;distractor?:boolean;rule?:string;marked_destination?:string|null;route_options?:string[]};
async function getStreamCue(id:string):Promise<StreamCue>{const r=await fetch(`/api/hybrid/attempts/${id}/stimulus`);const v=await r.json();if(!r.ok)throw new Error(v.detail??'Could not load next cue');return v;}
export function TidekeeperGame(props:Props){return <ActionGame {...props}>{(a,act,finish)=><TidekeeperBoard attempt={a} act={act} finish={finish} sessionId={props.sessionId} onCheckpoint={props.onCheckpoint} onTimedWindowChange={props.onTimedWindowChange}/>}</ActionGame>}
function TidekeeperBoard({attempt,act,finish,sessionId,onCheckpoint,onTimedWindowChange}:{attempt:Started;act:(t:'respond',p:Record<string,unknown>,cue?:string,elapsed?:number)=>Promise<void>;finish:(interrupted?:boolean)=>Promise<void>;sessionId:string;onCheckpoint?:CompanionCheckpointHandler;onTimedWindowChange?:TimedWindowHandler}){
 const [resumed]=useState(()=>Boolean(attempt.events?.some(e=>e.type==='hybrid_action_recorded')||localStorage.getItem(`hy-block-active:${attempt.attempt_id}`)));
 const [blockStarted,setBlockStarted]=useState(false),[cue,setCue]=useState<StreamCue|null>(null),[position,setPosition]=useState<boolean|null>(null),[symbol,setSymbol]=useState<boolean|null>(null),[error,setError]=useState(''),[hint,setHint]=useState(''),[pending,setPending]=useState<{payload:Record<string,unknown>;cue:string;elapsed:number}|null>(null);
 useEffect(()=>{onTimedWindowChange?.(blockStarted&&!cue?.complete);return()=>onTimedWindowChange?.(false)},[blockStarted,cue?.complete,onTimedWindowChange]);
 const answers=useRef({position:null as boolean|null,symbol:null as boolean|null}),sent=useRef(false),accepted=useRef(false),started=useRef(0),readyAt=useRef<number|null>(null),timedCueId=useRef<string|null>(null),actRef=useRef(act),finishRef=useRef(finish);
 actRef.current=act;finishRef.current=finish;
 function showCue(value:StreamCue){if(value.cue_id&&timedCueId.current===value.cue_id)return;if(value.cue_id){timedCueId.current=value.cue_id;started.current=performance.now()}setCue(value)}
 useEffect(()=>{if(resumed)void finishRef.current(true)},[attempt.attempt_id,resumed]);
 useEffect(()=>{if(!blockStarted||resumed)return;let mounted=true;void getStreamCue(attempt.attempt_id).then(v=>{if(mounted){showCue(v);if(v.complete)void finishRef.current()}}).catch(e=>setError(e.message));return()=>{mounted=false}},[attempt.attempt_id,blockStarted,resumed]);
 useEffect(()=>{if(!blockStarted||cue?.complete)return;const onVisibility=()=>{if(document.visibilityState==='hidden')void finish(true)};document.addEventListener('visibilitychange',onVisibility);return()=>document.removeEventListener('visibilitychange',onVisibility)},[blockStarted,cue?.complete,finish]);
 async function saveResponse(item:{payload:Record<string,unknown>;cue:string;elapsed:number}){if(!accepted.current){await actRef.current('respond',item.payload,item.cue,item.elapsed);accepted.current=true;}setError('');const next=await getStreamCue(attempt.attempt_id);setPosition(null);setSymbol(null);answers.current={position:null,symbol:null};sent.current=false;accepted.current=false;readyAt.current=null;setPending(null);if(next.complete){setCue(next);await finishRef.current()}else{showCue(next)}}
 async function requestStrategy(){const key=`hy-help:${attempt.attempt_id}:pre-block`;let raw=localStorage.getItem(key);if(!raw){raw=JSON.stringify({event_id:hybridUid(),exposure_kind:'strategy_prompt',checkpoint:'pre_block'});localStorage.setItem(key,raw)}try{const request=JSON.parse(raw);await recordHybridAssistance(attempt.attempt_id,request);localStorage.removeItem(key);setHint('Keep two separate rolling comparisons: one for position and one for symbol.');emitCompanionCheckpoint(onCheckpoint,{id:request.event_id,sessionId,activityId:attempt.config.activity_id??'HY-02',attemptId:attempt.attempt_id,kind:'assistance',text:'The recorded comparison strategy is available before the cue block.'})}catch(e){setError(e instanceof Error?e.message:'Help was not saved; retry before revealing it.')}}
 useEffect(()=>{if(!cue||cue.complete||pending)return;const timer=window.setTimeout(()=>{if(sent.current)return;sent.current=true;const elapsed=readyAt.current===null?cue.response_window_ms:Math.round(readyAt.current-started.current);const item={payload:{trial_index:cue.index,position_match:answers.current.position??false,symbol_match:answers.current.symbol??false},cue:cue.cue_id,elapsed};setPending(item);void saveResponse(item).catch(e=>setError(e instanceof Error?e.message:'Response not saved; retry the exact response.'))},cue.response_window_ms);return()=>window.clearTimeout(timer)},[cue,attempt.attempt_id,pending]);
 function pick(channel:'position'|'symbol',value:boolean){answers.current[channel]=value;if(answers.current.position!==null&&answers.current.symbol!==null&&readyAt.current===null)readyAt.current=performance.now();channel==='position'?setPosition(value):setSymbol(value)}
 return resumed?<div className="hy-tip"><p>This interrupted n-back stream is being recorded as interrupted so its prior-cue context is not silently lost.</p><button className="hy-primary" onClick={()=>void finish(true)}>Retry interruption record</button></div>:!blockStarted?<section><p>Watch each harbor cue and compare its position and symbol to the cue {attempt.config.n_back} steps earlier. The two channels have separate match/no-match pads. Each cue remains visible for a fixed response window.</p>{hint&&<p className="hy-tip">{hint}</p>}<div className="hy-actions"><button className="hy-ghost" onClick={()=>void requestStrategy()}>Ask for a recorded strategy hint</button><button className="hy-primary" onClick={()=>{onTimedWindowChange?.(true);localStorage.setItem(`hy-block-active:${attempt.attempt_id}`,'1');setError('');setBlockStarted(true)}}>Begin {attempt.config.trial_count}-cue block</button></div>{error&&<p className="hy-error" role="alert">{error}</p>}</section>:cue?.complete?<div><p>All cues completed. Outcome saved below.</p></div>:!cue?<><p>{error||'Loading the tide pattern…'}</p>{error&&<button className="hy-primary" onClick={()=>void getStreamCue(attempt.attempt_id).then(v=>{showCue(v);setError('');if(v.complete)void finishRef.current()}).catch(e=>setError(e.message))}>Retry loading current cue</button>}</>:<div className={`tide-play-surface${hint?' has-recorded-strategy':''}`}><p className="tide-cue-instruction">Compare with the cue {cue.n_back} step{cue.n_back===1?'':'s'} back. Respond to position and symbol separately.</p><p className="tide-cue-progress" aria-live="off">Cue {cue.index+1} of {attempt.config.trial_count}</p>{hint&&<aside className="tide-strategy-card" aria-label="Recorded strategy hint"><strong>Recorded strategy hint</strong><p>{hint}</p></aside>}<div className="tide-board-shell"><img className="tide-board-frame" src={flexibilityPlaqueBase} alt=""/><img className="tide-board-rail" src={attentionRail} alt="" aria-hidden="true"/><div className="tide-grid" role="img" aria-label={`Current cue: position ${(cue.position??0)+1} of 9, symbol ${cue.symbol}`}>{Array.from({length:9},(_,cell)=> <div className={`tide-cell ${cell===cue.position?'is-current':''}`} key={cell}><img src={flexibilityPlaqueTile} alt=""/>{cell===cue.position&&<span>{cue.symbol}</span>}</div>)}</div></div><div className="tide-response-pads">{(['position','symbol'] as const).map(channel=><fieldset className={`hy-choice-row tide-pad tide-pad-${channel}`} key={channel}><legend>{channel==='position'?'Position match?':'Symbol match?'}</legend><button type="button" disabled={Boolean(pending)} aria-pressed={(channel==='position'?position:symbol)===true} onClick={()=>pick(channel,true)}>Match</button><button type="button" disabled={Boolean(pending)} aria-pressed={(channel==='position'?position:symbol)===false} onClick={()=>pick(channel,false)}>No match</button></fieldset>)}</div><p className="tide-response-window">Response window: {(cue.response_window_ms/1000).toFixed(1)} seconds</p>{pending&&<button className="hy-primary" onClick={()=>void saveResponse(pending).catch(e=>setError(e.message))}>Retry saved response / load next cue</button>}{error&&<p className="hy-error" role="alert">{error}</p>}</div>}

export function HarborDispatchGame(props:Props){return <ActionGame {...props}>{(a,act,finish)=><HarborBoard attempt={a} act={act} finish={finish} sessionId={props.sessionId} onCheckpoint={props.onCheckpoint} onTimedWindowChange={props.onTimedWindowChange}/>}</ActionGame>}
function HarborBoard({attempt,act,finish,sessionId,onCheckpoint,onTimedWindowChange}:{attempt:Started;act:(t:'respond',p:Record<string,unknown>,cue?:string)=>Promise<void>;finish:()=>Promise<void>;sessionId:string;onCheckpoint?:CompanionCheckpointHandler;onTimedWindowChange?:TimedWindowHandler}) {
  const c=attempt.config,manifestKey=`hy-active:${attempt.attempt_id}:manifest-at`;
  const [encoding,setEncoding]=useState(() => !(attempt.events??[]).some(e=>e.type==='hybrid_action_recorded'));
  const [cue,setCue]=useState<StreamCue|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [betweenWave,setBetweenWave]=useState(false),[hint,setHint]=useState('');
  const [pendingDispatch,setPendingDispatch]=useState<{destination:string|null;cue:string}|null>(null);
  const acceptedDispatch=useRef(false),introActive=useRef(!(attempt.events??[]).some(e=>e.type==='hybrid_action_recorded'));
  const routeLabel=(destination:string)=>destination.split('-').map(part=>part.charAt(0).toUpperCase()+part.slice(1)).join(' ');

  useEffect(()=>{
    onTimedWindowChange?.(encoding);
    if(!encoding){
      if(introActive.current){introActive.current=false;emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:manifest-open`,sessionId,activityId:'HY-04',attemptId:attempt.attempt_id,kind:'checkpoint',text:'The manifest study period has ended. The next arrival is ready when you are.'});}
      return;
    }
    let at=Number(localStorage.getItem(manifestKey));
    if(!at){at=Date.now();localStorage.setItem(manifestKey,String(at));}
    const remaining=Math.max(0,6000-(Date.now()-at));
    const timer=window.setTimeout(()=>setEncoding(false),remaining);
    return()=>window.clearTimeout(timer);
  },[encoding,manifestKey,onTimedWindowChange,onCheckpoint,attempt.attempt_id,sessionId]);

  useEffect(()=>{
    if(encoding)return;
    let mounted=true;
    void getStreamCue(attempt.attempt_id)
      .then(v=>{if(mounted){setCue(v);if(v.complete)void finish();}})
      .catch(e=>{if(mounted)setError(e.message);});
    return()=>{mounted=false;};
  },[attempt.attempt_id,encoding]);

  async function dispatch(destination:string|null){
    if(!cue||busy)return;
    const saved=pendingDispatch??{destination,cue:cue.cue_id};
    if(saved.cue!==cue.cue_id||saved.destination!==destination){setError('Retry the exact saved dispatch before choosing another destination.');return;}
    setPendingDispatch(saved);setBusy(true);
    try{
      if(!acceptedDispatch.current){await act('respond',{arrival_index:cue.index,destination_id:saved.destination,ignore:saved.destination===null},saved.cue);acceptedDispatch.current=true;}
      const next=await getStreamCue(attempt.attempt_id);
      acceptedDispatch.current=false;setPendingDispatch(null);
      if(!next.complete&&next.wave!==cue.wave){setBetweenWave(true);emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:wave:${cue.wave}:complete`,sessionId,activityId:'HY-04',attemptId:attempt.attempt_id,kind:'checkpoint',text:'Harbor wave checkpoint saved. Take a moment before the next wave.'});}
      setCue(next);setError('');if(next.complete)await finish();
    }catch(e){setError(e instanceof Error?e.message:'Dispatch was not saved.');}
    finally{setBusy(false);}
  }

  async function requestWaveHint(){
    if(!cue)return;
    const key=`hy-help:${attempt.attempt_id}:wave-${cue.wave}`;
    let raw=localStorage.getItem(key);
    if(!raw){raw=JSON.stringify({event_id:hybridUid(),exposure_kind:'strategy_prompt',checkpoint:'between_waves'});localStorage.setItem(key,raw);}
    try{
      const request=JSON.parse(raw);await recordHybridAssistance(attempt.attempt_id,request);localStorage.removeItem(key);
      setHint('Use the manifest for familiar cargo, then check the current wave rule before routing.');
      emitCompanionCheckpoint(onCheckpoint,{id:request.event_id,sessionId,activityId:'HY-04',attemptId:attempt.attempt_id,kind:'assistance',text:'The recorded harbor routing strategy is available for this wave.'});
      setBetweenWave(false);
    }catch(e){setError(e instanceof Error?e.message:'Help was not saved; retry before revealing it.');}
  }

  if(encoding)return <><p>Remember this cargo manifest. It will hide before the arrivals.</p><ul className="harbor-manifest">{Object.entries(c.manifest).map(([cargo,dest]:any)=><li key={cargo}><img src={memoryLantern} alt=""/><span>{cargo.replace('cargo-','Cargo ')} → {dest.replace('-',' ')}</span></li>)}</ul><p>The first wave begins after the manifest.</p></>;
  if(cue?.complete)return <p>All waves completed.</p>;
  if(!cue)return <><p role={error?'alert':'status'}>{error||'Preparing the next harbor wave…'}</p>{error&&<button className="hy-primary" onClick={()=>void getStreamCue(attempt.attempt_id).then(v=>{setCue(v);setError('');}).catch(e=>setError(e.message))}>Retry loading next arrival</button>}</>;

  const destinations=cue.route_options??[];
  const ruleText=cue.rule==='marked'?'Follow the destination marked on each arrival.':'Use the cargo manifest to choose a destination.';
  const arrivalName=cue.distractor?'Unmarked decoy':routeLabel(cue.cargo_id??'Cargo');

  return <div className="dispatch-board">
    <div className="harbor-info-row">
      <div className="harbor-wave-sign" aria-label={`Current rule, wave ${cue.wave} of ${c.wave_count}, arrival ${cue.index+1} of ${c.wave_count*c.arrivals_per_wave}`}>
        <img src={harborPlaque} alt="" aria-hidden="true"/>
        <div><small>WAVE {cue.wave} OF {c.wave_count} · ARRIVAL {cue.index+1} OF {c.wave_count*c.arrivals_per_wave}</small><strong>{cue.rule==='marked'?'Marked destinations':'Cargo manifest'}</strong><span>{ruleText}</span></div>
      </div>
      <div className="harbor-arrival" aria-label={`Current arrival: ${arrivalName}${cue.marked_destination?`, marked for ${routeLabel(cue.marked_destination)}`:''}`}>
        <span className="harbor-arrival-art" aria-hidden="true"><img className="harbor-arrival-boat" src={harborBoatBlue} alt=""/>{!cue.distractor&&<img className="harbor-arrival-crate" src={harborCrate} alt=""/>}</span>
        <div><small>{cue.distractor?'UNMARKED ARRIVAL':`ARRIVAL ${cue.index+1}`}</small><h2>{arrivalName}</h2>{cue.marked_destination&&<p>Marked destination: <strong>{routeLabel(cue.marked_destination)}</strong></p>}</div>
      </div>
      {hint&&<aside className="harbor-recorded-hint" aria-label="Recorded strategy hint"><strong>Recorded strategy hint</strong><span>{hint}</span></aside>}
    </div>

    <section className="harbor-route-world" aria-label="Harbor destination lanes">
      <div className="harbor-route-map" aria-hidden="true">
        {destinations.map(dest=><div className="harbor-channel" key={dest}>
          <img className="harbor-channel-gate" src={harborGate} alt=""/>
          <span className="harbor-channel-name">{routeLabel(dest)}</span>
          <span className="harbor-channel-water"/>
        </div>)}
      </div>
      {betweenWave&&<section className="hy-tip harbor-wave-checkpoint"><p>A new wave has started. You can ask for a recorded routing strategy.</p><div className="harbor-checkpoint-actions"><button className="hy-ghost" onClick={()=>void requestWaveHint()}>Show strategy hint</button><button className="hy-ghost" onClick={()=>setBetweenWave(false)}>Continue without help</button></div></section>}
    </section>

    <section className="harbor-action-dock" aria-label="Dispatch controls">
      <p className="harbor-dock-heading">Route this arrival</p>
      {pendingDispatch&&!busy&&<button className="hy-primary harbor-retry" onClick={()=>void dispatch(pendingDispatch.destination)}>Retry exact saved dispatch</button>}
      <div className="harbor-destination-choices" role="group" aria-label="Choose a destination">
        {destinations.map(dest=><button type="button" className="harbor-destination-choice" key={dest} data-destination={dest} disabled={busy||betweenWave||Boolean(pendingDispatch)} onClick={()=>void dispatch(dest)} aria-label={`Route ${arrivalName} to ${routeLabel(dest)}`}>
          <img src={harborGate} alt="" aria-hidden="true"/><span><strong>{routeLabel(dest)}</strong><small>{cue.rule==='marked'?'Select marked destination':'Choose from manifest'}</small></span>
        </button>)}
      </div>
      <button className="harbor-ignore" disabled={busy||betweenWave||Boolean(pendingDispatch)} onClick={()=>void dispatch(null)} aria-label={`Ignore ${arrivalName}`}><img src={harborBuoy} alt="" aria-hidden="true"/><span><strong>Ignore decoy</strong><small>Use for unmarked arrivals</small></span></button>
    </section>
    {error&&<p className="hy-error harbor-error" role="alert">{error}</p>}{busy&&<p className="harbor-saving" role="status">Saving dispatch…</p>}
  </div>;
}
