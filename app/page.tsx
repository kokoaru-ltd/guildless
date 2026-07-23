"use client";

import { useEffect, useRef, useState } from "react";

type Locale = "en" | "ja";
type Section = "home" | "task" | "all" | "agents" | "connectors" | "settings";
type Worktab = "Changes" | "Evidence" | "Preview" | "Files" | "Activity" | "MCP";
type ModelId = "auto" | "codex" | "claude" | "kimi" | "grok" | "gemini";
type SpeechLike = { lang:string; continuous:boolean; interimResults:boolean; start():void; stop():void; onresult:((e:{results:ArrayLike<{0:{transcript:string}}>})=>void)|null; onend:(()=>void)|null; onerror:(()=>void)|null };
declare global { interface Window { SpeechRecognition?:new()=>SpeechLike; webkitSpeechRecognition?:new()=>SpeechLike } }

const ui = {
  en: { newTask:"New task", search:"Search", tasks:"Missions", agents:"Agents", connectors:"Connectors", projects:"PROJECTS", recent:"TASKS", title:"Build a playable iOS game with an AI company", done:"Completed", owner:"You", input:"Assign a mission, or type / for more", send:"Send", work:"Workstation", language:"日本語", deliverable:"Final deliverable", connected:"Connected", permissions:"Permissions", used:"Used in this mission" },
  ja: { newTask:"新しいタスク", search:"検索", tasks:"ミッション", agents:"エージェント", connectors:"接続", projects:"プロジェクト", recent:"タスク", title:"AI企業で遊べるiOSゲームを開発する", done:"完了", owner:"あなた", input:"ミッションを割り当てるか、/ で機能を表示", send:"送信", work:"ワークステーション", language:"English", deliverable:"最終成果物", connected:"接続済み", permissions:"権限", used:"このミッションで使用" },
};

const steps = [
  { agent:"Kimi", icon:"K", title:"Game concept and operating contract", body:"Defined the 60-second loop, combo economy, health, difficulty curve, and five failure modes.", state:"done" },
  { agent:"Claude", icon:"C", title:"Expo implementation", body:"Built the playable React Native game, touch controls, haptics, pause lifecycle, and deterministic rule module.", state:"done" },
  { agent:"Codex", icon:"⌘", title:"Independent review", body:"Rejected the build: timer drift and unsafe spawn geometry could break fairness.", state:"failed" },
  { agent:"Claude", icon:"C", title:"Corrective implementation", body:"Separated wall-clock time from physics and added adversarial spawn tests.", state:"done" },
  { agent:"Codex", icon:"⌘", title:"Final release review", body:"All blockers closed. 34 tests passed and the release gate was approved.", state:"passed" },
];

const connectors = [
  { icon:"GH", name:"GitHub", detail:"Source, commits, releases", access:"Read + Write", state:"connected", used:true },
  { icon:"FS", name:"Local workspace", detail:"Files and CLI tools", access:"Ask on changes", state:"connected", used:true },
  { icon:"DB", name:"SQLite ledger", detail:"Immutable mission events", access:"Append only", state:"connected", used:true },
  { icon:"WB", name:"Browser", detail:"Preview and visual QA", access:"Local URLs", state:"connected", used:true },
  { icon:"KM", name:"Kimi Desktop", detail:"Product and operations model", access:"Local account", state:"connected", used:true },
  { icon:"X", name:"Grok / xAI", detail:"X and GitHub scouting", access:"API or OAuth", state:"required", used:false },
];

const team = [
  ["Kimi","Product strategy","Connected","K"],["Claude","Implementation","Connected","C"],["Codex","Architecture & review","Connected","⌘"],["Node","Deterministic QA","Local","N"],["Grok","Research","Needs connection","X"],
];

const evidence = [
  {source:"User reviews",kind:"COMMUNITY",score:61,title:"Autonomy is valued; reliability is not trusted",detail:"Public Manus reviews repeatedly praise breadth and voice-driven execution while reporting failed long tasks, fragile app builds, support delays, and unpredictable credits.",signal:"Mixed"},
  {source:"SWE-bench",kind:"BENCHMARK",score:92,title:"Code must pass repository-level tests",detail:"Real GitHub issues and executable tests are stronger evidence than a model declaring its own code complete.",signal:"Strong"},
  {source:"GitHub issues",kind:"FIELD DATA",score:74,title:"Skills and integrations fail in production",detail:"Open issue trackers expose loading failures, context problems, regressions, and operational gaps hidden by demos.",signal:"Useful"},
  {source:"Independent AI review",kind:"CRITIC",score:87,title:"Builder and reviewer must be separated",detail:"A second model evaluates the artifact against a fixed rubric and cannot silently change acceptance criteria.",signal:"Strong"},
];

const experts = [
  {name:"Conversion Director",icon:"CD",decision:"Move proof above the first CTA",why:"Review evidence shows trust and reliability dominate purchase objections.",status:"APPROVE"},
  {name:"Product Designer",icon:"PD",decision:"Keep one primary action per viewport",why:"Reduces choice competition and makes the intended path measurable.",status:"APPROVE"},
  {name:"Staff Engineer",icon:"SE",decision:"Reject one-shot generated architecture",why:"Requires typed boundaries, tests, observability, rollback, and ownership.",status:"REVISE"},
  {name:"Security Lead",icon:"SL",decision:"Sandbox discovered Skills by default",why:"External instructions and model output are untrusted inputs.",status:"BLOCK"},
];

function MiniGame() {
  return <div className="manus-device">
    <div className="device-island"/><div className="neon-screen">
      <header><div><span>♥ ♥ ♥</span><b>×4</b></div><strong>42</strong><div><small>SCORE</small><b>380</b></div></header>
      <div className="timer-track"><i/></div><div className="playfield">
        <i className="gem g1"/><i className="gem g2"/><i className="gem g3"/>
        <i className="hazard h1"/><i className="hazard h2"/><i className="hazard h3"/>
        <i className="drifter"/><i className="touch-ring"/>
      </div><footer><b>NEON DRIFT</b><span>60 SEC RUN</span></footer>
    </div>
  </div>;
}

export default function Home() {
  const [locale,setLocale]=useState<Locale>("en");
  const [section,setSection]=useState<Section>("task");
  const [tab,setTab]=useState<Worktab>("Changes");
  const [draft,setDraft]=useState("");
  const [messages,setMessages]=useState<string[]>([]);
  const [listening,setListening]=useState(false);
  const [signedIn,setSignedIn]=useState(false);
  const [authOpen,setAuthOpen]=useState(false);
  const [modelOpen,setModelOpen]=useState(false);
  const [activeModel,setActiveModel]=useState<ModelId>("auto");
  const [searchOpen,setSearchOpen]=useState(false);
  const [searchQuery,setSearchQuery]=useState("");
  const [notice,setNotice]=useState("");
  const [evidenceResult,setEvidenceResult]=useState<{confidence:number;releaseGate:string;warnings:string[]}|null>(null);
  const [connectorStates,setConnectorStates]=useState<Record<string,boolean>>(()=>Object.fromEntries(connectors.map(c=>[c.name,c.state==="connected"])));
  const speech=useRef<SpeechLike|null>(null);
  const t=ui[locale];
  useEffect(()=>{const saved=localStorage.getItem("guildless.locale");if(saved==="ja"||saved==="en")setLocale(saved);setSignedIn(localStorage.getItem("guildless.auth")==="1")},[]);
  useEffect(()=>()=>speech.current?.stop(),[]);
  useEffect(()=>{
    const candidates=[
      {url:"https://www.reddit.com/r/ManusOfficial/",channel:"community",taskFit:.82,demonstratedQuality:.58,reproducibility:.35,maintenance:.65,manipulationRisk:.25,updatedAt:"2026-07-01",metrics:{views:180000}},
      {url:"https://arxiv.org/abs/2310.06770",channel:"benchmark",taskFit:.93,demonstratedQuality:.94,reproducibility:1,maintenance:.8,updatedAt:"2025-08-01",metrics:{downloads:800000}},
      {url:"https://github.com/OpenHands/OpenHands/issues",channel:"github",taskFit:.85,demonstratedQuality:.72,reproducibility:.78,maintenance:.9,updatedAt:"2026-07-20",metrics:{stars:75000}},
      {url:"https://github.com/langchain-ai/langgraph",channel:"implementation",taskFit:.8,demonstratedQuality:.82,reproducibility:.85,maintenance:.95,updatedAt:"2026-07-10",metrics:{stars:37000},license:"MIT"},
    ];
    fetch("/api/evidence",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({question:"Can this mission be released with professional quality?",candidates})})
      .then(r=>r.ok?r.json():Promise.reject()).then(setEvidenceResult).catch(()=>setEvidenceResult(null));
  },[]);
  const switchLocale=()=>{const n=locale==="en"?"ja":"en";setLocale(n);localStorage.setItem("guildless.locale",n)};
  const submit=()=>{if(!draft.trim())return;setMessages(v=>[...v,draft.trim()]);setDraft("");setSection("task")};
  const signIn=()=>{localStorage.setItem("guildless.auth","1");setSignedIn(true);setAuthOpen(false);setNotice("Workspace connected")};
  const signOut=()=>{localStorage.removeItem("guildless.auth");setSignedIn(false);setAuthOpen(false);setSection("home")};
  const flash=(message:string)=>{setNotice(message);window.setTimeout(()=>setNotice(""),1800)};
  const voice=()=>{if(listening){speech.current?.stop();setListening(false);return}const C=window.SpeechRecognition||window.webkitSpeechRecognition;if(!C)return alert("Voice input requires Chrome or Edge.");const r=new C();r.lang=locale==="ja"?"ja-JP":"en-US";r.continuous=false;r.interimResults=false;r.onresult=e=>setDraft(e.results[e.results.length-1]?.[0]?.transcript??"");r.onend=()=>setListening(false);r.onerror=()=>setListening(false);speech.current=r;r.start();setListening(true)};

  return <main className="manus-shell">
    <aside className="manus-sidebar">
      <header><div className="gl-orb">GL</div><strong>GUILDLESS</strong><button aria-label="Collapse sidebar" onClick={()=>flash("Sidebar control ready")}>⌄</button></header>
      <button className="new-task" onClick={()=>{setSection("task");setDraft("");setMessages([])}}><span>＋</span>{t.newTask}</button>
      <nav>
        <button onClick={()=>setSearchOpen(true)}><i>⌕</i>{t.search}</button>
        <button className={section==="all"?"active":""} onClick={()=>setSection("all")}><i>⌾</i>{t.tasks}</button>
        <button className={section==="agents"?"active":""} onClick={()=>setSection("agents")}><i>⌘</i>{t.agents}</button>
        <button className={section==="connectors"?"active":""} onClick={()=>setSection("connectors")}><i>◫</i>{t.connectors}</button>
      </nav>
      <div className="side-group"><small>{t.projects}</small><button className="project"><i className="project-dot"/>GUILDLESS <span>•••</span></button></div>
      <div className="side-group history"><small>{t.recent}</small>
        <button className={section==="task"?"selected":""} onClick={()=>setSection("task")}><i>◉</i><span>{t.title}<small>{t.done} · 14:09</small></span></button>
        <button onClick={()=>{setSection("task");setTab("Activity")}}><i>›_</i><span>Hello world CLI<small>{t.done} · 13:05</small></span></button>
      </div>
      <footer><button className="account-button" onClick={()=>setSection("settings")}><div className="avatar">{signedIn?"KK":"?"}</div><span><b>{signedIn?"kokoaru-ltd":"Account & settings"}</b><small>{signedIn?"Owner workspace":"Language · login · providers"}</small></span><em>⚙</em></button></footer>
    </aside>

    {section==="home"&&<section className="manus-home">
      <header className="home-top"><div className="model-anchor"><button className="model-selector" onClick={()=>setModelOpen(v=>!v)}>{activeModel==="auto"?"GUILDLESS AUTO":activeModel.toUpperCase()} <span>⌄</span></button>{modelOpen&&<ModelMenu value={activeModel} onChange={m=>{setActiveModel(m);setModelOpen(false);flash(m==="auto"?"Auto-routing enabled":`${m} selected`)}}/>}</div><div><button className="credit" onClick={()=>setSection("settings")}>⚙ Settings</button></div></header>
      <div className="home-center">
        <div className="plan-row"><span>LOCAL PLAN</span><button onClick={()=>setSection("agents")}>Connect more AI</button></div>
        <h1>{locale==="ja"?"何を実現しましょうか？":"What should your company build?"}</h1>
        <div className={`home-composer ${listening?"listening":""}`}>
          <textarea autoFocus value={draft} onChange={e=>setDraft(e.target.value)} placeholder={t.input} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();submit()}}}/>
          <div><button onClick={()=>flash("File attachment ready")}>＋</button><button title="Connectors" onClick={()=>setSection("connectors")}>⌘</button><button className="desktop-pill" onClick={()=>flash("Local workspace selected")}>▣ Local computer</button><span/><button title="Route models" onClick={()=>setModelOpen(v=>!v)}>◉</button><button onClick={voice} title="Voice input">{listening?"■":"♩"}</button><button className="home-send" disabled={!draft.trim()} onClick={submit}>↑</button></div>
        </div>
        <div className="quick-actions">
          <button onClick={()=>setDraft("Build a conversion landing page and verify it with another AI.")}>▱ Build website</button>
          <button onClick={()=>setDraft("Design and build a playable iOS game.")}>♙ Build a game</button>
          <button onClick={()=>setDraft("Research the best open-source tools on GitHub and X.")}>⌕ Deep research</button>
          <button onClick={()=>setSection("connectors")}>⌘ MCP</button>
          <button onClick={()=>setSection("all")}>••• More</button>
        </div>
      </div>
      <button className="home-feature" onClick={()=>setSection("task")}><span><b>See a company build a game</b><small>Kimi designs · Claude builds · Codex reviews</small></span><div className="feature-art"><i/><i/><i/></div></button>
    </section>}

    {section==="task" && <><section className="conversation">
      <header className="taskbar"><div><h1>{t.title}</h1><span><i/> {t.done} · 25m</span></div><div><button onClick={()=>flash("Share link copied")}>↗</button><button onClick={()=>setTab("Activity")}>•••</button></div></header>
      <div className="thread">
        <div className="owner-message"><div className="avatar small">KK</div><div><b>{t.owner}</b><p>Build a genuinely playable iOS game. Use Kimi for product judgment, Claude for implementation, and a separate AI for review. Do not call it done until the tests and independent gate pass.</p></div></div>
        <div className="agent-intro"><div className="gl-orb small">G</div><div><b>GUILDLESS</b><p>I’ll run this as a governed production mission. The implementer cannot approve its own work.</p></div></div>
        <div className="execution-card">
          <header><div><i className="pulse"/>Production run</div><span>5 stages · completed</span></header>
          {steps.map((step,index)=><article key={step.title} className={step.state}>
            <div className="agent-symbol">{step.icon}</div><div className="step-copy"><div><b>{step.title}</b><em>{step.agent}</em></div><p>{step.body}</p></div><i className="step-state">{step.state==="failed"?"!":"✓"}</i>
          </article>)}
        </div>
        <div className="expert-council">
          <header><div><i className="pulse"/>Expert council</div><span>4 specialists · 1 blocking objection</span></header>
          {experts.map(x=><article key={x.name}><i>{x.icon}</i><div><b>{x.name}</b><h4>{x.decision}</h4><p>{x.why}</p></div><em className={x.status.toLowerCase()}>{x.status}</em></article>)}
          <button onClick={()=>setTab("Evidence")}>Inspect evidence and disagreements →</button>
        </div>
        <div className="final-answer"><div className="gl-orb small">G</div><div><b>GUILDLESS</b><h2>NEON DRIFT is ready.</h2><p>A playable Expo game is packaged with deterministic rules, haptics, pause/resume, retry, safe spawns, and a true 60-second clock.</p>
          <div className="result-chips"><span>✓ 34 / 34 tests</span><span>✓ TypeScript</span><span>✓ Codex: PASS</span><span>↗ GitHub</span></div>
        </div></div>
        {messages.map((m,i)=><div className="owner-message new-message" key={i}><div className="avatar small">KK</div><div><b>{t.owner}</b><p>{m}</p></div></div>)}
      </div>
      <div className="composer-wrap"><div className={`manus-composer ${listening?"listening":""}`}><textarea value={draft} onChange={e=>setDraft(e.target.value)} placeholder={t.input} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();submit()}}}/><div><button onClick={()=>flash("File attachment ready")}>＋</button><button className="model-pill" onClick={()=>{setSection("agents");flash("Choose a mission model")}}>{activeModel==="auto"?"Auto route":activeModel}⌄</button><span/><button onClick={voice} aria-label="Voice input">{listening?"■":"♩"}</button><button className="send" disabled={!draft.trim()} onClick={submit}>↑</button></div></div><small>Builders cannot approve their own release. Every handoff keeps evidence.</small></div>
    </section>

    <aside className="workstation">
      <header><b>ENVIRONMENT</b><div><button onClick={()=>setTab("Preview")}>↗</button><button onClick={()=>setTab("Changes")}>＋</button></div></header>
      <nav>{(["Changes","Evidence","Preview","Files","Activity","MCP"] as Worktab[]).map(x=><button className={tab===x?"active":""} onClick={()=>setTab(x)} key={x}>{x}{x==="MCP"&&<i>5</i>}</button>)}</nav>
      {tab==="Changes"&&<div className="changes-pane"><header><b>Changes</b><span>+13,326 <em>−112</em></span></header><div><button onClick={()=>setTab("Files")}>▣ <span><b>2 files changed</b><small>Review implementation</small></span><em>›</em></button><button onClick={()=>flash("Branch copied")}>⑂ <span><b>agent/cross-model-production-policy</b><small>Current branch</small></span><em>⌄</em></button><button onClick={()=>flash("Ready to commit")}>○ <span><b>Commit or push</b><small>Working tree verified</small></span><em>›</em></button></div><footer><b>Information sources</b><button onClick={()=>setTab("MCP")}>⌘ MCP connectors <span>5</span></button><button onClick={()=>setTab("Preview")}>◎ Browser preview <span>Local</span></button></footer></div>}
      {tab==="Evidence"&&<div className="evidence-pane"><header><div><small>EVIDENCE ENGINE · LIVE</small><b>Why this decision?</b></div><span>{evidenceResult?evidenceResult.releaseGate:"scoring…"}</span></header><div className="evidence-score"><strong>{evidenceResult?.confidence??"—"}</strong><div><b>Decision confidence</b><small>Calculated by the server from task fit, quality, reproducibility, maintenance, adoption, freshness, and manipulation risk.</small></div></div>{evidenceResult?.warnings?.length?<div className="evidence-warning">Release blocked: {evidenceResult.warnings.join(" · ")}</div>:null}{evidence.map(x=><article key={x.title}><header><span>{x.kind}</span><em>{x.signal}</em></header><h4>{x.title}</h4><p>{x.detail}</p><footer><span>{x.source}</span><b>{x.score}/100</b></footer></article>)}</div>}
      {tab==="Preview"&&<div className="preview-pane"><div className="preview-toolbar"><span><i/> Expo · iOS</span><button>↻</button></div><div className="preview-canvas"><MiniGame/></div><div className="deliverable"><header><span><i>✓</i><b>{t.deliverable}</b></span><em>VERIFIED</em></header><h3>NEON DRIFT</h3><p>Playable one-thumb arcade game · Expo SDK 54</p><div><span>34 tests</span><span>Commit 35f1f0d</span></div><button>Open source ↗</button></div></div>}
      {tab==="Files"&&<div className="files-pane"><header><span>guildless / apps / mobile</span></header>{[["App.tsx","24.9 KB","M"],["gameRules.js","10.5 KB","A"],["gameRules.test.mjs","20.2 KB","A"],["gameRules.d.ts","2.9 KB","A"],["package.json","704 B","M"]].map(f=><div key={f[0]}><i>⌘</i><span><b>{f[0]}</b><small>{f[1]}</small></span><em>{f[2]}</em></div>)}</div>}
      {tab==="Activity"&&<div className="activity-pane">{steps.map((s,i)=><article key={s.title}><time>{["13:44","13:56","13:59","14:06","14:09"][i]}</time><i className={s.state}/><div><b>{s.agent}</b><p>{s.title}</p></div></article>)}</div>}
      {tab==="MCP"&&<ConnectorPane t={t} states={connectorStates} onToggle={name=>setConnectorStates(s=>({...s,[name]:!s[name]}))}/>}
    </aside></>}

    {section==="all"&&<SimplePage eyebrow="MISSIONS" title="Work continues in parallel." body="Each mission keeps its own context, model handoffs, evidence, artifacts, and release authority."><div className="task-list"><button onClick={()=>setSection("task")}><i className="done">✓</i><span><b>{t.title}</b><small>5 agents · 34 tests · Codex PASS</small></span><em>Completed</em></button><button><i className="done">✓</i><span><b>Hello world CLI</b><small>Claude → Codex · 9 ledger events</small></span><em>Completed</em></button></div></SimplePage>}
    {section==="agents"&&<SimplePage eyebrow="MODEL ROUTING" title="One founder. A governed AI company." body="Auto mode assigns every stage. Manual mode lets you override it. The model that builds cannot approve its own release."><div className="routing-strip"><b>MISSION ROUTE</b><span>Kimi plans</span><i>→</i><span>Claude builds</span><i>→</i><span>Codex reviews</span><i>→</i><span>Kimi operates</span></div><div className="team-grid">{team.map(a=><article className={activeModel===a[0].toLowerCase()?"selected":""} key={a[0]}><i>{a[3]}</i><div><small>{a[2]}</small><h3>{a[0]}</h3><p>{a[1]}</p></div><button onClick={()=>{setActiveModel((a[0].toLowerCase()==="node"?"auto":a[0].toLowerCase()) as ModelId);flash(`${a[0]} selected`)}}>Use</button></article>)}</div></SimplePage>}
    {section==="connectors"&&<SimplePage eyebrow="MCP & CONNECTORS" title="Your tools become the company’s hands." body="Connect context and actions once. Missions use only the permissions you grant."><ConnectorPane t={t} states={connectorStates} onToggle={name=>setConnectorStates(s=>({...s,[name]:!s[name]}))}/></SimplePage>}
    {section==="settings"&&<SimplePage eyebrow="SETTINGS" title="Workspace settings" body="Language, account, providers, permissions, and local execution live here—not in the work canvas."><div className="settings-card"><section><div><b>Language</b><small>Interface language</small></div><div className="segmented"><button className={locale==="en"?"active":""} onClick={()=>{setLocale("en");localStorage.setItem("guildless.locale","en")}}>English</button><button className={locale==="ja"?"active":""} onClick={()=>{setLocale("ja");localStorage.setItem("guildless.locale","ja")}}>日本語</button></div></section><section><div><b>Account</b><small>Sync missions and evidence</small></div><button onClick={()=>setAuthOpen(true)}>{signedIn?"Manage account":"Sign in"}</button></section><section><div><b>Default routing</b><small>Choose manually or let GUILDLESS assign every stage</small></div><button onClick={()=>setSection("agents")}>{activeModel==="auto"?"Auto company":activeModel.toUpperCase()} ›</button></section><section><div><b>Browser preview</b><small>Open builds inside the environment rail</small></div><button onClick={()=>{setSection("task");setTab("Preview")}}>Open preview ›</button></section></div></SimplePage>}
    {searchOpen&&<div className="modal-backdrop" onClick={()=>setSearchOpen(false)}><div className="search-modal" onClick={e=>e.stopPropagation()}><input autoFocus value={searchQuery} onChange={e=>setSearchQuery(e.target.value)} placeholder="Search missions, files, agents…"/><div>{["Build a playable iOS game","Hello world CLI","Codex review","GitHub connector"].filter(x=>x.toLowerCase().includes(searchQuery.toLowerCase())).map(x=><button key={x} onClick={()=>{setSearchOpen(false);setSection(x.includes("GitHub")?"connectors":"task")}}>⌕ <span>{x}</span></button>)}</div></div></div>}
    {authOpen&&<div className="modal-backdrop" onClick={()=>setAuthOpen(false)}><div className="auth-modal" onClick={e=>e.stopPropagation()}><div className="gl-orb">GL</div><h2>{signedIn?"Workspace account":"Run your company from one account"}</h2><p>{signedIn?"kokoaru-ltd is connected to this local workspace.":"Sign in to sync missions, provider connections, evidence, and releases."}</p>{signedIn?<><button className="primary" onClick={()=>setAuthOpen(false)}>Manage workspace</button><button onClick={signOut}>Sign out</button></>:<><button className="primary" onClick={signIn}>Continue with GitHub</button><button onClick={signIn}>Continue in local mode</button></>}</div></div>}
    {notice&&<div className="toast">{notice}</div>}
  </main>;
}

function ConnectorPane({t,states,onToggle}:{t:(typeof ui)["en"];states:Record<string,boolean>;onToggle:(name:string)=>void}) {
  const count=Object.values(states).filter(Boolean).length;
  return <div className="connector-pane"><div className="connector-summary"><b>{count}</b><span>{t.connected}<small>{connectors.length-count} require setup</small></span><i>{count>=4?"Healthy":"Setup required"}</i></div>{connectors.map(c=><article key={c.name}><div className="connector-icon">{c.icon}</div><div><header><b>{c.name}</b>{c.used&&<em>{t.used}</em>}</header><p>{c.detail}</p><small>{t.permissions}: {c.access}</small></div><button className={states[c.name]?"connected":"required"} onClick={()=>onToggle(c.name)}>{states[c.name]?"● Connected":"Connect"}</button></article>)}</div>;
}
function ModelMenu({value,onChange}:{value:ModelId;onChange:(m:ModelId)=>void}) {
  const models:[ModelId,string,string][]=[["auto","Auto company","Routes every stage"],["codex","Codex","Architecture & review"],["claude","Claude","Implementation"],["kimi","Kimi","Product & operations"],["grok","Grok","Live research"],["gemini","Gemini","Multimodal & video"]];
  return <div className="model-menu">{models.map(([id,name,role])=><button className={value===id?"active":""} onClick={()=>onChange(id)} key={id}><i>{id==="auto"?"GL":name[0]}</i><span><b>{name}</b><small>{role}</small></span><em>{value===id?"✓":""}</em></button>)}</div>;
}
function SimplePage({eyebrow,title,body,children}:{eyebrow:string;title:string;body:string;children:React.ReactNode}) {
  return <section className="simple-page"><header><small>{eyebrow}</small><h1>{title}</h1><p>{body}</p></header>{children}</section>;
}
