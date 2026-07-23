"use client";

import { useEffect, useRef, useState } from "react";

type Locale = "en" | "ja";
type Section = "task" | "all" | "agents" | "connectors";
type Worktab = "Preview" | "Files" | "Activity" | "MCP";
type SpeechLike = { lang:string; continuous:boolean; interimResults:boolean; start():void; stop():void; onresult:((e:{results:ArrayLike<{0:{transcript:string}}>})=>void)|null; onend:(()=>void)|null; onerror:(()=>void)|null };
declare global { interface Window { SpeechRecognition?:new()=>SpeechLike; webkitSpeechRecognition?:new()=>SpeechLike } }

const ui = {
  en: { newTask:"New task", search:"Search", tasks:"All tasks", agents:"Agents", connectors:"Connectors", projects:"PROJECTS", recent:"RECENT", title:"Build a playable iOS game with an AI company", done:"Completed", owner:"You", input:"Ask GUILDLESS to build, change, or investigate anything", send:"Send", work:"Workstation", language:"日本語", deliverable:"Final deliverable", connected:"Connected", permissions:"Permissions", used:"Used in this mission" },
  ja: { newTask:"新しいタスク", search:"検索", tasks:"すべてのタスク", agents:"AIエージェント", connectors:"接続", projects:"プロジェクト", recent:"最近", title:"AI企業で遊べるiOSゲームを開発する", done:"完了", owner:"あなた", input:"GUILDLESSに作成・変更・調査を指示する", send:"送信", work:"ワークステーション", language:"English", deliverable:"最終成果物", connected:"接続済み", permissions:"権限", used:"このミッションで使用" },
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
  const [tab,setTab]=useState<Worktab>("Preview");
  const [draft,setDraft]=useState("");
  const [messages,setMessages]=useState<string[]>([]);
  const [listening,setListening]=useState(false);
  const speech=useRef<SpeechLike|null>(null);
  const t=ui[locale];
  useEffect(()=>{const saved=localStorage.getItem("guildless.locale");if(saved==="ja"||saved==="en")setLocale(saved)},[]);
  useEffect(()=>()=>speech.current?.stop(),[]);
  const switchLocale=()=>{const n=locale==="en"?"ja":"en";setLocale(n);localStorage.setItem("guildless.locale",n)};
  const submit=()=>{if(!draft.trim())return;setMessages(v=>[...v,draft.trim()]);setDraft("")};
  const voice=()=>{if(listening){speech.current?.stop();setListening(false);return}const C=window.SpeechRecognition||window.webkitSpeechRecognition;if(!C)return alert("Voice input requires Chrome or Edge.");const r=new C();r.lang=locale==="ja"?"ja-JP":"en-US";r.continuous=false;r.interimResults=false;r.onresult=e=>setDraft(e.results[e.results.length-1]?.[0]?.transcript??"");r.onend=()=>setListening(false);r.onerror=()=>setListening(false);speech.current=r;r.start();setListening(true)};

  return <main className="manus-shell">
    <aside className="manus-sidebar">
      <header><div className="gl-orb">G</div><strong>GUILDLESS</strong><button>⌄</button></header>
      <button className="new-task" onClick={()=>setSection("task")}><span>＋</span>{t.newTask}<kbd>⌘ K</kbd></button>
      <nav>
        <button><i>⌕</i>{t.search}</button>
        <button className={section==="all"?"active":""} onClick={()=>setSection("all")}><i>▤</i>{t.tasks}<em>2</em></button>
        <button className={section==="agents"?"active":""} onClick={()=>setSection("agents")}><i>◇</i>{t.agents}</button>
        <button className={section==="connectors"?"active":""} onClick={()=>setSection("connectors")}><i>⌁</i>{t.connectors}</button>
      </nav>
      <div className="side-group"><small>{t.projects}</small><button className="project"><i className="project-dot"/>GUILDLESS <span>•••</span></button></div>
      <div className="side-group history"><small>{t.recent}</small>
        <button className={section==="task"?"selected":""} onClick={()=>setSection("task")}><i>◉</i><span>{t.title}<small>{t.done} · 14:09</small></span></button>
        <button><i>⌘</i><span>Hello world CLI<small>{t.done} · 13:05</small></span></button>
      </div>
      <footer><div className="avatar">KK</div><span><b>kokoaru-ltd</b><small>Owner workspace</small></span><button>•••</button></footer>
    </aside>

    {section==="task" && <><section className="conversation">
      <header className="taskbar"><div><h1>{t.title}</h1><span><i/> {t.done} · 25m</span></div><div><button>↗</button><button>•••</button></div></header>
      <div className="thread">
        <div className="owner-message"><div className="avatar small">KK</div><div><b>{t.owner}</b><p>Build a genuinely playable iOS game. Use Kimi for product judgment, Claude for implementation, and a separate AI for review. Do not call it done until the tests and independent gate pass.</p></div></div>
        <div className="agent-intro"><div className="gl-orb small">G</div><div><b>GUILDLESS</b><p>I’ll run this as a governed production mission. The implementer cannot approve its own work.</p></div></div>
        <div className="execution-card">
          <header><div><i className="pulse"/>Production run</div><span>5 stages · completed</span></header>
          {steps.map((step,index)=><article key={step.title} className={step.state}>
            <div className="agent-symbol">{step.icon}</div><div className="step-copy"><div><b>{step.title}</b><em>{step.agent}</em></div><p>{step.body}</p></div><i className="step-state">{step.state==="failed"?"!":"✓"}</i>
          </article>)}
        </div>
        <div className="final-answer"><div className="gl-orb small">G</div><div><b>GUILDLESS</b><h2>NEON DRIFT is ready.</h2><p>A playable Expo game is packaged with deterministic rules, haptics, pause/resume, retry, safe spawns, and a true 60-second clock.</p>
          <div className="result-chips"><span>✓ 34 / 34 tests</span><span>✓ TypeScript</span><span>✓ Codex: PASS</span><span>↗ GitHub</span></div>
        </div></div>
        {messages.map((m,i)=><div className="owner-message new-message" key={i}><div className="avatar small">KK</div><div><b>{t.owner}</b><p>{m}</p></div></div>)}
      </div>
      <div className="composer-wrap"><div className={`manus-composer ${listening?"listening":""}`}><textarea value={draft} onChange={e=>setDraft(e.target.value)} placeholder={t.input} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();submit()}}}/><div><button>＋</button><button className="model-pill">Auto route⌄</button><span/><button onClick={voice} aria-label="Voice input">{listening?"■":"♩"}</button><button className="send" disabled={!draft.trim()} onClick={submit}>↑</button></div></div><small>GUILDLESS can make mistakes. Every release still requires evidence.</small></div>
    </section>

    <aside className="workstation">
      <header><b>{t.work}</b><div><button>↗</button><button>×</button></div></header>
      <nav>{(["Preview","Files","Activity","MCP"] as Worktab[]).map(x=><button className={tab===x?"active":""} onClick={()=>setTab(x)} key={x}>{x}{x==="MCP"&&<i>5</i>}</button>)}</nav>
      {tab==="Preview"&&<div className="preview-pane"><div className="preview-toolbar"><span><i/> Expo · iOS</span><button>↻</button></div><div className="preview-canvas"><MiniGame/></div><div className="deliverable"><header><span><i>✓</i><b>{t.deliverable}</b></span><em>VERIFIED</em></header><h3>NEON DRIFT</h3><p>Playable one-thumb arcade game · Expo SDK 54</p><div><span>34 tests</span><span>Commit 35f1f0d</span></div><button>Open source ↗</button></div></div>}
      {tab==="Files"&&<div className="files-pane"><header><span>guildless / apps / mobile</span></header>{[["App.tsx","24.9 KB","M"],["gameRules.js","10.5 KB","A"],["gameRules.test.mjs","20.2 KB","A"],["gameRules.d.ts","2.9 KB","A"],["package.json","704 B","M"]].map(f=><div key={f[0]}><i>⌘</i><span><b>{f[0]}</b><small>{f[1]}</small></span><em>{f[2]}</em></div>)}</div>}
      {tab==="Activity"&&<div className="activity-pane">{steps.map((s,i)=><article key={s.title}><time>{["13:44","13:56","13:59","14:06","14:09"][i]}</time><i className={s.state}/><div><b>{s.agent}</b><p>{s.title}</p></div></article>)}</div>}
      {tab==="MCP"&&<ConnectorPane t={t}/>}
    </aside></>}

    {section==="all"&&<SimplePage eyebrow="MISSIONS" title="Work continues in parallel." body="Each mission keeps its own context, model handoffs, evidence, artifacts, and release authority."><div className="task-list"><button onClick={()=>setSection("task")}><i className="done">✓</i><span><b>{t.title}</b><small>5 agents · 34 tests · Codex PASS</small></span><em>Completed</em></button><button><i className="done">✓</i><span><b>Hello world CLI</b><small>Claude → Codex · 9 ledger events</small></span><em>Completed</em></button></div></SimplePage>}
    {section==="agents"&&<SimplePage eyebrow="MODEL ROUTING" title="A company, not a model picker." body="Every model gets a bounded job. Review and implementation are deliberately separated."><div className="team-grid">{team.map(a=><article key={a[0]}><i>{a[3]}</i><div><small>{a[2]}</small><h3>{a[0]}</h3><p>{a[1]}</p></div><button>•••</button></article>)}</div></SimplePage>}
    {section==="connectors"&&<SimplePage eyebrow="MCP & CONNECTORS" title="Your tools become the company’s hands." body="Connect context and actions once. Missions use only the permissions you grant."><ConnectorPane t={t}/></SimplePage>}
    <button className="locale-switch" onClick={switchLocale}>{t.language}</button>
  </main>;
}

function ConnectorPane({t}:{t:(typeof ui)["en"]}) {
  return <div className="connector-pane"><div className="connector-summary"><b>5</b><span>{t.connected}<small>1 requires setup</small></span><i>Healthy</i></div>{connectors.map(c=><article key={c.name}><div className="connector-icon">{c.icon}</div><div><header><b>{c.name}</b>{c.used&&<em>{t.used}</em>}</header><p>{c.detail}</p><small>{t.permissions}: {c.access}</small></div><span className={c.state}>{c.state==="connected"?"● Connected":"Connect"}</span></article>)}</div>;
}
function SimplePage({eyebrow,title,body,children}:{eyebrow:string;title:string;body:string;children:React.ReactNode}) {
  return <section className="simple-page"><header><small>{eyebrow}</small><h1>{title}</h1><p>{body}</p></header>{children}</section>;
}
