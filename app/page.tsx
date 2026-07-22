"use client";

import { useMemo, useRef, useState } from "react";

type SpeechRecognitionLike = { lang:string; interimResults:boolean; continuous:boolean; start():void; stop():void; onresult:((event:{results:ArrayLike<{0:{transcript:string}}>})=>void)|null; onend:(()=>void)|null; onerror:(()=>void)|null };
declare global { interface Window { SpeechRecognition?:new()=>SpeechRecognitionLike; webkitSpeechRecognition?:new()=>SpeechRecognitionLike } }

const roles = [
  {name:"Codex",role:"Architecture · integration",state:"connected",tone:"green"},
  {name:"Claude",role:"Implementation · review",state:"connect",tone:"gray"},
  {name:"Kimi",role:"Operations · maintenance",state:"local",tone:"amber"},
  {name:"Grok",role:"X · GitHub scouting",state:"key required",tone:"gray"},
  {name:"Gemini",role:"Multimodal · video",state:"interactive",tone:"blue"},
];
const initialSteps = [
  ["01","Evidence scout","Grok + GitHub","waiting"],
  ["02","Architecture contract","Codex","waiting"],
  ["03","Independent test design","Kimi","waiting"],
  ["04","Implementation","Claude","waiting"],
  ["05","Adversarial review","Codex","waiting"],
  ["06","Fix + deterministic verification","Claude + Node","waiting"],
];

export default function Home(){
  const [brief,setBrief]=useState(""); const [listening,setListening]=useState(false); const [mission,setMission]=useState(false); const [active,setActive]=useState("Command"); const [collapsed,setCollapsed]=useState(false);
  const recognition=useRef<SpeechRecognitionLike|null>(null); const chars=brief.trim().length;
  const steps=useMemo(()=>initialSteps.map((step,index)=>[...step.slice(0,3),mission&&index===0?"ready":step[3]]),[mission]);
  function toggleVoice(){
    if(listening){recognition.current?.stop();setListening(false);return}
    const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!Speech){alert("Voice input is not available in this browser. Use Chrome or Edge, or type the directive.");return}
    const instance=new Speech(); instance.lang="ja-JP";instance.interimResults=false;instance.continuous=true;
    instance.onresult=(event)=>{const latest=event.results[event.results.length-1]?.[0]?.transcript??"";setBrief(current=>`${current}${current?" ":""}${latest}`)};
    instance.onend=()=>setListening(false);instance.onerror=()=>setListening(false);recognition.current=instance;instance.start();setListening(true);
  }
  function createMission(){if(!brief.trim())return;setMission(true)}
  return <main className={`app-shell ${collapsed?"sidebar-collapsed":""}`}>
    <aside className="rail"><header><a className="mark" href="#top" aria-label="Guildless home"><img src="/guildless-icon.png" alt=""/></a><b>Guildless</b><button className="collapse" onClick={()=>setCollapsed(value=>!value)} aria-label={collapsed?"Expand sidebar":"Collapse sidebar"}>{collapsed?"›":"‹"}</button></header><div className="rail-nav">{["Command","Missions","Evidence","Agents"].map((item,index)=><button key={item} className={active===item?"selected":""} onClick={()=>setActive(item)} aria-label={item}><span>{["＋","▣","◎","◇"][index]}</span><small>{item}</small></button>)}</div><section className="recents"><strong>Recent missions</strong>{["iOS game vertical slice","Guildless control plane","Landing page research","Voice operator prototype"].map((item,index)=><button key={item} className={index===0&&mission?"current":""} onClick={()=>{setActive("Missions");setBrief(item)}}><i/>{item}</button>)}</section><footer className="rail-footer"><a className="repo" href="https://github.com/kokoaru-ltd/guildless/archive/refs/heads/agent/cross-model-production-policy.zip" aria-label="Download source">↓</a><div><b>Local workspace</b><small>Owner mode</small></div></footer></aside>
    <section className="workspace" id="top"><header className="topbar"><div><b>GUILDLESS</b><span>/</span><strong>Operator console</strong></div><div className="runtime"><i/> LOCAL RUNTIME <span>CONTROLLED</span></div></header>
      <div className="command-stage"><div className="eyebrow"><span>{active.toUpperCase()}</span><em>MISSION 0001</em></div><h1>{active==="Command"?<>Describe the outcome.<br/><span>The company builds the rest.</span></>:<>{active}<br/><span>One company, fully traceable.</span></>}</h1><p className="lead">One instruction becomes researched, divided, independently reviewed work. No model approves its own output.</p>
        <div className={`voice-composer ${listening?"is-listening":""}`}><textarea value={brief} onChange={event=>{setBrief(event.target.value);setMission(false)}} placeholder="例：iOS向けの3Dゲームを、企画・素材・実装・テスト・ストア公開まで作って。競合と評価済みOSSを先に調査して。" aria-label="Owner directive"/><div className="composer-bar"><button className="mic" onClick={toggleVoice} aria-pressed={listening}><i/>{listening?"Listening… tap to stop":"Speak directive"}</button><span>{chars?`${chars} characters`:"Japanese / English"}</span><button className="dispatch" disabled={!brief.trim()} onClick={createMission}>{mission?"Mission created":"Create verified mission"}<b>↗</b></button></div></div>
        <div className={`workgraph ${mission?"has-mission":""}`}><div className="section-head"><div><small>SEPARATION OF DUTIES</small><h2>{mission?"Mission compiled. Research is ready to run.":"The work contract is created before execution."}</h2></div><span>{mission?"1 READY · 5 LOCKED":"AWAITING DIRECTIVE"}</span></div><div className="steps">{steps.map((step,index)=><div className={`step ${step[3]}`} key={step[1]}><b>{step[0]}</b><div><strong>{step[1]}</strong><small>{step[2]}</small></div><em>{step[3]}</em>{index<steps.length-1&&<i/>}</div>)}</div>{mission&&<div className="truth-note"><b>Execution has not started.</b> This console created the governed work graph only. External research and model calls require their configured credentials.</div>}</div>
      </div></section>
    <aside className="inspector"><header><div><small>COMPANY STATUS</small><strong>1 owner / 5 engines</strong></div><button aria-label="Settings">•••</button></header><section className="health"><div className="score"><strong>20</strong><span>%<small>execution ready</small></span></div><div className="bar"><i/></div><p>Planning policy is live. Autonomous workers and durable scheduling are not complete.</p></section><section className="engine-stack"><div className="aside-title"><small>CAPABILITY ROUTER</small><span>LIVE TRUTH</span></div>{roles.map(engine=><div className="engine" key={engine.name}><i className={engine.tone}/><div><b>{engine.name}</b><small>{engine.role}</small></div><em>{engine.state}</em></div>)}</section><section className="release"><div className="aside-title"><small>RELEASE AUTHORITY</small><span>0 / 4</span></div>{["Build reproduced","Tests pass","Independent review","Rollback verified"].map(item=><div key={item}><i/> {item}</div>)}<button disabled>Release locked</button></section><footer><div><b>Desktop source</b><small>Run on your machine. Bring your own model accounts.</small></div><a href="https://github.com/kokoaru-ltd/guildless/archive/refs/heads/agent/cross-model-production-policy.zip">Download ↓</a><a className="github" href="https://github.com/kokoaru-ltd/guildless">View GitHub ↗</a></footer></aside>
  </main>
}
