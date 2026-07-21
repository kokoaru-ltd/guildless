"use client";

import { useMemo, useState } from "react";

const agents = [
  { id: "maker", name: "つくる係", mark: "作", color: "coral", skill: "Web・アプリ・ファイル", note: "考えるだけでなく、動くものまで仕上げます", engines: "Codex ほか" },
  { id: "editor", name: "つたえる係", mark: "伝", color: "violet", skill: "資料・文章・デザイン", note: "あなたらしい表現を覚えて整えます", engines: "Fable ほか" },
  { id: "researcher", name: "しらべる係", mark: "調", color: "blue", skill: "調査・比較・長い資料", note: "根拠を集め、判断できる形にまとめます", engines: "Kimi ほか" },
  { id: "operator", name: "うごかす係", mark: "動", color: "green", skill: "メール・予定・定型業務", note: "許可をもらい、いつもの仕事を実行します", engines: "Gemini ほか" },
];

const jobs = [
  { icon: "⌘", label: "Webサイトを作る", prompt: "商品の魅力が伝わるWebサイトを作って" },
  { icon: "文", label: "資料をまとめる", prompt: "この資料を読んで要点をわかりやすくまとめて" },
  { icon: "◎", label: "画像を読み取る", prompt: "画像の内容を読み取って改善案を出して" },
  { icon: "✦", label: "アイデアを形にする", prompt: "新しいサービスのアイデアを企画にして" },
];

function pickAgent(text: string) {
  const value = text.toLowerCase();
  if (/コード|web|サイト|アプリ|修正|開発/.test(value)) return agents[0];
  if (/スライド|資料を作|物語|文章|企画/.test(value)) return agents[1];
  if (/調べ|検索|要約|長い|pdf|資料を読/.test(value)) return agents[2];
  if (/画像|写真|google|表|動画/.test(value)) return agents[3];
  return agents[1];
}

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const recommendation = useMemo(() => pickAgent(prompt), [prompt]);

  function submit() {
    if (!prompt.trim()) return;
    setRunning(true);
    setSelected(recommendation.id);
    window.setTimeout(() => setRunning(false), 900);
  }

  return (
    <main>
      <nav className="nav">
        <a className="brand" href="#top" aria-label="さかなAI ホーム">
          <span className="fish" aria-hidden="true">›<i>°</i>)))彡</span>
          <span>さかな<span>AI</span></span>
        </a>
        <div className="nav-actions">
          <button className="plain-button">使い方</button>
          <button className="history-button"><span>↺</span> 履歴</button>
          <button className="avatar" aria-label="アカウント">さ</button>
        </div>
      </nav>

      <section className="hero" id="top">
        <div className="eyebrow"><span>✦</span> AIを選ばなくていい、新しい働き方</div>
        <h1>やりたいことを、<br /><em>得意なAI</em>へ。</h1>
        <p className="lead">ひとこと頼むだけ。さかなAIが、いちばん得意な<br className="desktop" />エージェントを選んで仕事を任せます。</p>

        <div className="composer-wrap">
          <div className="composer">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") submit();
              }}
              placeholder="今日は、なにを手伝いましょう？"
              aria-label="AIへの依頼"
            />
            <div className="composer-footer">
              <div className="route-preview">
                <span className={`mini-mark ${recommendation.color}`}>{recommendation.mark}</span>
              <span>{prompt ? `${recommendation.name} が担当` : "費用0円の経路を優先"}</span>
              </div>
              <button className="send" onClick={submit} disabled={!prompt.trim() || running} aria-label="依頼を送る">{running ? "…" : "↑"}</button>
            </div>
          </div>
          {selected && (
            <div className="result-toast" role="status">
              <span className={`mini-mark ${recommendation.color}`}>{recommendation.mark}</span>
              <div><strong>{running ? "完了までの道筋を考えています…" : `${recommendation.name} が仕事を始めました`}</strong><small>{running ? "使う道具・費用・確認点を整理中" : recommendation.note}</small></div>
              {!running && <span className="check">✓</span>}
            </div>
          )}
          <div className="privacy"><span>♢</span> 入力内容は学習に使いません</div>
        </div>

        <div className="quick-jobs">
          {jobs.map((job) => (
            <button key={job.label} onClick={() => setPrompt(job.prompt)}>
              <span>{job.icon}</span>{job.label}
            </button>
          ))}
        </div>
      </section>

      <section className="agents-section">
        <div className="section-heading">
          <div><span className="kicker">YOUR AI CREW</span><h2>モデルではなく、仕事で選ぶ。</h2></div>
          <p>裏側のAIが入れ替わっても大丈夫。<br />あなたの仕事の進め方は、ここに残ります。</p>
        </div>
        <div className="agent-grid">
          {agents.map((agent) => (
            <article className="agent-card" key={agent.id}>
              <span className={`agent-mark ${agent.color}`}>{agent.mark}</span>
              <div className="availability"><i /> 利用できます</div>
              <h3>{agent.name}</h3>
              <strong>{agent.skill}</strong>
              <p>{agent.note}</p>
              <span className="engine-label">現在の候補：{agent.engines}</span>
              <button onClick={() => { setPrompt(`${agent.name}に、`); document.getElementById("top")?.scrollIntoView({ behavior: "smooth" }); }}>この係に頼む <span>→</span></button>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
