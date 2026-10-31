export type CrystalConfig = { form_version:string; generator_version:string; prompt:string; grid:(number|null)[][]; choices:{choice_id:string;value:number}[] };
const req=async <T,>(url:string,body?:unknown):Promise<T>=>{const r=await fetch(url,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok)throw new Error(d.detail||`Request failed (${r.status})`);return d as T;};
export const startCrystal=(body:{event_id:string;session_id:string;learner_id:string})=>req<{attempt_id:string;config:CrystalConfig;status:string}>('/api/crystal/attempts',body);
export const getCrystal=(id:string)=>req<{attempt_id:string;status:string;config:CrystalConfig;outcome:any}>(`/api/crystal/attempts/${id}`);
export const answerCrystal=(id:string,body:{event_id:string;choice_id:string})=>req<{accepted:boolean;replayed:boolean;outcome:any}>(`/api/crystal/attempts/${id}/answer`,body);
export const crystalUid=()=>crypto.randomUUID();
