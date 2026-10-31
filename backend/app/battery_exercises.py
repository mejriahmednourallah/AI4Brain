"""Original frozen baseline tasks and server-owned evaluation for EX-01/03/04/05."""
from __future__ import annotations
import hashlib
import random
from collections import deque
from copy import deepcopy
from typing import Any
from .difficulty import DECISION_TRIAL_COUNT

VERSIONS = {'EX-01':'memory-v2','EX-03':'attention-v1','EX-04':'switching-v1','EX-05':'planning-v1'}
DIMENSIONS = {'EX-01':'working_memory','EX-03':'attention_inhibition','EX-04':'flexibility','EX-05':'planning'}
LEGACY_TRAINING_VERSIONS = {eid:f'training-{eid.lower()}-v1' for eid in DIMENSIONS}
TRAINING_VERSIONS = {eid:f'training-{eid.lower()}-v2' for eid in DIMENSIONS}
V2_COLORS=('blue','red','yellow','purple')
V2_SHAPES=('circle','square','triangle','diamond')
COLORS = ('red','blue','yellow')
SHAPES = ('circle','square','triangle')

def _seed(seed: str, key: str) -> int:
    return int(hashlib.sha256(f'{seed}:{key}'.encode()).hexdigest()[:16],16)

def _item(item_id: str, stimulus: dict, **extra: Any) -> dict:
    return {'item_id':item_id,'prompt':'','stimulus':stimulus,**extra}

def _memory_bank() -> list[dict]:
    sequences = [[0,4,8],[6,1,5],[2,5,4,7],[8,3,0,6],[1,4,2,7,0],[7,5,1,8,3]]
    return [_item(f'memory-spatial-{i+1:02d}',{'sequence':seq,'rows':3,'columns':3,'length':len(seq),'playback_ms':700}) for i,seq in enumerate(sequences)]

def _attention_schedule(seed: str) -> list[dict]:
    rng=random.Random(_seed(seed,'EX-03'))
    for _ in range(256):
        signals=['go']*30+['no_go']*10
        rng.shuffle(signals)
        if signals[0]=='go' and all(signals[i:i+3]!=['no_go']*3 for i in range(38)):
            break
    else:
        signals=['go','go','go','no_go']*10
    return [_item(f'attention-trial-{i+1:02d}',{'signal':signal,'symbol':'circle' if signal=='go' else 'square','color':'blue' if signal=='go' else 'gray','response_window_ms':1500}) for i,signal in enumerate(signals)]

def _switch_bank(seed: str, practice: bool=False) -> list[dict]:
    length=4 if practice else 24
    switches={1,3} if practice else {3,6,9,12,15,18,21,23}
    rng=random.Random(_seed(seed,'EX-04-practice' if practice else 'EX-04'))
    current='color'
    rows=[]
    for i in range(length):
        previous=current
        if i in switches: current='shape' if current=='color' else 'color'
        color=COLORS[(2*i+1)%3]; shape=SHAPES[(i+1)%3]
        alternatives=[{'color':color,'shape':next(x for x in SHAPES if x!=shape)},
                      {'color':next(x for x in COLORS if x!=color),'shape':shape}]
        rng.shuffle(alternatives)
        options=[{'id':letter,**option} for letter,option in zip(('A','B'),alternatives)]
        rows.append(_item(f"switch-{'practice' if practice else 'trial'}-{i+1:02d}",{'target':{'color':color,'shape':shape},'active_rule':current,'previous_rule':previous,'switch':i>0 and current!=previous,'options':options}))
    return rows

PLANNING_BOARDS=[
    {'item_id':'planning-puzzle-01','width':3,'height':3,'start':[0,0],'goal':[2,2],'walls':[[1,1]]},
    {'item_id':'planning-puzzle-02','width':4,'height':3,'start':[0,1],'goal':[3,1],'walls':[[1,1],[2,1]]},
    {'item_id':'planning-puzzle-03','width':4,'height':4,'start':[0,0],'goal':[3,3],'walls':[[1,0],[1,1],[1,2],[3,2]]},
]
DIRECTIONS={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}

def shortest_path(board: dict) -> list[str]:
    start=tuple(board['start']);goal=tuple(board['goal']);walls={tuple(p) for p in board['walls']}
    queue=deque([(start,[])]);seen={start}
    while queue:
        pos,path=queue.popleft()
        if pos==goal:return path
        for name,(dx,dy) in DIRECTIONS.items():
            nxt=(pos[0]+dx,pos[1]+dy)
            if 0<=nxt[0]<board['width'] and 0<=nxt[1]<board['height'] and nxt not in walls and nxt not in seen:
                seen.add(nxt);queue.append((nxt,path+[name]))
    raise ValueError('unsolvable planning board')

def exercise_items(exercise_id: str, session_id: str) -> list[dict]:
    if exercise_id=='EX-01':
        bank=_memory_bank();rng=random.Random(_seed(session_id,'memory-order'))
        # Each half contains one length3,4,5 item; only order changes between sessions.
        halves=[[bank[0],bank[2],bank[4]],[bank[1],bank[3],bank[5]]]
        for half in halves:rng.shuffle(half)
        return halves[0]+halves[1]
    if exercise_id=='EX-03':return _attention_schedule(session_id)
    if exercise_id=='EX-04':return _switch_bank(session_id)
    if exercise_id=='EX-05':return [_item(board['item_id'],deepcopy(board)) for board in PLANNING_BOARDS]
    raise KeyError('unknown exercise')

def public_exercise(exercise_id: str, phase: str, session_id: str) -> dict:
    if phase not in {'practice','baseline'}:raise ValueError('unsupported phase')
    items=exercise_items(exercise_id,session_id)
    if phase=='practice':
        if exercise_id=='EX-01':items=[_item('memory-practice-01',{'sequence':[0,4,2],'rows':3,'columns':3,'length':3,'playback_ms':700})]
        elif exercise_id=='EX-03':items=[_item(f'attention-practice-{i+1:02d}',{'signal':'go' if i%3!=2 else 'no_go','symbol':'circle' if i%3!=2 else 'square','color':'blue' if i%3!=2 else 'gray','response_window_ms':1500}) for i in range(6)]
        elif exercise_id=='EX-04':items=_switch_bank(session_id,practice=True)
        else:items=[_item('planning-tutorial',{'width':2,'height':2,'start':[0,0],'goal':[1,1],'walls':[]})]
    instructions={'EX-01':'Watch the highlighted positions on the 3 by 3 grid. Repeat them in the same order.',
                  'EX-03':'Respond to the blue GO circle. Withhold your response to the gray NO-GO square.',
                  'EX-04':'Match the target using only the current color or shape rule.',
                  'EX-05':'Move the marker to the goal around blocked cells using as few legal steps as possible.'}
    for row in items:row['prompt']=instructions[exercise_id]
    return {'schema_version':'1.0.0','exercise_id':exercise_id,'exercise_version':VERSIONS[exercise_id],
            'phase':phase,'items':items,'instructions':instructions[exercise_id]}

def evaluate_memory(item: dict, response: dict) -> dict:
    selected=response.get('selected_sequence')
    expected=item['stimulus']['sequence']
    if not isinstance(selected,list) or len(selected)>len(expected) or any(type(cell) is not int or not 0<=cell<=8 for cell in selected):
        raise ValueError('selected_sequence must contain grid positions0..8, no longer than the presented sequence')
    positions=[i<len(selected) and selected[i]==cell for i,cell in enumerate(expected)]
    correct=len(selected)==len(expected) and all(positions)
    return {'correct':correct,'position_correct':positions,'correct_positions':sum(positions),'expected_positions':len(expected),
            'fully_correct_span':len(expected) if correct else 0,'error_type':None if correct else 'order_mismatch'}

def evaluate_attention(item: dict, response: dict) -> dict:
    responded=response.get('responded')
    if type(responded) is not bool:raise ValueError('responded must be boolean')
    rt=response.get('response_time_ms')
    if responded and (not isinstance(rt,(int,float)) or isinstance(rt,bool) or rt<0):raise ValueError('a response requires nonnegative browser response_time_ms')
    window=item['stimulus']['response_window_ms'];late=bool(responded and rt>window)
    eligible_press=responded and not late
    signal=item['stimulus']['signal']
    result=('hit' if eligible_press else 'omission') if signal=='go' else ('commission_error' if eligible_press else 'correct_rejection')
    correct=result in {'hit','correct_rejection'}
    return {'correct':correct,'result':result,'response_time_ms':rt if responded else None,'early':bool(responded and rt<100),
            'outlier':bool(responded and (rt<100 or late)),'late_response':late,'response_window_ms':window,
            'error_type':None if correct else result}

def evaluate_switch(item: dict, response: dict) -> dict:
    chosen=response.get('choice');s=item['stimulus'];options={o['id']:o for o in s['options']}
    if chosen not in options:raise ValueError('choice must be A or B')
    correct_option=next(o['id'] for o in options.values() if o[s['active_rule']]==s['target'][s['active_rule']])
    right=chosen==correct_option
    previous=next(o['id'] for o in options.values() if o[s['previous_rule']]==s['target'][s['previous_rule']])
    return {'correct':right,'component':'switch' if s['switch'] else 'repeat',
            'error_previous_rule':bool(not right and s['switch'] and chosen==previous),
            'error_type':None if right else ('error_previous_rule' if s['switch'] and chosen==previous else 'incorrect_rule')}

def replay_planning(item: dict, response: dict) -> dict:
    board=item['stimulus'];pos=list(board['start']);stack=[];illegal=undos=restarts=moves=0
    actions=response.get('actions')
    if not isinstance(actions,list) or len(actions)>500 or any(not isinstance(a,dict) for a in actions):raise ValueError('actions must be a list of move/undo/restart objects (max500)')
    walls={tuple(p) for p in board['walls']}
    for action in actions:
        kind=action.get('action')
        if kind=='move':
            direction=action.get('direction')
            if direction not in DIRECTIONS:illegal+=1;continue
            dx,dy=DIRECTIONS[direction];nxt=[pos[0]+dx,pos[1]+dy]
            if not(0<=nxt[0]<board['width'] and 0<=nxt[1]<board['height']) or tuple(nxt) in walls:illegal+=1;continue
            stack.append(pos);pos=nxt;moves+=1
        elif kind=='undo':
            if stack:pos=stack.pop();undos+=1;moves+=1
        elif kind=='restart':pos=list(board['start']);stack=[];restarts+=1
        else:illegal+=1
    complete=pos==board['goal'];optimum=len(shortest_path(board))
    efficiency=min(100.,100.*optimum/moves) if complete and moves else 0.
    return {'completed':complete,'correct':complete,'legal_moves':moves,'illegal_moves':illegal,'undo_count':undos,
            'restart_count':restarts,'optimal_moves':optimum,'efficiency_0_100':round(efficiency,2),
            'excess_moves':max(0,moves-optimum) if complete else None,'final_position':pos,
            'error_type':None if complete and efficiency>=80 else ('inefficient_moves' if complete else 'incomplete_puzzle')}
# Versioned deterministic training banks. IDs are distinct from all frozen baseline items.
_TIER_NUMBER = {"tier-1":1,"tier-2":2,"tier-3":3}

def _legacy_training_items(exercise_id: str, tier: str) -> list[dict]:
    level=_TIER_NUMBER.get(tier)
    if level is None: raise ValueError("tier must be tier-1, tier-2, or tier-3")
    suffix=f"{tier}"
    rows=[]
    if exercise_id=="EX-01":
        base=[[0,4,2,6,1],[6,1,4,0,8],[2,5,3,7,1],[8,3,1,6,2],[1,4,2,8,0],[7,5,1,8,2],[0,8,2,6,4],[3,7,1,5,0]]
        challenge_length=level+2
        for i,seq in enumerate(base):
            shown=seq[:challenge_length]
            rows.append(_item(f"memory-training-{suffix}-{i+1:02d}",{"sequence":shown,"rows":3,"columns":3,"length":len(shown),"playback_ms":700}))
    elif exercise_id=="EX-03":
        # Four go and four no-go trials in every block; no three consecutive no-go cues.
        for i in range(8):
            signal="no_go" if i in ({1,3,5,7} if level==1 else {0,2,4,6} if level==2 else {1,2,5,6}) else "go"
            rows.append(_item(f"attention-training-{suffix}-{i+1:02d}",{"signal":signal,"symbol":"circle" if signal=="go" else "square","color":"blue" if signal=="go" else "gray","response_window_ms":1800-300*(level-1)}))
    elif exercise_id=="EX-04":
        # The first four items form the adaptive window: 1/2/3 active-rule changes by tier.
        switch_positions={1:{2},2:{1,3},3:{1,2,3}}[level]
        rng=random.Random(_seed(f"training:{suffix}","EX-04"));current="color"
        for i in range(8):
            previous=current
            if i in switch_positions:current="shape" if current=="color" else "color"
            color=COLORS[(2*i+level)%3];shape=SHAPES[(i+level)%3]
            alternatives=[{"color":color,"shape":next(x for x in SHAPES if x!=shape)},
                          {"color":next(x for x in COLORS if x!=color),"shape":shape}]
            rng.shuffle(alternatives)
            options=[{"id":letter,**option} for letter,option in zip(("A","B"),alternatives)]
            rows.append(_item(f"switch-training-{suffix}-{i+1:02d}",{"target":{"color":color,"shape":shape},"active_rule":current,
                "previous_rule":previous,"switch":i>0 and current!=previous,"options":options}))
    elif exercise_id=="EX-05":
        # Eight distinct, BFS-solvable layouts per tier with increasing board size/obstacle density.
        layouts={
            1:[(3,3,(0,0),(2,2),[[1,1]]),(3,3,(0,2),(2,0),[[1,1]]),(3,3,(0,0),(2,1),[[1,0]]),(3,3,(0,1),(2,2),[[1,2]]),(3,3,(0,0),(2,2),[[0,1]]),(3,3,(0,2),(2,0),[[2,1]]),(3,3,(0,0),(2,1),[[1,1]]),(3,3,(0,1),(2,0),[[1,1]])],
            2:[(4,3,(0,1),(3,1),[[1,1],[2,1]]),(4,3,(0,0),(3,2),[[1,0],[2,1]]),(4,3,(0,2),(3,0),[[1,2],[2,1]]),(4,3,(0,1),(3,0),[[1,1],[2,2]]),(4,3,(0,0),(3,1),[[1,0],[2,2]]),(4,3,(0,2),(3,1),[[1,2],[2,0]]),(4,3,(0,1),(3,2),[[1,1],[2,0]]),(4,3,(0,0),(3,2),[[1,1],[2,1]])],
            3:[(4,4,(0,0),(3,3),[[1,0],[1,1],[1,2],[3,2]]),(4,4,(0,3),(3,0),[[1,1],[2,1],[2,2]]),(4,4,(0,0),(3,3),[[1,0],[2,2],[3,1]]),(4,4,(0,3),(3,0),[[1,2],[2,1],[2,3]]),(4,4,(0,0),(3,2),[[1,0],[2,1],[3,3]]),(4,4,(0,2),(3,0),[[1,2],[2,1],[3,3]]),(4,4,(0,1),(3,3),[[1,1],[2,2],[3,0]]),(4,4,(0,3),(3,1),[[1,2],[2,0],[3,3]])]}
        for i,(w,h,start,goal,walls) in enumerate(layouts[level]):
            board={"width":w,"height":h,"start":list(start),"goal":list(goal),"walls":walls}
            shortest_path(board)
            rows.append(_item(f"planning-training-{suffix}-{i+1:02d}",board))
    else: raise KeyError("unknown exercise")
    for row in rows: row["difficulty"]=tier
    return rows

def _training_memory_v2(tier:str,block_id:str)->list[dict]:
    level=_TIER_NUMBER[tier];rng=random.Random(_seed(block_id,'EX-01-training-v2'));items=[]
    for index in range(8):
        length=2*level+2+rng.randrange(2);sequence=[]
        while len(sequence)<length:
            cell=rng.randrange(9)
            if not sequence or cell!=sequence[-1]:sequence.append(cell)
        items.append(_item(f'memory-training-{tier}-{index+1:02d}',{'sequence':sequence,'rows':3,'columns':3,'length':length,'playback_ms':700},difficulty=tier))
    return items

def _training_attention_v2(tier:str,block_id:str)->list[dict]:
    level=_TIER_NUMBER[tier];rng=random.Random(_seed(block_id,'EX-03-training-v2'))
    near_misses=[('blue','square'),('blue','triangle'),('red','circle'),('yellow','circle'),('purple','circle'),('red','square')]
    items=[]
    for index in range(8):
        signal='go' if index%4<2 else 'no_go'
        # Independently balance both halves so the controller's first four are comparable.
        if index<4:signal='go' if index in {0,3} else 'no_go'
        if index>=4:signal='go' if index in {4,7} else 'no_go'
        color,symbol=('blue','circle') if signal=='go' else near_misses[rng.randrange(len(near_misses))]
        items.append(_item(f'attention-training-{tier}-{index+1:02d}',{'signal':signal,'symbol':symbol,'color':color,
            'response_window_ms':1500-300*(level-1)},difficulty=tier))
    # Shuffle within the first and second four-item balanced windows, retaining their 2/2 ratio.
    first=items[:4];second=items[4:];rng.shuffle(first);rng.shuffle(second)
    return first+second

def _training_switch_v2(tier:str,block_id:str)->list[dict]:
    level=_TIER_NUMBER[tier];rng=random.Random(_seed(block_id,'EX-04-training-v2'))
    switches={1:{2,6},2:{1,3,6,7},3:{1,2,3,5,6,7}}[level]
    option_count=4 if level==3 else 3;current='color';items=[]
    for index in range(8):
        previous=current
        if index in switches:current='shape' if current=='color' else 'color'
        target={'color':rng.choice(V2_COLORS),'shape':rng.choice(V2_SHAPES)}
        active_values=V2_COLORS if current=='color' else V2_SHAPES
        other_values=V2_SHAPES if current=='color' else V2_COLORS
        correct_other=target['shape'] if current=='color' else target['color']
        candidates=[(target['color'],target['shape'])]
        distractor_active=[value for value in active_values if value!=target[current]]
        rng.shuffle(distractor_active)
        previous_value=target[previous]
        if previous!=current:
            previous_other=previous_value
            previous_active=distractor_active.pop(0)
            pair=(previous_active,previous_other) if current=='color' else (previous_other,previous_active)
            candidates.append(pair)
        attempts=0
        while len(candidates)<option_count and attempts<100:
            attempts+=1
            active_value=distractor_active[(len(candidates)-1)%len(distractor_active)]
            other_value=rng.choice(other_values)
            pair=(active_value,other_value) if current=='color' else (other_value,active_value)
            if pair not in candidates:candidates.append(pair)
        if len(candidates)!=option_count:raise AssertionError('could not build unique rule-switch options')
        rng.shuffle(candidates)
        options=[{'id':letter,'color':color,'shape':shape} for letter,(color,shape) in zip(('A','B','C','D'),candidates)]
        if sum(option[current]==target[current] for option in options)!=1:raise AssertionError('training switch has ambiguous active rule')
        items.append(_item(f'switch-training-{tier}-{index+1:02d}',{'target':target,'active_rule':current,'previous_rule':previous,
            'switch':index>0 and current!=previous,'options':options},difficulty=tier))
    return items

def _training_planning_v2(tier:str,block_id:str)->list[dict]:
    level=_TIER_NUMBER[tier];size={1:5,2:7,3:9}[level]
    min_path={1:8,2:12,3:16}[level];wall_rate={1:.18,2:.21,3:.23}[level]
    rng=random.Random(_seed(block_id,'EX-05-training-v2'));items=[];seen=set()
    for index in range(8):
        board=None
        for _ in range(3000):
            start=[0,rng.randrange(size)];goal=[size-1,rng.randrange(size)]
            walls=[]
            for y in range(size):
                for x in range(size):
                    if [x,y] not in (start,goal) and rng.random()<wall_rate:walls.append([x,y])
            candidate={'item_id':f'planning-puzzle-{tier}-{index+1:02d}','width':size,'height':size,
                       'start':start,'goal':goal,'walls':walls}
            try:path=shortest_path(candidate)
            except ValueError:continue
            if len(path)<min_path:continue
            # Require reachable branching locations so layouts are not simple corridors.
            open_cells={(x,y) for y in range(size) for x in range(size) if [x,y] not in walls}
            branch_points=sum(sum((x+dx,y+dy) in open_cells for dx,dy in DIRECTIONS.values())>=3 for x,y in open_cells)
            signature=(tuple(start),tuple(goal),tuple(map(tuple,walls)))
            if branch_points<4 or signature in seen:continue
            seen.add(signature);board=candidate;break
        if board is None:raise RuntimeError(f'could not generate a branching solvable {size}x{size} training maze')
        items.append(_item(board['item_id'],board,difficulty=tier))
    return items

def training_items(exercise_id: str, tier: str, block_id: str | None=None,
                   version: str | None=None) -> list[dict]:
    version=version or LEGACY_TRAINING_VERSIONS[exercise_id]
    if version==LEGACY_TRAINING_VERSIONS[exercise_id]:return _legacy_training_items(exercise_id,tier)
    if version!=TRAINING_VERSIONS[exercise_id]:raise ValueError('unsupported training exercise version')
    seed=block_id or f'preview:{exercise_id}:{tier}'
    if exercise_id=='EX-01':return _training_memory_v2(tier,seed)
    if exercise_id=='EX-03':return _training_attention_v2(tier,seed)
    if exercise_id=='EX-04':return _training_switch_v2(tier,seed)
    if exercise_id=='EX-05':return _training_planning_v2(tier,seed)
    raise KeyError('unknown battery exercise')

def battery_training_exercise(exercise_id: str, tier: str, block_id: str,
                              version: str | None=None) -> dict:
    version=version or LEGACY_TRAINING_VERSIONS[exercise_id]
    items=training_items(exercise_id,tier,block_id,version)
    instructions={"EX-01":"Watch the highlighted positions, then repeat them in order.",
        "EX-03":"Respond to the blue GO circle. Withhold your response to the gray NO-GO square.",
        "EX-04":"Match the target using only the current color or shape rule.",
        "EX-05":"Move the marker to the goal around blocked cells using few legal steps."}
    if exercise_id=="EX-03" and version==TRAINING_VERSIONS[exercise_id]:
        instructions["EX-03"]="Respond only when the cue is a blue circle. Withhold your response to every other color and shape pairing."
    for row in items: row["prompt"]=instructions[exercise_id]
    return {"schema_version":"1.0.0","exercise_id":exercise_id,"exercise_version":version,
        "phase":"training","difficulty_tier":tier,"training_block_id":block_id,"challenge_seed":block_id,
        "items":items,"instructions":instructions[exercise_id],"decision_trial_count":DECISION_TRIAL_COUNT}
REASSESSMENT_VERSION = "reassessment-v1"
def battery_reassessment_exercise(exercise_id: str, session_id: str) -> dict:
    if exercise_id=="EX-05":
        layouts=[
            (4,4,(0,0),(3,3),[[1,0],[1,1],[1,2],[3,1]]),
            (4,4,(0,3),(3,0),[[1,2],[2,2],[2,1]]),
            (4,4,(0,1),(3,3),[[1,1],[2,1],[2,2]])]
        items=[]
        for i,(w,h,start,goal,walls) in enumerate(layouts):
            board={"width":w,"height":h,"start":list(start),"goal":list(goal),"walls":walls}
            shortest_path(board)
            items.append(_item(f"planning-reassessment-{i+1:02d}",board))
    elif exercise_id=="EX-01":
        sequences=[[8,4,0],[1,6,3],[7,0,5,2],[2,8,4,1],[3,5,0,7,2],[6,2,8,1,4]]
        rows=[_item(f"memory-reassessment-{i+1:02d}",{"sequence":seq,"rows":3,"columns":3,"length":len(seq),"playback_ms":700}) for i,seq in enumerate(sequences)]
        rng=random.Random(_seed(session_id,"EX-01-reassessment"))
        halves=[rows[:3],rows[3:]]
        for half in halves:rng.shuffle(half)
        items=halves[0]+halves[1]
    elif exercise_id=="EX-03":
        items=_attention_schedule(session_id+":reassessment")
        for i,item in enumerate(items):item["item_id"]=f"attention-reassessment-{i+1:02d}"
    elif exercise_id=="EX-04":
        items=_switch_bank(session_id+":reassessment")
        for i,item in enumerate(items):item["item_id"]=f"switch-reassessment-{i+1:02d}"
    else:raise ValueError("reasoning reassessment is not configured")
    return {"schema_version":"1.0.0","exercise_id":exercise_id,"exercise_version":REASSESSMENT_VERSION,
        "phase":"reassessment","items":items,"instructions":"Complete this new, comparable fixed item set. It is additional task evidence and does not overwrite the original baseline."}
