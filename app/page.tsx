"use client";
import { useState } from "react";

const proofs=[
  ["GH","GitHub","motiondivision / motion","29.8k stars · MIT · active",94],
  ["PR","Product","motionsites.ai","Shipped motion references · inspected",86],
  ["X","X","Seedance 2.0 direction guide","5.1k views · 178 bookmarks · recent",81],
];
const engines=[
  ["Codex","Architecture + implementation","Ready","ok"],
  ["Claude / Fable","Implementation + review","Degraded","warn"],
  ["Kimi","Evidence analysis + operations","Degraded","warn"],
  ["Grok Build","X + GitHub scouting","Needs API key","off"],
  ["Node verifier","Deterministic acceptance","Ready","ok"],
];
const work=[
  ["Normalize owner intent","Codex","complete"],
  ["Collect human evidence","Grok + GitHub","ready"],
  ["Challenge design direction","Kimi","blocked"],
  ["Write acceptance tests","Independent model","queued"],
  ["Implement vertical slice","Claude / Fable","queued"],
  ["Verify and integrate","Node + Codex","queued"],
];

export default function Home(){
  const [phase,setPhase]=useState<"idle"|"scanning"|"ready">("idle");
  const [goal,setGoal]=useState("Turn a spoken product idea into a verified, production-ready vertical slice.");
  const scan=()=>{setPhase("scanning");window.setTimeout(()=>setPhase("ready"),900)};
  return <main className="shell">
    <header><a className="brand" href="#top"><b>G</b>GUILDLESS <small>LAB 01</small></a><nav><button className="active">Control plane</button><button>Evidence</button><button>Runs</button></nav><span className="online"><i/>LOCAL CONTROL PLANE</span></header>

    <section className="hero" id="top"><div><div className="kicker"><em>SELF-HOSTED MISSION</em> dogfood-control-plane-m0</div><h1>One owner.<br/><span>An evidence-driven company.</span></h1><p>State the outcome. GUILDLESS researches what humans already value, assigns the best engine to each artifact, and refuses to ship without independent proof.</p></div><aside className="truth"><small>CURRENT TRUTH</small><strong>Planning works.<br/>Autonomous execution does not—yet.</strong><p>Mission compilation, separation of duties, evidence scoring, adapters, and release policy are live. Durable scheduling and end-to-end workers remain unbuilt.</p><div className="meter"><i/></div><footer><span>9 deterministic tests passing</span><b>CONTROL PLANE 18%</b></footer></aside></section>

    <section className="directive"><div className="title"><div><small>OWNER DIRECTIVE</small><h2>What should the company accomplish?</h2></div><span>● Voice capture designed · not connected</span></div><div className="composer"><textarea aria-label="Mission objective" value={goal} onChange={e=>setGoal(e.target.value)}/><footer><div><small>BUDGET CEILING</small><b>¥3,000</b></div><div><small>AUTHORITY</small><b>Sandbox only</b></div><button onClick={scan} disabled={phase==="scanning"}>{phase==="idle"?"Research before planning":phase==="scanning"?"Scanning evidence…":"Evidence ready"}<b>→</b></button></footer></div></section>

    <section className="grid">
      <article className="panel evidence"><div className="title"><div><small>EVIDENCE ENGINE</small><h2>Human proof, before AI judgment</h2></div><span className={`pill ${phase}`}>{phase==="idle"?"NOT RUN":phase==="scanning"?"SCANNING":"DECISION READY"}</span></div><p className="intro">Popularity discovers candidates. Task fit, demonstrated quality, reproducibility, maintenance, and license decide what survives.</p>{phase==="ready"?<div className="proofs">{proofs.map((p,i)=><div className="proof" key={String(p[2])} style={{animationDelay:`${i*50}ms`}}><b className={`source s${i}`}>{p[0]}</b><div><small>{p[1]}</small><strong>{p[2]}</strong><span>{p[3]}</span></div><em>{p[4]}<small>/100</small></em></div>)}</div>:<div className={`empty ${phase}`}><i/><span>{phase==="scanning"?"Inspecting sources and licenses":"Run research to build an Evidence Pack"}</span></div>}<footer className="weights"><span>FIT <b>30%</b></span><span>QUALITY <b>25%</b></span><span>REPRODUCIBLE <b>15%</b></span><span>ADOPTION <b>10%</b></span></footer></article>

      <article className="panel engines"><div className="title"><div><small>ENGINE HEALTH</small><h2>Capability, not loyalty</h2></div><button aria-label="Refresh">↻</button></div><div className="engine-list">{engines.map(e=><div className="engine" key={e[0]}><i className={e[3]}/><div><strong>{e[0]}</strong><span>{e[1]}</span></div><em>{e[2]}</em></div>)}</div><aside><b>!</b> Installed is not healthy. Claude and Kimi connected but timed out during unattended trials.</aside></article>

      <article className="panel graph"><div className="title"><div><small>VERIFIED WORK GRAPH</small><h2>Nothing completes by self-report</h2></div><span>GRAPH v1</span></div><div>{work.map((w,i)=><div className={`task ${w[2]}`} key={w[0]}><b>{w[2]==="complete"?"✓":i+1}</b><div><strong>{w[0]}</strong><small>{w[1]}</small></div><em>{w[2]}</em></div>)}</div></article>

      <article className="panel gate"><small>RELEASE GATE</small><h2>Blocked by evidence,<br/>not optimism.</h2><strong className="count">0<span>/ 4</span></strong><ul><li>Reproducible build</li><li>Deterministic tests</li><li>Independent review</li><li>Rollback rehearsal</li></ul><button disabled>Release unavailable</button></article>
    </section>
  </main>
}
