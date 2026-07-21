"use client";

import { useState } from "react";

const engines = [
  { name: "GPT Image", role: "Visual Studio", task: "コンセプトアート・UI・ゲーム素材", color: "#ff735c", mark: "GI" },
  { name: "Claude", role: "Engineering", task: "設計・実装・レビュー", color: "#db9b63", mark: "CL" },
  { name: "Kimi", role: "Operations", task: "低コストな監視・保守・調査", color: "#5b8def", mark: "KI" },
  { name: "Gemini", role: "Media Lab", task: "動画・音声・大規模コンテキスト", color: "#43aa82", mark: "GE" },
  { name: "Seedance", role: "Motion Studio", task: "PV・広告・ゲーム映像", color: "#9a78e5", mark: "SE" },
];

const stages = [
  { name: "企画・市場検証", owner: "Strategy", status: "done" },
  { name: "世界観・仕様設計", owner: "Director", status: "done" },
  { name: "ゲームプレイ実装", owner: "Engineering", status: "active" },
  { name: "アセット制作", owner: "Visual Studio", status: "active" },
  { name: "自動プレイテスト", owner: "QA", status: "queued" },
  { name: "PV・ストア公開", owner: "Growth", status: "queued" },
];

export default function Home() {
  const [goal, setGoal] = useState("協力プレイ対応のローグライトゲームを、Steamで90日以内に公開する");
  const [running, setRunning] = useState(false);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="logo"><span>G</span> GUILDLESS <small>alpha</small></div>
        <nav>
          <a className="active" href="#mission">⌘<span>Mission Control</span></a>
          <a href="#roadmap">◇<span>Roadmap</span></a>
          <a href="#studio">◫<span>AI Studio</span></a>
          <a href="#builds">△<span>Builds</span></a>
          <a href="#growth">↗<span>Growth</span></a>
        </nav>
        <div className="solo-card">
          <span className="pulse" /> SOLO OPERATOR
          <strong>1 human</strong>
          <p>12 agents working</p>
        </div>
      </aside>

      <section className="workspace" id="mission">
        <header>
          <div><span className="overline">PROJECT / NIGHTFALL</span><h1>Mission Control</h1></div>
          <div className="top-stats"><span><small>MONTHLY BURN</small>¥38,420</span><span><small>TEAM SAVED</small>14.2人月</span><button>Ship build</button></div>
        </header>

        <section className="mission-card">
          <div className="mission-copy">
            <span className="tag">OWNER DIRECTIVE</span>
            <h2>あなたが決める。<br /><em>AIスタジオが完成させる。</em></h2>
            <p>ゲーム、SaaS、アプリ、映像、マーケティング。目標から公開・運用まで、専門エージェントが並列で進めます。</p>
          </div>
          <div className="directive-box">
            <label htmlFor="goal">今回のゴール</label>
            <textarea id="goal" value={goal} onChange={(e) => setGoal(e.target.value)} />
            <div><span>予算上限 ¥100,000 / 月</span><button onClick={() => { setRunning(true); setTimeout(() => setRunning(false), 1200); }}>{running ? "組織を編成中…" : "開発を開始 →"}</button></div>
          </div>
        </section>

        <div className="grid">
          <section className="panel pipeline" id="roadmap">
            <div className="panel-head"><div><span>LIVE EXECUTION</span><h3>90日リリース計画</h3></div><button>全体を見る</button></div>
            <div className="progress"><i /><span>Day 18 / 90</span><b>21%</b></div>
            <div className="stage-list">
              {stages.map((stage, index) => <div className={`stage ${stage.status}`} key={stage.name}><span className="stage-no">{stage.status === "done" ? "✓" : index + 1}</span><div><strong>{stage.name}</strong><small>{stage.owner}</small></div><em>{stage.status === "active" ? "進行中" : stage.status === "done" ? "完了" : "待機"}</em></div>)}
            </div>
          </section>

          <section className="panel studio" id="studio">
            <div className="panel-head"><div><span>BEST ENGINE FOR THE JOB</span><h3>AI Studio</h3></div><i className="live-dot" /></div>
            <p className="panel-description">モデルに忠誠を持たない。品質・速度・費用から、タスクごとに最良のエンジンを使います。</p>
            <div className="engine-list">
              {engines.map((engine) => <div className="engine" key={engine.name}><span className="engine-mark" style={{ background: engine.color }}>{engine.mark}</span><div><strong>{engine.role}</strong><small>{engine.task}</small></div><em>{engine.name}</em></div>)}
            </div>
          </section>

          <section className="panel approvals">
            <div className="panel-head"><div><span>ONLY YOU CAN DECIDE</span><h3>2件の承認待ち</h3></div></div>
            <article><span className="risk">DESIGN</span><strong>戦闘テンポを15%速くする</strong><p>AIプレイテストでは継続率が8.4%改善。既存アニメーション42点を自動調整します。</p><div><button className="ghost">詳しく見る</button><button className="approve">承認</button></div></article>
            <article><span className="risk money">COST</span><strong>PV動画の高品質レンダリング</strong><p>Seedanceによる30秒PV。追加費用見込み ¥1,840。</p><div><button className="ghost">却下</button><button className="approve">承認</button></div></article>
          </section>

          <section className="panel output" id="builds">
            <div className="panel-head"><div><span>TODAY'S OUTPUT</span><h3>スタジオ稼働状況</h3></div><b>47 tasks</b></div>
            <div className="metric-row"><div><strong>18</strong><span>実装</span></div><div><strong>142</strong><span>テスト</span></div><div><strong>36</strong><span>素材</span></div><div><strong>4</strong><span>施策</span></div></div>
            <div className="activity"><span>06:42</span><p><b>QA Agent</b> ボス戦を10,000回シミュレーション</p><em>完了</em></div>
            <div className="activity"><span>06:38</span><p><b>Growth Agent</b> SteamストアA/Bコピーを生成</p><em>実行中</em></div>
          </section>
        </div>
      </section>
    </main>
  );
}
