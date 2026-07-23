"use client";

import { useEffect, useState } from "react";

type Locale = "en" | "ja";
type View = "Overview" | "Missions" | "Evidence" | "Agents";

const labels = {
  en: {
    Overview: "Overview", Missions: "Missions", Evidence: "Evidence", Agents: "Agents",
    recent: "RECENT MISSIONS", live: "LOCAL RUNTIME", owner: "Owner mode",
    built: "Built by an AI company.", proof: "Every handoff is visible.",
    lead: "A playable iOS-first arcade game planned by Kimi, built by Claude, rejected twice by Codex, corrected, tested, and approved.",
    open: "Open mission", play: "Playable build", verified: "VERIFIED",
    timeline: "Production timeline", artifacts: "Shipped artifacts", gate: "Release gate",
  },
  ja: {
    Overview: "概要", Missions: "ミッション", Evidence: "証拠", Agents: "AIエージェント",
    recent: "最近のミッション", live: "ローカル実行中", owner: "オーナーモード",
    built: "AI企業が開発した。", proof: "全ての受け渡しを可視化。",
    lead: "Kimiが企画し、Claudeが実装。Codexが2回却下し、修正・テストを経て承認した、実際に遊べるiOS向けゲームです。",
    open: "ミッションを開く", play: "プレイ可能ビルド", verified: "検証済み",
    timeline: "開発タイムライン", artifacts: "完成した成果物", gate: "リリース判定",
  },
};

const agents = [
  { name: "Kimi", glyph: "K", role: "Game design & live-ops", status: "COMPLETE", color: "#c7a7ff" },
  { name: "Claude", glyph: "C", role: "React Native implementation", status: "COMPLETE", color: "#e9a477" },
  { name: "Codex", glyph: "⌘", role: "Independent adversarial review", status: "PASS", color: "#8eb7ff" },
  { name: "Node", glyph: "N", role: "Deterministic verification", status: "34 / 34", color: "#8bcf9b" },
  { name: "Grok", glyph: "X", role: "Research connector", status: "NOT CONNECTED", color: "#727780" },
];

const events = [
  { time: "13:44", actor: "Kimi", title: "Product contract approved", detail: "60-second loop, combo, health, difficulty curve, and failure modes.", result: "SPEC" },
  { time: "13:56", actor: "Claude", title: "Playable Expo build produced", detail: "Touch controls, haptics, pause/resume, game-over, and deterministic rules.", result: "BUILD" },
  { time: "13:59", actor: "Codex", title: "Review rejected", detail: "Timer drift and unsafe spawn geometry found. Release remained locked.", result: "FAIL", fail: true },
  { time: "14:06", actor: "Claude", title: "Corrective patch completed", detail: "Wall-clock separated from physics; adversarial spawn tests added.", result: "FIX" },
  { time: "14:08", actor: "Codex", title: "Second review rejected", detail: "One timer edge case and visual collision mismatch remained.", result: "FAIL", fail: true },
  { time: "14:09", actor: "Codex", title: "Independent gate passed", detail: "All review findings closed. 34 tests and TypeScript validation passed.", result: "PASS", pass: true },
];

function GamePreview() {
  return <div className="device-wrap">
    <div className="device">
      <div className="island" />
      <div className="game">
        <div className="game-hud">
          <div><span className="hearts">♥ ♥ ♥</span><b>×4</b></div>
          <strong>42</strong>
          <div className="score"><small>SCORE</small><b>380</b></div>
        </div>
        <div className="time-line"><i /></div>
        <div className="arena">
          <i className="shard s1" /><i className="shard s2" /><i className="shard s3" />
          <i className="mine m1"><b /></i><i className="mine m2"><b /></i><i className="mine m3"><b /></i>
          <i className="orbit" /><i className="player"><b /></i>
        </div>
        <div className="game-caption"><small>NEON DRIFT</small><span>60 SECOND RUN</span></div>
      </div>
    </div>
  </div>;
}

export default function Home() {
  const [locale, setLocale] = useState<Locale>("en");
  const [view, setView] = useState<View>("Overview");
  const [collapsed, setCollapsed] = useState(false);
  const t = labels[locale];

  useEffect(() => {
    const saved = localStorage.getItem("guildless.locale");
    if (saved === "ja" || saved === "en") setLocale(saved);
  }, []);

  const changeLocale = () => {
    const next = locale === "en" ? "ja" : "en";
    setLocale(next);
    localStorage.setItem("guildless.locale", next);
  };

  return <main className={`control-shell ${collapsed ? "is-collapsed" : ""}`}>
    <aside className="control-rail">
      <header>
        <div className="brand-mark">GL</div>
        <b>GUILDLESS</b>
        <button onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar">‹</button>
      </header>
      <nav>
        {(["Overview", "Missions", "Evidence", "Agents"] as View[]).map((item, index) =>
          <button key={item} className={view === item ? "active" : ""} onClick={() => setView(item)}>
            <i>{["⌂", "◫", "✓", "◇"][index]}</i><span>{t[item]}</span>
          </button>)}
      </nav>
      <section className="rail-recents">
        <small>{t.recent}</small>
        <button className="selected" onClick={() => setView("Overview")}><i /><span><b>NEON DRIFT</b><em>iOS game · completed</em></span></button>
        <button><i /><span><b>Hello CLI</b><em>Node · completed</em></span></button>
      </section>
      <footer><span>KK</span><div><b>kokoaru-ltd</b><small>{t.owner}</small></div></footer>
    </aside>

    <section className="control-main">
      <header className="control-topbar">
        <div><b>GUILDLESS</b><span>/</span><strong>{t[view]}</strong></div>
        <div><button onClick={changeLocale}>{locale === "en" ? "日本語" : "English"}</button><span className="runtime-dot"><i />{t.live}</span></div>
      </header>

      {view === "Overview" && <div className="mission-page">
        <section className="mission-hero">
          <div className="hero-copy">
            <div className="mission-state"><i /> MISSION COMPLETE <span>IOS-002</span></div>
            <h1>{t.built}<br/><span>{t.proof}</span></h1>
            <p>{t.lead}</p>
            <div className="hero-actions">
              <button onClick={() => setView("Evidence")}>{t.open} <b>→</b></button>
              <span><i /> {t.play}</span>
            </div>
            <dl className="hero-metrics">
              <div><dt>34 / 34</dt><dd>RULE TESTS</dd></div>
              <div><dt>2×</dt><dd>REVIEW REJECTIONS</dd></div>
              <div><dt>PASS</dt><dd>FINAL GATE</dd></div>
              <div><dt>35f1f0d</dt><dd>GIT COMMIT</dd></div>
            </dl>
          </div>
          <GamePreview />
        </section>
        <Pipeline locale={locale} />
      </div>}

      {view === "Missions" && <div className="section-page">
        <div className="section-title"><small>PRODUCTION PORTFOLIO</small><h1>2 missions shipped.</h1><p>The system records who built, who reviewed, and why the release was allowed.</p></div>
        <div className="mission-grid">
          <article className="mission-card feature" onClick={() => setView("Overview")}><div><span>IOS-002 · COMPLETED</span><h2>NEON DRIFT</h2><p>Playable 60-second arcade game for Expo and iOS.</p></div><strong>PASS</strong></article>
          <article className="mission-card"><div><span>CLI-001 · COMPLETED</span><h2>Hello CLI</h2><p>First autonomous Claude → Codex verified mission.</p></div><strong>PASS</strong></article>
        </div>
      </div>}

      {view === "Evidence" && <div className="section-page evidence-page">
        <div className="section-title"><small>IMMUTABLE PRODUCTION RECORD</small><h1>{t.timeline}</h1><p>Claims are tied to model output, review decisions, deterministic tests, and source artifacts.</p></div>
        <div className="evidence-layout">
          <div className="event-stream">{events.map((event, index) =>
            <article className={event.fail ? "failed" : event.pass ? "passed" : ""} key={event.time + event.actor}>
              <time>{event.time}</time><div className="event-node">{index + 1}</div>
              <div><header><span>{event.actor}</span><em>{event.result}</em></header><h3>{event.title}</h3><p>{event.detail}</p></div>
            </article>)}</div>
          <aside className="artifact-panel"><small>{t.artifacts}</small>
            <h2>NEON DRIFT</h2>
            {[["App.tsx","Playable application"],["gameRules.js","Deterministic rules"],["gameRules.test.mjs","34 passing tests"],["Expo bundle","iOS-compatible output"]].map(x=><div key={x[0]}><i>✓</i><span><b>{x[0]}</b><small>{x[1]}</small></span></div>)}
            <a href="https://github.com/kokoaru-ltd/guildless/tree/agent/cross-model-production-policy/apps/mobile">View source on GitHub →</a>
          </aside>
        </div>
      </div>}

      {view === "Agents" && <div className="section-page">
        <div className="section-title"><small>MODEL ROUTING</small><h1>Specialists, not a model picker.</h1><p>Each model gets a bounded role. An implementer cannot approve its own output.</p></div>
        <div className="agent-grid">{agents.map(agent=><article key={agent.name}>
          <i style={{background: agent.color}}>{agent.glyph}</i><div><small>{agent.status}</small><h2>{agent.name}</h2><p>{agent.role}</p></div>
        </article>)}</div>
      </div>}
    </section>

    <aside className="control-inspector">
      <header><small>{t.gate}</small><strong>{t.verified}</strong></header>
      <div className="release-score"><b>100</b><span>/ 100</span><div><i /></div><p>Independent review closed every blocker before release.</p></div>
      <section><small>RELEASE CHECKS</small>{["Build reproduced","34 tests pass","TypeScript clean","Codex review: PASS"].map(item=><div className="check" key={item}><i>✓</i>{item}</div>)}</section>
      <section><small>ACTIVE CREW</small>{agents.slice(0,4).map(agent=><div className="mini-agent" key={agent.name}><i style={{background:agent.color}}>{agent.glyph}</i><span><b>{agent.name}</b><em>{agent.status}</em></span></div>)}</section>
      <footer><small>DOWNLOADABLE SOURCE</small><p>Expo project ready for iPhone testing. App Store signing requires Apple credentials.</p><a href="https://github.com/kokoaru-ltd/guildless/archive/refs/heads/agent/cross-model-production-policy.zip">Download project ↓</a></footer>
    </aside>
  </main>;
}

function Pipeline({ locale }: { locale: Locale }) {
  const t = labels[locale];
  return <section className="pipeline-section">
    <div className="pipeline-title"><div><small>AUTONOMOUS PRODUCTION</small><h2>{t.timeline}</h2></div><span>6 HANDOFFS · 0 SELF-APPROVALS</span></div>
    <div className="pipeline">{events.map((event, index)=><article className={event.fail?"failed":event.pass?"passed":""} key={event.time}>
      <header><i>{index+1}</i><span>{event.actor}</span><em>{event.result}</em></header><h3>{event.title}</h3><p>{event.detail}</p>
    </article>)}</div>
  </section>;
}
