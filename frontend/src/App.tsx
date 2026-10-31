import { useCallback, useEffect, useRef, useState } from 'react';
import { Database, Info, LoaderCircle, X } from 'lucide-react';
import TaskRenderer, { type Exercise } from './TaskComponents';
import Companion from './Companion';
import type { CompanionCheckpointSignal } from './companionCheckpoint';
import { MotionConfig } from 'motion/react';
import AdventureHome from './AdventureHome';
import { InsightsPage, type InsightDashboardSource } from './redesign/pages/InsightsPage';
import { PlanPage as RedesignedPlanPage, type PlanStep } from './redesign/pages/PlanPage';
import { parsePersistedPlanLaunch, type PersistedPlanLaunch, type PlanStepLaunchResponse } from './redesign/pages/planActivity';
import { PracticeCompletePage, PracticeEntryPage } from './redesign/pages/PracticePages';
import { EvidencePage, type EvidenceGraphQuery, type EvidenceRecordRef } from './redesign/pages/EvidencePage';
import { CollaborationPage as RedesignedCollaborationPage } from './redesign/pages/CollaborationPage';
import { PauseOverlay, PrivacyPage } from './redesign/pages/PrivacyAndPause';
import { DesktopNavigation, Header, MobileNavigation, type Page } from './navigation';
import { HybridPage } from './redesign/hybrid/HybridPage';
import './adventure.css';

type EventRow={event_id:string;session_id:string;type:string;created_at:string;payload:Record<string,any>};
type Profile={learner_id:string;dimensions:Record<string,any>;snapshots:any[];evidence?:any[];interpretation:string};
type DashboardDTO={learner_id:string;profile:Profile;events:EventRow[];plan:{latest:any;history:any[]};preferences?:{dashboard_mode:'analytics'|'rpg';goal_dimension:string|null};collaboration?:{score:{score_0_100:number|null;status:string;interpretation:string;dimensions:Record<string,{score_0_100:number|null;weight_percent:number;evaluated_opportunity_count:number;evidence:{evidence_ids:string[]}[]}>};opportunity_count:number;evaluated_opportunity_count:number;open_opportunity_count:number};milestones?:{id:string;title:string;description:string;achieved:boolean;progress_current:number;progress_target:number;evidence_ids:string[]}[];activity:{window_days:number;start_date:string;end_date:string;buckets:{date:string;count:number}[];total_valid_trials:number;interpretation?:string};participation:{practice_trial_count:number;training_trial_count:number;assisted_training_trial_count:number;xp:number;level:number;xp_into_level:number;xp_to_next_level:number;interpretation:string};task_coverage:{assessed_count:number;total_count:number;dimensions:{dimension:string;status:string;index_0_100:number|null;evidence_count:number;required_evidence_count:number;uncertainty_status:string|null;evidence_ids:string[]}[]}};
type Pending=Record<string,any>;
type AcceptedTrial={payload:Pending;exercise:Exercise;blockId:string|null;result:any};
const SESSION='ai4brain.session',BLOCK='ai4brain.trainingBlock',PENDING='ai4brain.pendingTrial',INTERRUPTION='ai4brain.pendingInterruption',FAMILY='ai4brain.family';
const PLAN_LAUNCH='ai4brain.planV3Launch';
function clearOriginalActivityRecovery() {
 for (const storage of [localStorage, sessionStorage]) {
  for (const key of Object.keys(storage)) {
   if (key.startsWith('hy-') || key.startsWith('crystal-') || key.startsWith('ai4brain.hy')) storage.removeItem(key);
  }
 }
}
const families=['EX-01','EX-02','EX-03','EX-04','EX-05'];
const dimensions:Record<string,string>={'EX-01':'working_memory','EX-02':'reasoning','EX-03':'attention_inhibition','EX-04':'flexibility','EX-05':'planning'};
const dimensionNames:Record<string,string>={working_memory:'Memory',reasoning:'Reasoning',attention_inhibition:'Attention & inhibition',flexibility:'Flexibility',planning:'Planning'};
const validStartedAt=(value:any):string|null=>typeof value==='string'&&Number.isFinite(Date.parse(value))?value:null;
async function request<T>(url:string,init?:RequestInit):Promise<T>{
 const r=await fetch(url,{...init,headers:{'Content-Type':'application/json',...init?.headers}});
 if(!r.ok){
  let m=`Request failed (${r.status})`;
  try{
   const detail=(await r.json()).detail;
   // FastAPI validation errors arrive as a list of objects; never surface "[object Object]".
   if(typeof detail==='string')m=detail;
   else if(Array.isArray(detail))m=detail.map((entry:any)=>entry?.msg??entry?.message??JSON.stringify(entry)).join('; ');
   else if(detail)m=JSON.stringify(detail);
  }catch{}
  throw new Error(m);
 }
 return r.json() as Promise<T>;
}
const json=(x:any)=>JSON.stringify(x), good=(e:EventRow)=>!e.payload.interaction?.visibility_interrupted&&!e.payload.interaction?.hint_count;
const consumedTrial=(e:EventRow)=>!e.payload.interaction?.visibility_interrupted&&!e.payload.visibility_interrupted;
const phaseEvents=(events:EventRow[],ex:string,phase:string)=>events.filter(e=>e.payload.exercise_id===ex&&e.payload.phase===phase&&good(e));
const trainingResumeIndex=(block:any,sessionId:string,events:EventRow[])=>{
 if(block?.block?.session_id!==sessionId)throw new Error('The saved training block is linked to a different session.');
 if(block.block?.status==='completed'||block.difficulty_decision)return {finished:true,index:-1};
 const consumed=new Set(events.filter(event=>event.payload.training_block_id===block.block.block_id&&event.payload.phase==='training'&&consumedTrial(event)).map(event=>event.payload.item_id));
 const index=(block.exercise?.items??[]).findIndex((item:any)=>!consumed.has(item.item_id));
 return {finished:index<0,index};
};
function Practice({sessionStartedAt,exercise,itemIndex,selected,setSelected,responseData,pending,submitting,decision,recommendation,planStep,resetKey,exhausted,blockLoading,onStart,onSubmit,onStimulusOnset,onReset,onRetryDecision,onPlan,onBrain,journeyProgress,onPause,paused,onCueActivity}:{sessionStartedAt:string|null;exercise:Exercise|null;itemIndex:number;selected:string|null;setSelected:(v:string|null)=>void;responseData:any;pending:boolean;submitting:boolean;decision:any;recommendation:any;planStep:any;resetKey:number;exhausted:boolean;blockLoading:boolean;onStart:()=>void;onSubmit:(d?:any,c?:string,t?:number|null,onset?:number|null)=>void;onStimulusOnset:(onset:number|null)=>void;onReset:()=>void;onRetryDecision:()=>void;onPlan:()=>void;onBrain:()=>void;journeyProgress:{familyIndex:number;familyCount:number;completedFamilies?:number};onPause:(draft?:Record<string,any>)=>void;paused:boolean;onCueActivity:(active:boolean)=>void}){
 // A leftover assessment exercise must not decide the practice entry's world; the
 // entry follows the recommendation, while completion follows the actual block.
 const recommendedDimension=recommendation?.dimension??dimensions[recommendation?.exercise_id]??null;
 const entryDimension=recommendedDimension??(exercise?dimensions[exercise.exercise_id]:null)??'reasoning';
 const trainingDimension=exercise?dimensions[exercise.exercise_id]??entryDimension:entryDimension;
 if(!exercise||exercise.phase!=='training')return <PracticeEntryPage dimension={entryDimension} tier={recommendation?.tier??null} timeMinutes={planStep?.estimated_time_minutes??null} strategy={recommendation?.selected_strategy_id?{id:recommendation.selected_strategy_id}:null} rationale={recommendation?.rationale??null} evidenceCount={Array.isArray(recommendation?.evidence_ids)?recommendation.evidence_ids.length:null} policyVersion={recommendation?.policy_version??null} loading={blockLoading} onEnter={onStart} onPlan={onPlan}/>;
 if(decision)return <PracticeCompletePage dimension={trainingDimension} decision={decision} loading={blockLoading} onReturnInsights={onReset} onInspectEvidence={onBrain}/>;
 if(exhausted)return <PracticeCompletePage dimension={trainingDimension} decision={null} loading={blockLoading} onReturnInsights={onReset} onRetryDecision={onRetryDecision}/>;
 const item=exercise.items[itemIndex];
  return item?<main className="adventure-game-stage"><TaskRenderer exercise={exercise} item={item} index={itemIndex} selected={selected} setSelected={setSelected} savedResponse={responseData} submitting={submitting} pending={pending} onSubmit={onSubmit} onStimulusOnset={onStimulusOnset} resetKey={resetKey} sessionStartedAt={sessionStartedAt} journeyProgress={journeyProgress} onPause={onPause} paused={paused} onCueActivity={onCueActivity}/></main>:null;
}

function DataManager({onClose,onDeleted}:{onClose:()=>void;onDeleted:()=>void}){
 const [notice,setNotice]=useState<any>(null),[loading,setLoading]=useState(true),[error,setError]=useState<string|null>(null),[exporting,setExporting]=useState(false),[deleting,setDeleting]=useState(false),[deleteResult,setDeleteResult]=useState<any>(null),[reconciling,setReconciling]=useState(false);
 useEffect(()=>{let live=true;request<any>('/api/data/demo-user/notice').then(x=>{if(live)setNotice(x)}).catch(e=>{if(live)setError(e instanceof Error?e.message:'Could not load the data notice.')}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[]);
 const exportData=async()=>{setExporting(true);setError(null);try{const r=await fetch('/api/data/demo-user/export');if(!r.ok)throw new Error(`Export failed (${r.status}).`);const blob=await r.blob(),disposition=r.headers.get('content-disposition')??'',name=disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i)?.[1]??'ai4brain-data-export.json',url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=decodeURIComponent(name.replace(/"/g,''));document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);}catch(e){setError(e instanceof Error?e.message:'Could not export local data.');}finally{setExporting(false)}};
 const deleteData=async()=>{setDeleting(true);setError(null);try{const r=await request<any>('/api/data/demo-user/delete',{method:'POST',body:json({confirmation:'DELETE LOCAL DATA'})});setDeleteResult(r);onDeleted();}catch(e){setError(e instanceof Error?e.message:'Could not delete local data.');}finally{setDeleting(false)}};
 const reconcile=async()=>{setReconciling(true);setError(null);try{const r=await request<any>('/api/data/demo-user/reconcile',{method:'POST'});setDeleteResult((old:any)=>old?{...old,mirror:r}:old);setNotice((old:any)=>({...old,mirror_reconciliation:r}));}catch(e){setError(e instanceof Error?e.message:'Graph mirror reconciliation failed.');}finally{setReconciling(false)}};
 return <PrivacyPage notice={notice} loading={loading} error={error} exporting={exporting} deleting={deleting} reconciling={reconciling} deleteResult={deleteResult} onClose={onClose} onExport={()=>void exportData()} onDelete={()=>void deleteData()} onReconcile={()=>void reconcile()}/>;
}

function CollaborationPageContainer({sessionId,onChanged}:{sessionId:string|null;onChanged:()=>void}){
 const [data,setData]=useState<any>(null),[loading,setLoading]=useState(false),[error,setError]=useState<string|null>(null);
 const load=useCallback(async()=>{if(!sessionId){setData(null);return;}setLoading(true);setError(null);try{const [legacy,v2Score]=await Promise.all([request<any>(`/api/collaboration/demo-user?session_id=${encodeURIComponent(sessionId)}`),request<any>(`/api/collaboration/v2/score/demo-user?session_id=${encodeURIComponent(sessionId)}`)]);setData({...legacy,v2Score});}catch(e){setError(e instanceof Error?e.message:'Could not load collaboration opportunities.');}finally{setLoading(false);}},[sessionId]);
 useEffect(()=>{void load()},[load]);
 const inspect=async(op:any,eventId:string)=>{
  if(!sessionId)return {inspected:false as const,reason:'Start a local session before inspecting evidence.'};
  const offered=(op.inspectable_evidence_ids??[]).includes(eventId);
  if(!offered)return {inspected:false as const,reason:'This record was not cited for verification in this opportunity.'};
  const result=await request<any>('/api/collaboration/inspect',{method:'POST',body:json({session_id:sessionId,opportunity_id:op.opportunity_id,event_id:eventId})});
  if(!result?.inspection?.event_id)return {inspected:false as const,reason:'The inspection was not recorded.'};
  // Carry the cited record so the inspector shows what was actually verified. The
  // public event nests its data under `payload`, so flatten it for the inspector.
  const cited=result.source_event??null;
  const record=cited?{...cited,...(cited.payload??{})}:null;
  return {inspected:true as const,eventId,record,inspectionEventId:result.inspection.event_id};
 };
  const prepareV2=useCallback(async(op:any)=>{
   if(!sessionId)return null;
   await request<any>('/api/collaboration/v2/prepare',{method:'POST',body:json({session_id:sessionId,source_event_id:op.source_event_id})});
   const claim=await request<any>(`/api/collaboration/v2/claim?opportunity_id=${encodeURIComponent(op.opportunity_id)}&session_id=${encodeURIComponent(sessionId)}`);
   if(typeof claim?.claim_text!=='string'||typeof claim?.about_evidence_id!=='string')return null;
   return {claimText:claim.claim_text,evidenceEventId:claim.about_evidence_id,context:claim.context??null};
  },[sessionId]);
  const v2Act=useCallback(async(op:any,evidence:{verdict:'supported'|'contradicted'|'insufficient_evidence';inspected_event_id:string})=>{
   if(!sessionId)throw new Error('Start a local session before recording structured collaboration evidence.');
   await request<any>('/api/collaboration/v2/actions',{method:'POST',body:json({session_id:sessionId,opportunity_id:op.opportunity_id,evidence})});
   await load();
   onChanged();
  },[load,onChanged,sessionId]);
  const act=async(op:any,body:Record<string,any>)=>{
  await request<any>('/api/collaboration/actions',{method:'POST',body:json({session_id:sessionId,opportunity_id:op.opportunity_id,...body})});
  await load();
  onChanged();
 };
 return <RedesignedCollaborationPage collaboration={data} loading={loading} error={error} onRefresh={()=>void load()} onInspect={inspect} onAction={act} onPrepareV2={prepareV2} onV2Action={v2Act}/>;
}

export default function App(){
 const [page,setPage]=useState<Page>('welcome'),[sessionId,setSessionId]=useState<string|null>(null),[sessionStartedAt,setSessionStartedAt]=useState<string|null>(null),[mode,setMode]=useState<'analytics'|'quest'>('analytics'),[consent,setConsent]=useState(false),[exercise,setExercise]=useState<Exercise|null>(null),[itemIndex,setItemIndex]=useState(0),[selected,setSelected]=useState<string|null>(null),[taskResponse,setTaskResponse]=useState<any>(null),[dashboard,setDashboard]=useState<DashboardDTO|null>(null),[dashboardLoading,setDashboardLoading]=useState(false),[dashboardError,setDashboardError]=useState<string|null>(null),[loading,setLoading]=useState(false),[submitting,setSubmitting]=useState(false),[error,setError]=useState<string|null>(null),[pending,setPending]=useState<Pending|null>(null),[acceptedTrial,setAcceptedTrial]=useState<AcceptedTrial|null>(null),[pendingInterruption,setPendingInterruption]=useState<Pending|null>(()=>{try{return JSON.parse(localStorage.getItem(INTERRUPTION)??'null')}catch{return null}}),[acceptedInterruption,setAcceptedInterruption]=useState<Pending|null>(null),[transitionLocked,setTransitionLocked]=useState(false),[blockExhausted,setBlockExhausted]=useState(false),[decision,setDecision]=useState<any>(null),[blockId,setBlockId]=useState<string|null>(null),[resetKey,setResetKey]=useState(0),[dataInfo,setDataInfo]=useState(false),[dataResetKey,setDataResetKey]=useState(0),[graph,setGraph]=useState<any>(null),[graphLoading,setGraphLoading]=useState(false),[graphError,setGraphError]=useState<string|null>(null),[graphDimension,setGraphDimension]=useState('reasoning'),[planData,setPlanData]=useState<any>(null),[recommendation,setRecommendation]=useState<any>(null),[planLoading,setPlanLoading]=useState(false),[planError,setPlanError]=useState<string|null>(null),[sampleScenarios,setSampleScenarios]=useState<any>(null),[goalSaved,setGoalSaved]=useState(false),[budgetMinutes,setBudgetMinutes]=useState(15),[goalDimension,setGoalDimension]=useState('');
  const [pauseOpen,setPauseOpen]=useState(false),[pauseDraft,setPauseDraft]=useState<Record<string,any>|null>(null);
  const [homeNotice,setHomeNotice]=useState<string|null>(null);
  const [hybridActivityActive,setHybridActivityActive]=useState(false);
  const [hybridTimedWindow,setHybridTimedWindow]=useState(false);
  const [companionCheckpoint,setCompanionCheckpoint]=useState<CompanionCheckpointSignal|null>(null);
  const [planLaunch,setPlanLaunch]=useState<PersistedPlanLaunch|null>(()=>parsePersistedPlanLaunch(localStorage.getItem(PLAN_LAUNCH)));
  const [launchingPlanStep,setLaunchingPlanStep]=useState<string|null>(null);
  useEffect(()=>{window.scrollTo({top:0,left:0,behavior:'instant'});},[page]);
  const pauseInterruptedRef=useRef(false),attentionCueActive=useRef(false);
  useEffect(()=>{if(!pauseOpen)return;const prior=document.activeElement as HTMLElement|null;const focusFrame=requestAnimationFrame(()=>document.querySelector<HTMLElement>('.adventure-pause-dialog button:not(:disabled)')?.focus());const keydown=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();if(!transitionLocked&&!submitting){setPauseOpen(false);setPauseDraft(null);pauseInterruptedRef.current=false;}return;}if(event.key==='Tab'){const buttons=Array.from(document.querySelectorAll<HTMLElement>('.adventure-pause-dialog button:not(:disabled)'));if(!buttons.length)return;const first=buttons[0],last=buttons[buttons.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}};document.addEventListener('keydown',keydown);return()=>{cancelAnimationFrame(focusFrame);document.removeEventListener('keydown',keydown);prior?.focus();};},[pauseOpen,transitionLocked,submitting]);
  useEffect(()=>{
    // While a modal is open, the page behind it must not be reachable by keyboard or AT.
    const targets=Array.from(document.querySelectorAll<HTMLElement>('.adventure-header, .adventure-layout, .adventure-mobile-nav, .app-footer, .companion-dock, .companion-restore'));
    const modalOpen=dataInfo||pauseOpen;
    targets.forEach(target=>{if(modalOpen){target.setAttribute('inert','');target.setAttribute('aria-hidden','true');}else{target.removeAttribute('inert');target.removeAttribute('aria-hidden');}});
    return ()=>{targets.forEach(target=>{target.removeAttribute('inert');target.removeAttribute('aria-hidden');});};
  },[dataInfo,pauseOpen]);
  const active=exercise?.items[itemIndex],closeData=useCallback(()=>setDataInfo(false),[]);const lock=useRef(false),interruptionSignal=useRef(false),interruptionAccepted=useRef(false),pauseExitAfterSubmit=useRef(false),sessionRef=useRef<string|null>(null),preferredFamily=useRef<string|null>(null),pageRef=useRef<Page>('welcome'),exerciseRef=useRef<Exercise|null>(null),indexRef=useRef(0),onset=useRef(performance.now()),attentionCueOnset=useRef<number|null>(null);useEffect(()=>{sessionRef.current=sessionId},[sessionId]);useEffect(()=>{pageRef.current=page},[page]);useEffect(()=>{exerciseRef.current=exercise},[exercise]);useEffect(()=>{indexRef.current=itemIndex},[itemIndex]);useEffect(()=>{onset.current=performance.now()},[page,exercise?.exercise_id,exercise?.phase,exercise?.items[itemIndex]?.item_id,resetKey]);
 const modePreferenceRevision=useRef(0),modeWritePending=useRef(false),modeWriteQueue=useRef<Promise<void>>(Promise.resolve()),savedModeRef=useRef<'analytics'|'quest'|null>(null),graphRequest=useRef(0),graphRecordRequest=useRef(0),graphQueryRef=useRef<EvidenceGraphQuery>({scope:'global',limit:5000,offset:0}),graphRevisionRef=useRef<string|null>(null),recommendationFallback=useRef(false),navGeneration=useRef(0);
 const receiveHybridCheckpoint=useCallback((signal:CompanionCheckpointSignal)=>{if(signal.sessionId!==sessionRef.current)return;setCompanionCheckpoint(signal);},[]);
 useEffect(()=>{
  if(page==='practice'&&decision&&blockId)setCompanionCheckpoint({id:`training-decision:${blockId}:${decision.event_id??decision.new_tier??'saved'}`,sessionId:sessionId??'',activityId:decision.exercise_id??exercise?.exercise_id??'core',attemptId:blockId,kind:'completed',text:'This training block is complete. You can review the saved decision or choose another step.'});
 },[page,decision,blockId,sessionId,exercise?.exercise_id]);
 const refreshDashboard=useCallback(async()=>{const readRevision=modePreferenceRevision.current;setDashboardLoading(true);setDashboardError(null);try{const dto=await request<DashboardDTO>('/api/dashboard/demo-user');if(!dto||!dto.task_coverage||!dto.activity||!dto.participation)throw new Error('Dashboard summary is incomplete.');setDashboard(previous=>{const preferenceWriteOverlaps=readRevision!==modePreferenceRevision.current||modeWritePending.current;const latestSavedMode=preferenceWriteOverlaps?(savedModeRef.current??previous?.preferences?.dashboard_mode??dto.preferences?.dashboard_mode):dto.preferences?.dashboard_mode;const normalizedMode=latestSavedMode?(latestSavedMode==='quest'||latestSavedMode==='rpg'?'rpg' as const:'analytics' as const):null;const goalDimension=preferenceWriteOverlaps?(previous?.preferences?.goal_dimension??dto.preferences?.goal_dimension??null):dto.preferences?dto.preferences.goal_dimension:previous?.preferences?.goal_dimension??null;const preferences=normalizedMode?{dashboard_mode:normalizedMode,goal_dimension:goalDimension}:dto.preferences??previous?.preferences;return {...dto,...(preferences?{preferences}:{})};});return dto;}catch(e){setDashboardError(e instanceof Error?e.message:'Dashboard summary is unavailable.');return null;}finally{setDashboardLoading(false);}},[]);
 const refreshSession=useCallback(async(id:string)=>{const r=await request<any>(`/api/sessions/${id}`);const rows=(r.events??[]) as EventRow[];if(pageRef.current==='overview')void refreshDashboard();return rows;},[refreshDashboard]);
 const getConfig=useCallback((id:string,ex:string,phase:string)=>{const suffix=ex==='EX-02'?'':`&session_id=${encodeURIComponent(id)}`;return request<Exercise>(`/api/exercises/${ex}?phase=${phase}${suffix}`);},[]);
 const advanceFamily=useCallback(async(id:string,rows:EventRow[],ex:string)=>{const [pr,base]=await Promise.all([getConfig(id,ex,'practice'),getConfig(id,ex,'baseline')]);const donePractice=new Set(phaseEvents(rows,ex,'practice').map(e=>e.payload.item_id));if(donePractice.size<pr.items.length){setExercise(pr);setItemIndex(Math.max(0,pr.items.findIndex(i=>!donePractice.has(i.item_id))));setSelected(null);setTaskResponse(null);return true;}const doneBase=new Set(phaseEvents(rows,ex,'baseline').map(e=>e.payload.item_id));if(doneBase.size<base.items.length){setExercise(base);setItemIndex(Math.max(0,base.items.findIndex(i=>!doneBase.has(i.item_id))));setSelected(null);setTaskResponse(null);return true;}return false;},[getConfig]);
 const advance=useCallback(async(id:string,rows:EventRow[])=>{for(const ex of families){if(await advanceFamily(id,rows,ex))return true;}setExercise(null);return false;},[advanceFamily]);
 const clearPendingTrial=useCallback(()=>{
   localStorage.removeItem(PENDING);
   setPending(null);
   setAcceptedTrial(null);
  },[]);
  const reconcileAcceptedTrial=useCallback(async(accepted:AcceptedTrial)=>{
   const {payload,exercise:submittedExercise,blockId:submittedBlockId,result}=accepted;
   const rows=await refreshSession(payload.session_id);
   setSelected(null);
   setTaskResponse(null);
   if(submittedExercise.phase==='training'){
    const consumed=new Set(rows.filter(e=>e.payload.training_block_id===submittedBlockId&&e.payload.phase==='training'&&consumedTrial(e)).map(e=>e.payload.item_id));
    if(result.difficulty_decision){
     setDecision(result.difficulty_decision);
     setBlockExhausted(false);
     setItemIndex(3);
     // The block is finished; a stale saved id would request a training config that
     // no longer has a valid block on the next load.
     localStorage.removeItem(BLOCK);
    }else{
     const next=submittedExercise.items.findIndex(item=>!consumed.has(item.item_id));
     if(next>=0){setItemIndex(next);setBlockExhausted(false);}
     else{
      const block=await request<any>(`/api/training/blocks/${submittedBlockId}`);
      if(block.difficulty_decision){setDecision(block.difficulty_decision);setBlockExhausted(false);}
      else setBlockExhausted(true);
      setItemIndex(3);
     }
    }
   }else if(submittedExercise.phase==='reassessment'){
    const completed=new Set(rows.filter(e=>e.payload.phase==='reassessment'&&e.payload.exercise_id===submittedExercise.exercise_id&&consumedTrial(e)).map(e=>e.payload.item_id));
    if(completed.size<submittedExercise.items.length){
     const config=await getConfig(payload.session_id,submittedExercise.exercise_id,'reassessment');
     setExercise(config);
     setItemIndex(Math.max(0,config.items.findIndex(item=>!completed.has(item.item_id))));
     setPage('assessment');
    }else setPage('overview');
   }else if(!await advanceFamily(payload.session_id,rows,submittedExercise.exercise_id)){
    // The explicitly chosen family is finished; do not silently move the learner
    // into a different family's assessment. Only an explicit journey continues.
    preferredFamily.current=null;
    localStorage.removeItem(FAMILY);
    setExercise(null);
    setPage('overview');
   }
   clearPendingTrial();
  },[refreshSession,getConfig,advanceFamily,clearPendingTrial]);
   const restore=useCallback(async(id:string,keepHome=false)=>{
   // A learner navigation during a slow restore wins: only write the page if none happened.
   const navToken=navGeneration.current;const settlePage=(next:Page)=>{if(navGeneration.current===navToken)setPage(next);};
   setLoading(true);
   setError(null);
   try{
     const session=await request<any>(`/api/sessions/${id}`);
     setSessionStartedAt(validStartedAt(session.started_at));
    let rows=(session.events??[]) as EventRow[];
    setSessionId(id);
    sessionRef.current=id;
    setMode(session.dashboard_mode==='rpg'?'quest':'analytics');

    const interruptionRaw=localStorage.getItem(INTERRUPTION);
    if(interruptionRaw){
     let interruption:Pending|null=null;
     try{interruption=JSON.parse(interruptionRaw);}catch{localStorage.removeItem(INTERRUPTION);}
     if(interruption?.session_id===id){
      setPendingInterruption(interruption);
      setTransitionLocked(true);
      interruptionSignal.current=true;
      const recorded=rows.some(event=>event.event_id===interruption.event_id);
      if(!recorded)await request('/api/trials',{method:'POST',body:json(interruption)});
      setAcceptedInterruption(interruption);
      setSelected(null);
      setTaskResponse(null);
      setResetKey(value=>value+1);
      rows=await refreshSession(id);
      localStorage.removeItem(INTERRUPTION);
      setPendingInterruption(null);
      setAcceptedInterruption(null);
      setTransitionLocked(false);
      interruptionAccepted.current=false;
      interruptionSignal.current=false;
     }
    }

    let saved:Pending|null=null,acceptedSaved:Pending|null=null;
    const raw=localStorage.getItem(PENDING);
    if(raw){
     try{
      const value=JSON.parse(raw);
      if(value.session_id===id){
       if(rows.some(event=>event.event_id===value.event_id))acceptedSaved=value;
       else saved=value;
      }else localStorage.removeItem(PENDING);
     }catch{localStorage.removeItem(PENDING);}
    }
    if(saved){setPending(saved);setSelected(saved.choice??saved.response_data?.choice??null);setTaskResponse(saved.response_data??null);}
    if(acceptedSaved)setPending(acceptedSaved);

    const savedBlockId=localStorage.getItem(BLOCK);
    if(savedBlockId){
     const block=await request<any>(`/api/training/blocks/${savedBlockId}`);
     if(block.block.session_id!==id)throw new Error('The saved training block is linked to a different session.');
     setBlockId(savedBlockId);
     setExercise(block.exercise);
     setDecision(block.difficulty_decision??null);
     const consumed=new Set(rows.filter(event=>event.payload.training_block_id===savedBlockId&&event.payload.phase==='training'&&consumedTrial(event)).map(event=>event.payload.item_id));
     const next=block.exercise.items.findIndex((item:any)=>!consumed.has(item.item_id));
     setBlockExhausted(next<0&&!block.difficulty_decision);
     setItemIndex(next<0?Math.max(0,block.exercise.items.length-1):next);
      settlePage(keepHome?'welcome':'practice');
     if(acceptedSaved)clearPendingTrial();
     return;
    }

    // An explicit world choice survives a reload: restore it before falling back to
    // the canonical recommendation, and drop it once that family has nothing left.
    let chosen=preferredFamily.current;
    if(!chosen){
     const storedFamily=localStorage.getItem(FAMILY);
     if(storedFamily&&families.includes(storedFamily))chosen=storedFamily;
    }
    let active=chosen?await advanceFamily(id,rows,chosen):false;
    if(!active&&chosen){preferredFamily.current=null;localStorage.removeItem(FAMILY);}
    if(!active)active=await advance(id,rows);
    if(active){
     let trainingRestore=false;
     if(saved){
      // A pending training trial needs its block: the training config is block-seeded
      // and rejects a request without a block id, so build it from the saved block.
      const block=saved.phase==='training'&&saved.training_block_id?await request<any>(`/api/training/blocks/${saved.training_block_id}`):null;
      const config=block?block.exercise as any:await getConfig(id,saved.exercise_id,saved.phase);
      setExercise(config);
      const index=config.items.findIndex((item:any)=>item.item_id===saved.item_id);
      if(index>=0)setItemIndex(index);
      setSelected(saved.choice??saved.response_data?.choice??null);
      setTaskResponse(saved.response_data??null);
      if(block){trainingRestore=true;setBlockId(saved.training_block_id!);setDecision(block.difficulty_decision??null);setBlockExhausted(false);}
     }
      // A pending training response belongs to the practice stage, where its retry is surfaced.
      settlePage(trainingRestore&&!keepHome?'practice':keepHome?'welcome':'assessment');
     }else settlePage(keepHome?'welcome':'overview');
    if(acceptedSaved)clearPendingTrial();
   }catch(e){
    const message=e instanceof Error?e.message:'';
    // A saved id that no longer exists cannot succeed on retry. Clear the stale local
    // pointers and offer a fresh session instead of a dead Retry loop.
    if(/session not found/i.test(message)){
     localStorage.removeItem(SESSION);
     localStorage.removeItem(BLOCK);
     localStorage.removeItem(PENDING);
     localStorage.removeItem(INTERRUPTION);
     sessionRef.current=null;
     setSessionId(null);
     setSessionStartedAt(null);
     setDashboard(null);
     setDashboardError(null);
     setPlanData(null);
     setRecommendation(null);
     setError(null);
     setHomeNotice('Your saved session is no longer on this device. Accept the notice below to start a new local session.');
     settlePage('welcome');
     return;
    }
    setSessionId(id);
    sessionRef.current=id;
    setError(message||'Could not restore the local session. Retry from the saved session.');
     settlePage(keepHome?'welcome':'overview');
   }finally{setLoading(false);}
  },[advance,advanceFamily,getConfig,refreshSession,clearPendingTrial]);
   const openPlanLaunch=useCallback(async(saved:PersistedPlanLaunch,response:PlanStepLaunchResponse,navToken=navGeneration.current)=>{
    const active={...saved,response};
    localStorage.setItem(PLAN_LAUNCH,json(active));
    setPlanLaunch(active);
    setError(null);
    // Persist the server-owned attempt even if the learner navigated elsewhere
    // while the launch request was in flight; never steal that navigation.
    if(navGeneration.current!==navToken)return;
    if(response.destination.kind==='hybrid'||response.destination.kind==='crystal'){
     setPage('hybrid');
     return;
    }
    if(response.destination.kind==='core'){
     const block=await request<any>(`/api/training/blocks/${encodeURIComponent(response.attempt_ref.id)}`);
     if(navGeneration.current!==navToken)return;
     setBlockId(response.attempt_ref.id);localStorage.setItem(BLOCK,response.attempt_ref.id);
     setExercise(block.exercise);setDecision(block.difficulty_decision??null);setBlockExhausted(false);setItemIndex(0);setSelected(null);setTaskResponse(null);setPage('practice');
    }
   },[]);
   const launchPlanStep=useCallback(async(step:PlanStep)=>{
    if(!sessionId){setPlanError('Start a consented local session before launching a planned activity.');return;}
    const latest=planData?.latest?.plan??planData?.latest??planData?.plan??planData;
    const planId=latest?.plan_id;
    const stepId=step.step_id;
    const navToken=navGeneration.current;
    const ref=step.activity_ref;
    if(!planId||!stepId||!ref){setPlanError('This saved plan step has no typed activity reference. Update the plan before launching it.');return;}
    if(ref.kind==='core'&&step.mode!=='training'&&step.action!=='targeted_training'){
     setPlanLoading(true);setPlanError(null);
     try{const cfg=await getConfig(sessionId,ref.id,step.mode==='baseline'?'baseline':'practice');if(navGeneration.current!==navToken)return;setExercise(cfg);setItemIndex(0);setSelected(null);setTaskResponse(null);setPage('assessment');}
     catch(e){setPlanError(e instanceof Error?e.message:'Could not open the canonical core assessment.');}
     finally{setPlanLoading(false);}
     return;
    }
    setLaunchingPlanStep(stepId);setPlanError(null);
    let saved=parsePersistedPlanLaunch(localStorage.getItem(PLAN_LAUNCH));
    if(!saved||saved.plan_id!==planId||saved.step_id!==stepId||saved.request_body.session_id!==sessionId){
     const requestId=globalThis.crypto?.randomUUID?.();
     if(!requestId){setPlanError('This browser cannot create the request ID needed for a safe plan launch.');setLaunchingPlanStep(null);return;}
     const savedTier=step.launch_tier??step.difficulty_tier;
     saved={plan_id:planId,step_id:stepId,activity_ref:ref,request_body:{request_id:requestId,session_id:sessionId,...(step.mode?{mode:step.mode}:{}),...(savedTier?{difficulty_tier:savedTier}:{})}};
    }
    if(!saved){setPlanError('The exact plan launch could not be prepared.');setLaunchingPlanStep(null);return;}
    const launch=saved;
    localStorage.setItem(PLAN_LAUNCH,json(launch));
    try{
     const response=await request<PlanStepLaunchResponse>(`/api/plans/${encodeURIComponent(planId)}/steps/${encodeURIComponent(stepId)}/launch`,{method:'POST',body:json(launch.request_body)});
     await openPlanLaunch(launch,response,navToken);
    }catch(e){setPlanError(e instanceof Error?e.message:'Plan launch is unavailable. The exact launch request is saved for retry.');}
    finally{setLaunchingPlanStep(null);}
   },[getConfig,openPlanLaunch,planData,sessionId]);
   useEffect(()=>{
    const id=localStorage.getItem(SESSION);
    if(!id)return;
    const saved=parsePersistedPlanLaunch(localStorage.getItem(PLAN_LAUNCH));
    const explicitPlanRoute=window.location.pathname==='/plan';
    const navToken=navGeneration.current;
    void(async()=>{
     await restore(id,true);
     if(navGeneration.current!==navToken||!saved||explicitPlanRoute||saved.request_body.session_id!==id)return;
     try{
      const response=await request<PlanStepLaunchResponse>(`/api/plans/${encodeURIComponent(saved.plan_id)}/steps/${encodeURIComponent(saved.step_id)}/launch`,{method:'POST',body:json(saved.request_body)});
      await openPlanLaunch(saved,response,navToken);
     }catch(e){setPlanError(e instanceof Error?e.message:'Saved plan launch could not be reconciled. Return to the plan and retry the exact launch.');if(navGeneration.current===navToken)setPage('plan');}
    })();
   },[openPlanLaunch,restore]);
 const start=async()=>{if(!consent)return;const navToken=navGeneration.current;setLoading(true);setError(null);setHomeNotice(null);try{const s=await request<any>('/api/sessions',{method:'POST',body:json({learner_id:'demo-user',consent_accepted:true,dashboard_mode:mode==='quest'?'rpg':'analytics'})});setSessionId(s.id);setSessionStartedAt(validStartedAt(s.started_at));sessionRef.current=s.id;localStorage.setItem(SESSION,s.id);const active=await advance(s.id,[]);if(navGeneration.current===navToken)setPage(active?'assessment':'overview');}catch(e){setError(e instanceof Error?e.message:'Could not start your session.');}finally{setLoading(false);}};
 const changeMode=async(v:'analytics'|'quest')=>{
  setMode(v);
  const revision=++modePreferenceRevision.current;
  if(!sessionId){modeWritePending.current=false;return;}
  modeWritePending.current=true;
  const dashboardMode=v==='quest'?'rpg':'analytics';
  const write=modeWriteQueue.current.catch(()=>undefined).then(async()=>{
   if(revision!==modePreferenceRevision.current)return;
   try{
    await request('/api/preferences',{method:'POST',body:json({session_id:sessionId,dashboard_mode:dashboardMode})});
    if(revision!==modePreferenceRevision.current)return;
    modeWritePending.current=false;
    savedModeRef.current=v;
    setDashboard(previous=>previous?{...previous,preferences:{...(previous.preferences??{goal_dimension:null}),dashboard_mode:dashboardMode}}:previous);
    if(!dashboard)void refreshDashboard();
   }catch(e){if(revision===modePreferenceRevision.current){modeWritePending.current=false;setError(e instanceof Error?e.message:'Could not save presentation preference.');}}
  });
  modeWriteQueue.current=write;
  await write;
 };
 const submit=useCallback(async(data?:any,choice?:string,responseTime?:number|null,stimulusOnset?:number|null)=>{
   const submittedExercise=exerciseRef.current,id=sessionRef.current,item=submittedExercise?.items[indexRef.current];
   if(lock.current||acceptedTrial||transitionLocked||!submittedExercise||!id||!item)return;
   if(!pending&&!data&&!choice)return;
   lock.current=true;
   setSubmitting(true);
   setError(null);
   let payload=pending;
   let acknowledged:AcceptedTrial|null=null;
   if(!payload){
     // Assistance markers travel beside response_data, never inside the evaluated payload.
     const replayCount=data&&typeof (data as any).replay_count==='number'?(data as any).replay_count:0;
     const responseData=data?Object.fromEntries(Object.entries(data).filter(([key])=>key!=='replay_count')):undefined;
     payload={event_id:crypto.randomUUID(),session_id:id,phase:submittedExercise.phase,exercise_id:submittedExercise.exercise_id,exercise_version:submittedExercise.exercise_version,item_id:item.item_id,...(submittedExercise.exercise_id==='EX-02'&&choice?{choice}:{}),...(responseData&&Object.keys(responseData).length?{response_data:responseData}:{}),...(replayCount?{replay_count:replayCount}:{}),response_time_ms:responseTime!==undefined?responseTime:Math.max(0,performance.now()-onset.current),stimulus_onset_ms:stimulusOnset!==undefined?stimulusOnset:onset.current,...(submittedExercise.phase==='training'?{training_block_id:blockId}: {})};
    setPending(payload);
    localStorage.setItem(PENDING,json(payload));
   }
   try{
    const result=await request<any>('/api/trials',{method:'POST',body:json(payload)});
    acknowledged={payload,exercise:submittedExercise,blockId:payload.training_block_id??blockId,result};
    setAcceptedTrial(acknowledged);
    await reconcileAcceptedTrial(acknowledged);
     if(pauseExitAfterSubmit.current){pauseExitAfterSubmit.current=false;setPauseOpen(false);setPauseDraft(null);navigate('welcome');}
   }catch(e){
     if(pauseExitAfterSubmit.current){pauseExitAfterSubmit.current=false;setPauseOpen(false);setPauseDraft(null);}
    setError(acknowledged?'Your response was saved, but progress could not be refreshed. Retry progress refresh.':'Your response could not be confirmed. The exact saved response is retained; retry it to continue.');
   }finally{setSubmitting(false);lock.current=false;}
  },[pending,acceptedTrial,transitionLocked,blockId,reconcileAcceptedTrial]);
  const interrupt=useCallback(async(retry=false)=>{
   const submittedExercise=exerciseRef.current,id=sessionRef.current,item=submittedExercise?.items[indexRef.current];
   if(lock.current||interruptionSignal.current||(transitionLocked&&!retry)||pending||pageRef.current!=='assessment'&&pageRef.current!=='practice'||!submittedExercise||!id||!item||(submittedExercise.phase==='training'&&(decision||blockExhausted)))return;
   let payload=pendingInterruption;
   if(!payload||payload.session_id!==id||payload.exercise_id!==submittedExercise.exercise_id||payload.item_id!==item.item_id){
      const attention=submittedExercise.exercise_id==='EX-03';
      payload={event_id:crypto.randomUUID(),session_id:id,phase:submittedExercise.phase,exercise_id:submittedExercise.exercise_id,exercise_version:submittedExercise.exercise_version,item_id:item.item_id,...(submittedExercise.phase==='training'?{training_block_id:blockId}:{}),response_time_ms:null,stimulus_onset_ms:attention?attentionCueOnset.current:onset.current,visibility_interrupted:true};
    setPendingInterruption(payload);
    localStorage.setItem(INTERRUPTION,json(payload));
   }
   interruptionSignal.current=true;
   lock.current=true;
   setTransitionLocked(true);
   setError(null);
   let accepted=false;
   try{
    await request('/api/trials',{method:'POST',body:json(payload)});
    accepted=true;
    interruptionAccepted.current=true;
    setAcceptedInterruption(payload);
    setSelected(null);
    setTaskResponse(null);
    setResetKey(value=>value+1);
    await refreshSession(id);
    localStorage.removeItem(INTERRUPTION);
    setPendingInterruption(null);
    setAcceptedInterruption(null);
    setTransitionLocked(false);
    interruptionAccepted.current=false;
    interruptionSignal.current=false;
   }catch(e){
    if(accepted){
     interruptionAccepted.current=true;
     setAcceptedInterruption(payload);
     setError('Interruption was saved, but task state could not be refreshed. Retry progress refresh.');
    }else{
     interruptionAccepted.current=false;
     interruptionSignal.current=false;
     setError('Interruption could not be confirmed. Its exact request is retained; retry it before continuing.');
    }
   }finally{lock.current=false;}
  },[blockId,refreshSession,pending,pendingInterruption,transitionLocked,decision,blockExhausted]);
  const retryRecovery=useCallback(async()=>{
   if(lock.current)return;
   if(acceptedTrial){
    lock.current=true;setSubmitting(true);setError(null);
    try{await reconcileAcceptedTrial(acceptedTrial);}
    catch(e){setError('Your response was saved, but progress could not be refreshed. Retry progress refresh.');}
    finally{setSubmitting(false);lock.current=false;}
    return;
   }
   if(acceptedInterruption){
    lock.current=true;setSubmitting(true);setError(null);
    try{
     await refreshSession(acceptedInterruption.session_id);
     localStorage.removeItem(INTERRUPTION);setPendingInterruption(null);setAcceptedInterruption(null);setTransitionLocked(false);interruptionAccepted.current=false;interruptionSignal.current=false;
    }catch(e){setError('Interruption was saved, but task state could not be refreshed. Retry progress refresh.');}
    finally{setSubmitting(false);lock.current=false;}
    return;
   }
   if(pendingInterruption){
    if(pageRef.current!=='assessment'&&pageRef.current!=='practice'){await restore(pendingInterruption.session_id);return;}
    await interrupt(true);return;
   }
   if(pending){
    if(pageRef.current!=='assessment'&&pageRef.current!=='practice'){await restore(pending.session_id);return;}
    await submit();return;
   }
   if(sessionId)await restore(sessionId);
  },[acceptedTrial,acceptedInterruption,refreshSession,reconcileAcceptedTrial,pendingInterruption,pending,interrupt,submit,restore,sessionId]);
   const openGamePause=(draft?:Record<string,any>)=>{
    const cueWasActive=attentionCueActive.current;
    setPauseDraft(draft??null);
    setPauseOpen(true);
    if(cueWasActive&&!pauseInterruptedRef.current){
     pauseInterruptedRef.current=true;
     attentionCueActive.current=false;
     void interrupt();
    }
   };
   const resumeGameFromPause=()=>{
    if(transitionLocked||submitting)return;
    setPauseOpen(false);
    setPauseDraft(null);
    pauseInterruptedRef.current=false;
   };
   const exitGameFromPause=async()=>{
    if(transitionLocked||submitting)return;
    if(!pauseInterruptedRef.current&&!pendingInterruption&&!acceptedInterruption&&!localStorage.getItem(INTERRUPTION)){
     await interrupt();
     if(interruptionSignal.current||transitionLocked||localStorage.getItem(INTERRUPTION))return;
    }
    setPauseOpen(false);setPauseDraft(null);pauseInterruptedRef.current=false;navigate('welcome');
   };
   const recordDraftAndExit=()=>{if(!pauseDraft)return;pauseExitAfterSubmit.current=true;void submit(pauseDraft);};
  useEffect(()=>{
   const visibility=()=>{if(document.visibilityState==='hidden')void interrupt();else if(!interruptionAccepted.current&&!pendingInterruption)interruptionSignal.current=false;};
   const blur=()=>void interrupt();
   const focus=()=>{if(document.visibilityState==='visible'&&!interruptionAccepted.current&&!pendingInterruption)interruptionSignal.current=false;};
   document.addEventListener('visibilitychange',visibility);window.addEventListener('blur',blur);window.addEventListener('focus',focus);
   return()=>{document.removeEventListener('visibilitychange',visibility);window.removeEventListener('blur',blur);window.removeEventListener('focus',focus);};
  },[interrupt,pendingInterruption]);
  const beginTraining=async()=>{if(!sessionId)return;setLoading(true);try{// Always re-read the recommendation: a cached one can still describe the tier the
   // learner just left, which made the next block relaunch at the old tier.
   const rec=await request<any>('/api/recommendations/next',{method:'POST',body:json({session_id:sessionId,budget_minutes:budgetMinutes,...(goalDimension?{goal_dimension:goalDimension}:{})})});setRecommendation(rec);if(rec.action==='complete_baseline'){await restore(sessionId);return;}if(rec.action==='additional_assessment'){const cfg=await getConfig(sessionId,'EX-05','reassessment');setExercise(cfg);setItemIndex(0);setSelected(null);setTaskResponse(null);setPage('assessment');return;}const r=await request<any>('/api/training/blocks',{method:'POST',body:json({session_id:sessionId,exercise_id:rec.exercise_id??'EX-02',...(rec.tier&&['tier-1','tier-2','tier-3'].includes(String(rec.tier))?{tier:rec.tier}:{})})});setBlockId(r.block.block_id);localStorage.setItem(BLOCK,r.block.block_id);setBlockExhausted(false);setExercise(r.exercise);setItemIndex(0);setDecision(null);setPage('practice');}catch(e){setError(e instanceof Error?e.message:'Could not open the recommended practice block.');}finally{setLoading(false);}};
  const playFromHome=async()=>{
   const id=sessionRef.current??localStorage.getItem(SESSION);
   if(!id){await start();return;}
   if(pending||acceptedTrial||pendingInterruption||acceptedInterruption||localStorage.getItem(PENDING)||localStorage.getItem(INTERRUPTION)){
    await restore(id);return;
   }
   const savedBlockId=localStorage.getItem(BLOCK);
   if(savedBlockId){
    try{
     const [block,session]=await Promise.all([request<any>(`/api/training/blocks/${savedBlockId}`),request<any>(`/api/sessions/${id}`)]);
     const resume=trainingResumeIndex(block,id,(session.events??[]) as EventRow[]);
     if(!resume.finished){await restore(id);return;}
     localStorage.removeItem(BLOCK);setBlockId(null);setDecision(null);setBlockExhausted(false);setExercise(null);
    }catch(e){setError(e instanceof Error?e.message:'Could not verify the saved training block. Its saved state is preserved; retry to continue.');return;}
   }
   const dto=dashboard??await refreshDashboard();
   const assessedCount=Number(dto?.task_coverage?.assessed_count),totalCount=Number(dto?.task_coverage?.total_count);
   if(Number.isFinite(assessedCount)&&Number.isFinite(totalCount)&&totalCount>0&&assessedCount>=totalCount){
    setSessionId(id);sessionRef.current=id;await beginTraining();return;
   }
   await restore(id);
  };
  const openWorld=async(exerciseId:string)=>{
   if(transitionLocked){setError('Your saved response is still being confirmed. Use Continue journey to resume it first.');return;}
   // A restore or advance scan can still be in flight when the learner clicks a world.
   // Wait for it instead of silently swallowing the click, then report if it never clears.
   for(let waited=0;lock.current&&waited<60;waited+=1){
     await new Promise(resolve=>setTimeout(resolve,150));
   }
   if(lock.current){setError('The saved session is still loading. Try again in a moment.');return;}
   if(!sessionId&&!consent){setError('Please accept the preliminary-observations notice before starting a local session.');return;}
   lock.current=true;setLoading(true);setError(null);
   try{
    let id=sessionRef.current??localStorage.getItem(SESSION);
    if(!id){
     const created=await request<any>('/api/sessions',{method:'POST',body:json({learner_id:'demo-user',consent_accepted:true,dashboard_mode:mode==='quest'?'rpg':'analytics'})});
     if(typeof created.id!=='string'||!created.id)throw new Error('The local session could not be confirmed.');
     const createdSessionId:string=created.id;id=createdSessionId;localStorage.setItem(SESSION,createdSessionId);setSessionId(createdSessionId);sessionRef.current=createdSessionId;setSessionStartedAt(validStartedAt(created.started_at));
    }
    if(!id)throw new Error('The saved local session is unavailable.');
    setSessionId(id);sessionRef.current=id;
    if(pending||acceptedTrial||pendingInterruption||acceptedInterruption||localStorage.getItem(PENDING)||localStorage.getItem(INTERRUPTION)){
     lock.current=false;setLoading(false);await restore(id);return;
    }
    const session=await request<any>(`/api/sessions/${id}`);setSessionStartedAt(validStartedAt(session.started_at));
    const rows=(session.events??[]) as EventRow[];
    const savedBlockId=localStorage.getItem(BLOCK);
    const familyIndex=families.indexOf(exerciseId as typeof families[number]);
    if(familyIndex<0)throw new Error('That world is unavailable.');
    preferredFamily.current=exerciseId;localStorage.setItem(FAMILY,exerciseId);
    // Continue journey resumes the active block. An explicit world choice instead
    // resumes that world's latest unfinished block, found in canonical session events.
    // Other worlds' progress remains persisted and can be resumed when selected again.
    const latestFamilyBlock=[...rows].reverse().find(event=>event.type==='training_block_started'&&event.payload.exercise_id===exerciseId)?.payload.training_block_id;
    const candidates=[...new Set([savedBlockId,latestFamilyBlock].filter((value):value is string=>typeof value==='string'&&Boolean(value)))];
    for(const candidate of candidates){
     const block=await request<any>(`/api/training/blocks/${candidate}`);
     if(block.block?.exercise_id!==exerciseId)continue;
     const resume=trainingResumeIndex(block,id,rows);
     if(!resume.finished){localStorage.setItem(BLOCK,candidate);lock.current=false;setLoading(false);await restore(id);return;}
    }
    localStorage.removeItem(BLOCK);setBlockId(null);setDecision(null);setBlockExhausted(false);setExercise(null);
    const [practiceConfig,baselineConfig]=await Promise.all([getConfig(id,exerciseId,'practice'),getConfig(id,exerciseId,'baseline')]);
    const donePractice=new Set(rows.filter(event=>event.payload.exercise_id===exerciseId&&event.payload.phase==='practice'&&consumedTrial(event)).map(event=>event.payload.item_id));
    const doneBaseline=new Set(rows.filter(event=>event.payload.exercise_id===exerciseId&&event.payload.phase==='baseline'&&consumedTrial(event)).map(event=>event.payload.item_id));
    setSelected(null);setTaskResponse(null);setResetKey(value=>value+1);setDecision(null);
    if(donePractice.size<practiceConfig.items.length){setExercise(practiceConfig);setItemIndex(Math.max(0,practiceConfig.items.findIndex(item=>!donePractice.has(item.item_id))));setPage('assessment');return;}
    if(doneBaseline.size<baselineConfig.items.length){setExercise(baselineConfig);setItemIndex(Math.max(0,baselineConfig.items.findIndex(item=>!doneBaseline.has(item.item_id))));setPage('assessment');return;}
    // The explicit world owns its tier: the server resolves the family's canonical
    // current tier from its recorded decision, so no client tier is sent.
    const block=await request<any>('/api/training/blocks',{method:'POST',body:json({session_id:id,exercise_id:exerciseId})});
    setBlockId(block.block.block_id);localStorage.setItem(BLOCK,block.block.block_id);setBlockExhausted(false);setExercise(block.exercise);setItemIndex(0);setPage('practice');
   }catch(e){setError(e instanceof Error?e.message:'Could not open this world. Your saved session is still available.');}
   finally{setLoading(false);lock.current=false;}
  };
 const loadSavedPlan=useCallback(async(includeSamples=false)=>{
  const readRevision=modePreferenceRevision.current,readSession=sessionId;
  setPlanLoading(true);setPlanError(null);
  try{
   const saved=await request<any>('/api/plans/demo-user');setPlanData(saved);
   if(sessionId){
    try{
     const current=await request<any>('/api/recommendations/current');
     setRecommendation(current?.recommendation??null);
     if(current?.preferences?.goal_dimension!==undefined){setGoalDimension(current.preferences.goal_dimension??'');setGoalSaved(true);}
     const storedMode=current?.preferences?.dashboard_mode;
     if(storedMode&&readSession===sessionRef.current&&readRevision===modePreferenceRevision.current&&!modeWritePending.current){const resolved=storedMode==='rpg'?'quest':'analytics';savedModeRef.current=resolved;setMode(resolved);}
    }catch{/* Saved plans remain readable if the current recommendation endpoint is not ready. */}
   }
   if(includeSamples){try{setSampleScenarios(await request<any>('/api/personalization/sample-scenarios'));}catch{setSampleScenarios(null);}}
  }catch(e){setPlanError(e instanceof Error?e.message:'Saved plan service is unavailable.');}
  finally{setPlanLoading(false);}
 },[sessionId]);
 const updatePlan=useCallback(async()=>{if(!sessionId){setPlanError('Start a local session before requesting an evidence-based plan.');return;}setPlanLoading(true);setPlanError(null);const body={session_id:sessionId,budget_minutes:budgetMinutes,...(goalDimension?{goal_dimension:goalDimension}:{})};try{const rec=await request<any>('/api/recommendations/next',{method:'POST',body:json(body)});setRecommendation(rec);const created=await request<any>('/api/plans/next',{method:'POST',body:json(body)});const history=await request<any>('/api/plans/demo-user');setPlanData({learner_id:history.learner_id,latest:created,history:history.history??[]});}catch(e){setPlanError(e instanceof Error?e.message:'Could not update the plan.');}finally{setPlanLoading(false);}},[sessionId,budgetMinutes,goalDimension]);const saveGoal=useCallback(async()=>{if(!sessionId){setPlanError('Start a local session before saving a focus area.');return;}setPlanLoading(true);setPlanError(null);try{await request('/api/preferences',{method:'POST',body:json({session_id:sessionId,dashboard_mode:mode==='quest'?'rpg':'analytics',goal_dimension:goalDimension||null})});setGoalSaved(true);}catch(e){setPlanError(e instanceof Error?e.message:'Could not save the focus area.');}finally{setPlanLoading(false);}},[sessionId,mode,goalDimension]);useEffect(()=>{if(page==='plan')void loadSavedPlan(true);else if(page==='overview'||page==='welcome'||page==='practice'){void loadSavedPlan(false);void refreshDashboard();}},[page,loadSavedPlan,refreshDashboard]);
 const queryGraph=useCallback(async(query:EvidenceGraphQuery)=>{
  graphQueryRef.current=query;
  const generation=++graphRequest.current;
  const params=new URLSearchParams();
  for(const [key,value] of Object.entries(query)){
   if(value===undefined||value===null||value==='')continue;
   params.set(key,Array.isArray(value)?value.join(','):String(value));
  }
  if(graphRevisionRef.current)params.set('revision',graphRevisionRef.current);
  setGraphLoading(true);setGraphError(null);
  try{
   const g=await request<any>(`/api/graph/demo-user?${params.toString()}`);
   if(generation!==graphRequest.current)return;
   graphRevisionRef.current=typeof g?.revision==='string'?g.revision:null;
   setGraph(g);
  }catch(e){
   if(generation!==graphRequest.current)return;
   setGraph(null);setGraphError(e instanceof Error?e.message:'Graph service unavailable.');
  }finally{if(generation===graphRequest.current)setGraphLoading(false);}
 },[]);
 const loadGraph=useCallback(()=>void queryGraph({...graphQueryRef.current,dimension:graphDimension}),[queryGraph,graphDimension]);
 const resolveGraphRecord=useCallback(async(ref:EvidenceRecordRef,learnerId:string)=>{
  if(learnerId!=='demo-user')return null;
  const generation=++graphRecordRequest.current;
  const params=new URLSearchParams({kind:ref.kind,id:ref.id});
  try{
   const record=await request<any>(`/api/graph/${encodeURIComponent(learnerId)}/record?${params.toString()}`);
   return generation===graphRecordRequest.current?record:null;
  }catch(e){
   if(generation===graphRecordRequest.current)setGraphError(e instanceof Error?e.message:'Could not resolve that canonical record.');
   return null;
  }
 },[]);
 const openGraphRecord=useCallback((ref:EvidenceRecordRef,learnerId:string)=>{
  if(learnerId!=='demo-user')return;
  // The inspector already shows the resolved record; this opens its canonical,
  // read-only API representation so the underlying evidence remains inspectable.
  const params=new URLSearchParams({kind:ref.kind,id:ref.id});
  window.open(`/api/graph/${encodeURIComponent(learnerId)}/record?${params.toString()}`,'_blank','noopener,noreferrer');
 },[]);
 useEffect(()=>{if(page==='brain')void loadGraph()},[page,loadGraph]);
  const navigate=(target:Page)=>{
   // A learner navigation must not be overridden by a restore that was already running.
   navGeneration.current+=1;
   if(target!=='hybrid'){setHybridTimedWindow(false);setCompanionCheckpoint(null);}
   if(target!==page&&(page==='assessment'||page==='practice'))void interrupt();
   if(target==='overview'){if(sessionId)void refreshSession(sessionId);setPage(target);return;}
   if(target==='assessment'){
    // A finished or abandoned training block must not mask the assessment route.
    if(exercise?.phase==='training'){
     setExercise(null);setDecision(null);setBlockExhausted(false);setBlockId(null);setSelected(null);setTaskResponse(null);localStorage.removeItem(BLOCK);
    }
    if(sessionId){setPage('assessment');void restore(sessionId);}
    else if(consent)void start();
    else setPage('welcome');
    return;
   }
   setPage(target);
  };
  const coachExerciseId=(value:string|null|undefined):string|null=>{
   if(!value)return null;
   if(families.includes(value))return value;
   const match=Object.entries(dimensions).find(([,dimension])=>dimension===value);
   return match?.[0]??null;
  };
  const coachNavigate=(target:string)=>{
   let parsed:URL;
   try{parsed=new URL(target,window.location.origin);}catch{setError('That companion action is not available from this shell.');return;}
   if(parsed.origin!==window.location.origin){setError('That companion action is not available from this shell.');return;}
   if(parsed.pathname==='/evidence'){navigate('brain');return;}
   if(parsed.pathname==='/plan'){navigate('plan');return;}
   if(parsed.pathname==='/practice'){
    const exerciseId=coachExerciseId(parsed.searchParams.get('family'));
    if(exerciseId){void openWorld(exerciseId);return;}
    setError('The companion did not provide a practice family. Choose a world from the home page.');
    return;
   }
   setError('That companion action is not available from this shell.');
  };
  const coachRequestStrategy=(strategyId:string,exerciseId:string|null)=>{
   if(!strategyId){setError('The selected strategy is not available.');return;}
   const resolved=coachExerciseId(exerciseId);
   if(!resolved){setError('The companion did not provide a practice family for that strategy.');return;}
   void openWorld(resolved);
  };
  const coachSelectAction=async(selection:{requestId:string;actionId:string;target?:string;strategyId?:string;exerciseId?:string|null})=>{
   if(!sessionId)return;
   try{
    // The backend re-checks that this action was offered by the saved coaching turn
    // before anything is recorded or navigated.
    await request<any>('/api/coach/actions',{method:'POST',body:json({session_id:sessionId,request_id:selection.requestId,action_id:selection.actionId,...(selection.target?{target:selection.target}:{}),...(selection.strategyId?{strategy_id:selection.strategyId}:{}),...(selection.exerciseId?{exercise_id:selection.exerciseId}:{})})});
   }catch(e){
    setError(e instanceof Error?e.message:'That companion action could not be recorded, so nothing was opened.');
    return;
   }
   if(selection.actionId==='try_strategy'){coachRequestStrategy(selection.strategyId??'',selection.exerciseId??null);return;}
   if(selection.target)coachNavigate(selection.target);
  };
  const familyIndex=Math.max(0,families.indexOf((exercise?.exercise_id??'EX-01') as typeof families[number]));
  const journeyProgress={familyIndex,familyCount:families.length,completedFamilies:dashboard?.task_coverage?.assessed_count};
  const planSteps:any[]=planData?.latest?.steps??planData?.latest?.plan?.steps??planData?.steps??[];
  const practicePlanStep=planSteps.find((step:any)=>(step.dimension_id??dimensions[step.exercise_type_id])===(recommendation?.dimension??dimensions[recommendation?.exercise_id]));
  const refreshDecision=async()=>{if(!blockId)return;setLoading(true);try{const block=await request<any>(`/api/training/blocks/${blockId}`);if(block?.difficulty_decision)setDecision(block.difficulty_decision);else setError('The saved difficulty decision is not available yet.');}catch(e){setError(e instanceof Error?e.message:'Could not refresh the saved decision.');}finally{setLoading(false);}};
  // A saved difficulty decision changes the canonical next tier, so the cached
  // recommendation must be recomputed before the entry screen or next block reads it.
  const refreshRecommendation=useCallback(async()=>{if(!sessionId)return;try{const rec=await request<any>('/api/recommendations/next',{method:'POST',body:json({session_id:sessionId,budget_minutes:budgetMinutes,...(goalDimension?{goal_dimension:goalDimension}:{})})});if(rec)setRecommendation(rec);}catch{/* keep the previous recommendation; the next block launch retries */}},[sessionId,budgetMinutes,goalDimension]);
  useEffect(()=>{if(decision&&blockId)void refreshRecommendation();},[decision,blockId,refreshRecommendation]);
  // The practice entry must state the canonical tier. When no saved recommendation
  // exists yet, compute it once so the entry, the next block request and the saved
  // plan agree instead of showing "Tier unavailable".
  useEffect(()=>{
    if(page!=='practice'){recommendationFallback.current=false;return;}
    if(exercise?.phase==='training'||recommendation||!sessionId||recommendationFallback.current)return;
    recommendationFallback.current=true;
    void refreshRecommendation();
  },[page,exercise,recommendation,sessionId,refreshRecommendation]);
  const homeError=error??dashboardError;
  const retryHome=()=>{if(error)void retryRecovery();else void refreshDashboard();};
  const activeGame=(page==='hybrid'&&hybridActivityActive)||(page==='assessment'&&Boolean(exercise&&exercise.phase!=='training'&&active))||(page==='practice'&&Boolean(exercise?.phase==='training'&&active&&!decision&&!blockExhausted));
  const assessmentLabel=sessionId&&dashboard?.task_coverage&&dashboard.task_coverage.assessed_count<dashboard.task_coverage.total_count?'Resume assessment':'Assessment';
  return <MotionConfig reducedMotion="user"><div className={`app-shell adventure-app${activeGame?' is-game-page':''}${page==='welcome'?' home-shell':''}`}><Header setPage={navigate} mode={mode} setMode={changeMode}/><div className="adventure-layout"><DesktopNavigation page={page} onNavigate={navigate} onData={()=>setDataInfo(true)} assessmentLabel={assessmentLabel}/><div className="adventure-content">
  {error&&page!=='welcome'&&<div className="global-error" role="alert"><Info size={17}/><span>{error}</span>{(acceptedTrial||acceptedInterruption||pending||pendingInterruption||sessionId)&&<button className="secondary-button" disabled={submitting||loading} onClick={()=>void retryRecovery()}>{acceptedTrial||acceptedInterruption?'Retry progress refresh':pendingInterruption?'Retry saved interruption':pending?'Retry saved response':'Retry session restore'}</button>}<button onClick={()=>setError(null)} aria-label="Dismiss error"><X size={17}/></button></div>}{loading&&<div className="loading-strip" role="status"><LoaderCircle className="spin" size={17}/> Opening your saved activity…</div>}
  {page==='welcome'&&<AdventureHome dashboard={dashboard} loading={loading||dashboardLoading} error={homeError} notice={homeNotice} sessionId={sessionId} consent={consent} setConsent={setConsent} onPlay={playFromHome} onWorld={openWorld} onRetry={retryHome} onPlan={()=>navigate('plan')}/>}
  {page==='assessment'&&exercise&&exercise.phase!=='training'&&active&&<main className="adventure-game-stage"><TaskRenderer exercise={exercise} item={active} index={itemIndex} selected={selected} setSelected={setSelected} savedResponse={taskResponse} submitting={submitting||transitionLocked} pending={!!pending} onSubmit={submit} onStimulusOnset={value=>{attentionCueOnset.current=value}} resetKey={resetKey} sessionStartedAt={sessionStartedAt} journeyProgress={journeyProgress} onPause={openGamePause} paused={pauseOpen} onRecover={()=>void retryRecovery()} onCueActivity={value=>{attentionCueActive.current=value}}/></main>}
  {page==='assessment'&&(!exercise||!active||exercise.phase==='training')&&<main className="empty-assessment"><LoaderCircle className="spin"/>{loading?'Preparing the next task…':'No task is ready to open. Return to Play or your plan to continue.'}</main>}
  {page==='overview'&&<InsightsPage dashboard={dashboard as unknown as InsightDashboardSource} mode={mode} loading={dashboardLoading} error={dashboardError} onPlan={()=>navigate('plan')} onPractice={()=>navigate('practice')} onBrain={()=>navigate('brain')} onRefresh={()=>void refreshDashboard()} onCollaboration={()=>navigate('collaboration')} onModeChange={changeMode}/>}
  {page==='brain'&&<EvidencePage graph={graph} dimension={graphDimension} loading={graphLoading} error={graphError} selectedStrategyId={recommendation?.selected_strategy_id??null} onSelectDimension={setGraphDimension} onRefresh={()=>void loadGraph()} onQueryGraph={queryGraph} onResolveRecord={resolveGraphRecord} onOpenRecord={openGraphRecord} onOpenEvidenceRecord={eventId=>openGraphRecord({kind:'canonical_event',id:eventId},'demo-user')}/>}
  {page==='plan'&&<RedesignedPlanPage budget={budgetMinutes} setBudget={setBudgetMinutes} goal={goalDimension} setGoal={v=>{setGoalDimension(v);setGoalSaved(false);}} loading={planLoading} error={planError} plan={planData} recommendation={recommendation} samples={sampleScenarios} goalSaved={goalSaved} launchingStepId={launchingPlanStep} onSaveGoal={()=>void saveGoal()} onRefresh={()=>void updatePlan()} onLaunchStep={step=>void launchPlanStep(step)} onExploreActivities={()=>navigate('hybrid')} onAction={async()=>{const navToken=navGeneration.current;if(recommendation?.action==='complete_baseline'){if(sessionId)await restore(sessionId);else navigate('welcome');}else if(recommendation?.action==='additional_assessment'&&sessionId){try{setLoading(true);const cfg=await getConfig(sessionId,'EX-05','reassessment');if(navGeneration.current!==navToken)return;setExercise(cfg);setItemIndex(0);setSelected(null);setTaskResponse(null);setPage('assessment');}catch(e){setPlanError(e instanceof Error?e.message:'Could not load the comparable task set.');}finally{setLoading(false);}}else navigate('practice');}}/>}
  {page==='hybrid'&&<HybridPage sessionId={sessionId}
    initialActivityId={planLaunch?.response?.destination.kind==='crystal'?'crystal':planLaunch?.response?.destination.kind==='hybrid'?planLaunch.response.destination.id as any:null}
    initialAttemptId={planLaunch?.response?.attempt_ref.id??null}
    onActivityActiveChange={setHybridActivityActive} onCheckpoint={receiveHybridCheckpoint} onTimedWindowChange={setHybridTimedWindow}
    onActivityExit={planLaunch?()=>{localStorage.removeItem(PLAN_LAUNCH);setPlanLaunch(null);navigate('plan');void loadSavedPlan(false);}:undefined}
    onChanged={()=>{if(sessionId){void refreshSession(sessionId);}void loadSavedPlan(false);}}/>}
  {page==='collaboration'&&<CollaborationPageContainer sessionId={sessionId} onChanged={()=>{if(sessionId){void refreshSession(sessionId);}void loadSavedPlan(false);}}/>}
  {page==='practice'&&<Practice sessionStartedAt={sessionStartedAt} exercise={exercise} itemIndex={itemIndex} selected={selected} setSelected={setSelected} responseData={taskResponse} pending={!!pending} submitting={submitting||transitionLocked} decision={decision} recommendation={recommendation} planStep={practicePlanStep} resetKey={resetKey} exhausted={blockExhausted} blockLoading={loading} onStart={beginTraining} onSubmit={submit} onStimulusOnset={value=>{attentionCueOnset.current=value}} onReset={()=>{setDecision(null);setBlockExhausted(false);setBlockId(null);setExercise(null);localStorage.removeItem(BLOCK);navigate('overview');}} onRetryDecision={()=>void refreshDecision()} onPlan={()=>navigate('plan')} onBrain={()=>navigate('brain')} journeyProgress={journeyProgress} onPause={openGamePause} paused={pauseOpen} onCueActivity={value=>{attentionCueActive.current=value}}/>}
  </div></div><MobileNavigation page={page} onNavigate={navigate} onData={()=>setDataInfo(true)} assessmentLabel={assessmentLabel}/>
  {pauseOpen&&<PauseOverlay open taskLabel={exercise?dimensionNames[dimensions[exercise.exercise_id]]??exercise.exercise_id:null} phaseLabel={exercise?.phase??null} canResume={!transitionLocked} busy={submitting||loading} betweenSignals={exercise?.exercise_id==='EX-03'} savedResponsePending={!!pending} savedInterruptionPending={!!(pendingInterruption||acceptedInterruption)} draftAvailable={!!pauseDraft} onResume={resumeGameFromPause} onRetrySavedResponse={()=>void retryRecovery()} onRetrySavedInterruption={()=>void retryRecovery()} onSubmitDraft={recordDraftAndExit} onLeave={()=>void exitGameFromPause()} leaveLabel={pending||pendingInterruption?'Return home with saved retry':'Save interruption and return home'}/>}
  {dataInfo&&<DataManager onClose={closeData} onDeleted={()=>{clearOriginalActivityRecovery();localStorage.removeItem(SESSION);localStorage.removeItem(BLOCK);localStorage.removeItem(PENDING);localStorage.removeItem(INTERRUPTION);localStorage.removeItem(FAMILY);setPendingInterruption(null);setAcceptedInterruption(null);setTransitionLocked(false);setSessionId(null);setSessionStartedAt(null);sessionRef.current=null;setExercise(null);setItemIndex(0);setSelected(null);setTaskResponse(null);setPending(null);setDecision(null);setBlockId(null);setDashboard(null);setDashboardError(null);setPlanData(null);setRecommendation(null);setPlanError(null);setGraph(null);setGraphError(null);setConsent(false);setMode('analytics');setPage('welcome');setError(null);setHomeNotice(null);setDataResetKey(v=>v+1);}}/>}
  <Companion key={dataResetKey} page={page} phase={exercise?.phase} quietTask={pauseOpen||(page==='hybrid'&&hybridTimedWindow)||exercise?.exercise_id==='EX-03'&&(page==='assessment'||page==='practice')&&!decision} checkpoint={companionCheckpoint} decision={decision} sessionId={sessionId} itemId={active?.item_id} blockId={blockId} onCoachNavigate={coachNavigate} onCoachRequestStrategy={coachRequestStrategy} onCoachAction={coachSelectAction} onRecorded={()=>{if(sessionId)void refreshSession(sessionId);}}/><footer className="app-footer"><span>Non-clinical · Local data</span><span>Five task families · Indices are not comparable</span><button className="footer-data-button" onClick={()=>setDataInfo(true)}><Database size={14}/> Data & privacy</button></footer></div></MotionConfig>;
}
