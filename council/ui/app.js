const terminalStates = new Set(["completed", "degraded", "partial", "awaiting_approval", "failed"]);
const statusLabels = {
  queued: "待機中", researching: "OSSを探索中", analysis_researching: "GitHubを調査中",
  analysis_proposing: "専門AIが提案中", analysis_criticizing: "反対意見を検討中",
  analysis_judging: "最終判定中", analysis_completed: "Council完了",
  analysis_degraded: "一部モデルで継続", cloning: "固定コミットを取得中",
  implementing: "Action Agentが実装中", verifying: "成果物を検証中",
  completed: "完了", degraded: "縮退完了", partial: "要確認",
  awaiting_approval: "承認待ち", failed: "失敗"
};
const statusDetails = {
  queued: "ジョブを実行待ちキューへ登録しました。", researching: "目的に合うOSS候補を探しています。",
  analysis_researching: "候補のライセンス・更新状況・機能を確認しています。",
  analysis_proposing: "Research・Sales・Financeが独立して提案しています。",
  analysis_criticizing: "Devil's Advocateが提案の弱点を検査しています。",
  analysis_judging: "独立Judgeが採否と次の行動を決めています。",
  analysis_completed: "Councilの候補判断を保存しました。",
  analysis_degraded: "利用可能なモデルだけでCouncilを継続しました。",
  cloning: "選定OSSを固定コミットで隔離領域へ取得しています。",
  implementing: "読み取り専用Action Agentが実装ファイルを設計しています。",
  verifying: "Guildless本体が成果物・テスト・元OSSハッシュを検証しています。",
  completed: "実装とテストを完了し、監査記録を保存しました。",
  degraded: "一部機能を縮退して完了しました。", partial: "成果物はありますが、合格条件を満たしていません。",
  awaiting_approval: "外部作用の前で停止しています。", failed: "処理を安全に停止しました。"
};

const state = { jobs: [], currentJobId: localStorage.getItem("guildless.currentJob"), events: [], after: 0, timer: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const shortId = (id = "") => id.length > 28 ? `${id.slice(0, 20)}…${id.slice(-6)}` : id;
const timeLabel = (value) => value ? new Intl.DateTimeFormat("ja-JP", {hour:"2-digit", minute:"2-digit", second:"2-digit"}).format(new Date(value)) : "--:--";
const dateLabel = (value) => value ? new Intl.DateTimeFormat("ja-JP", {month:"numeric", day:"numeric", hour:"2-digit", minute:"2-digit"}).format(new Date(value)) : "—";

function statusClass(status) {
  if (status === "completed") return "is-success";
  if (["failed"].includes(status)) return "is-error";
  if (["degraded", "partial", "awaiting_approval"].includes(status)) return "is-warning";
  if (status && status !== "idle") return "is-running";
  return "is-idle";
}

function eventStage(status) {
  if (["researching", "analysis_researching"].includes(status)) return 0;
  if (status.startsWith("analysis_") && !["analysis_completed","analysis_degraded"].includes(status)) return 1;
  if (["analysis_completed", "analysis_degraded", "cloning"].includes(status)) return 2;
  if (status === "implementing") return 3;
  if (status === "verifying") return 4;
  if (terminalStates.has(status)) return 5;
  return -1;
}

function renderPipeline(status, events = []) {
  const latest = events.length ? events[events.length - 1].status : status;
  let active = eventStage(latest);
  if (status === "completed") active = 5;
  const stages = $$(".stage");
  const lines = $$(".stage-line");
  stages.forEach((node, index) => {
    node.classList.toggle("is-done", status === "completed" ? true : index < active);
    node.classList.toggle("is-active", index === active && !["failed", "partial"].includes(status));
  });
  lines.forEach((node, index) => node.classList.toggle("is-done", status === "completed" || index < active));
}

function renderActivity(events) {
  const list = $("#activityList");
  if (!events.length) {
    list.innerHTML = '<div class="empty-state"><span>⌁</span><p>保存済みジョブです。<br>結果は右側で確認できます。</p></div>';
    return;
  }
  list.innerHTML = events.map((event) => `
    <div class="activity-item">
      <time>${escapeHtml(timeLabel(event.occurred_at))}</time>
      <span class="activity-mark">${terminalStates.has(event.status) ? "✓" : "•"}</span>
      <div class="activity-copy">
        <b>${escapeHtml(statusLabels[event.status] || event.status)}</b>
        <p>${escapeHtml(statusDetails[event.status] || JSON.stringify(event.details || {}))}</p>
      </div>
    </div>`).join("");
  list.scrollTop = list.scrollHeight;
}

function renderInspector(payload) {
  const result = payload?.result;
  const inspector = $("#resultInspector");
  if (!result) {
    inspector.innerHTML = '<div class="empty-state"><span>◇</span><p>Guildlessが処理中です。<br>結果が届くまで待っています。</p></div>';
    return;
  }
  const report = result.execution_report || {};
  const verification = result.verification || {};
  const repository = result.selected_repository || {};
  const audit = payload.execution_audit || {};
  const approval = report.approval_requests || [];
  inspector.innerHTML = `
    <div class="result-block"><label>実行結果</label><p>${escapeHtml(report.summary || "結果を保存しました。")}</p></div>
    <div class="result-grid">
      <div class="result-chip"><span>採用OSS</span><strong>${escapeHtml(repository.full_name || "—")}</strong></div>
      <div class="result-chip"><span>固定COMMIT</span><strong>${escapeHtml((repository.commit_sha || "—").slice(0,10))}</strong></div>
      <div class="result-chip"><span>実行言語</span><strong>${escapeHtml((audit.detected_runtimes || []).join(" + ") || "—")}</strong></div>
      <div class="result-chip"><span>元OSS</span><strong>${verification.source_unchanged === false ? "変更あり" : "変更なし"}</strong></div>
    </div>
    <div class="result-block" style="margin-top:15px"><label>次の行動</label><p>${escapeHtml(report.next_action || "人間レビューを待ちます。")}</p></div>
    ${approval.length ? `<div class="result-block"><label>承認が必要</label><p>${escapeHtml(approval.join(" / "))}</p></div>` : ""}`;
}

function renderCurrent(payload) {
  const result = payload?.result || {};
  const report = result.execution_report || {};
  const verify = result.verification || {};
  const repo = result.selected_repository || {};
  const status = payload?.status || "idle";
  const statusNode = $("#runStatus");
  statusNode.className = `status-badge ${statusClass(status)}`;
  statusNode.innerHTML = `<span></span>${escapeHtml(statusLabels[status] || status)}`;
  $("#currentObjective").textContent = result.objective || state.jobs.find((job) => job.job_id === state.currentJobId)?.objective || "処理を開始しています。";
  $("#currentJobId").textContent = state.currentJobId ? shortId(state.currentJobId) : "NO ACTIVE JOB";
  $("#repoMetric").textContent = repo.full_name || state.jobs.find((job) => job.job_id === state.currentJobId)?.repository || "—";
  $("#testMetric").textContent = verify.passed_test_count ?? 0;
  $("#fileMetric").textContent = verify.output_file_count ?? 0;
  $("#effectMetric").textContent = result.external_actions_performed ? "!" : "0";
  renderPipeline(status, state.events);
  renderInspector(payload);
  renderJobs();
  if (report.summary) $("#activeRunTitle").textContent = status === "completed" ? "完了した実行" : "現在の実行";
}

function renderJobs() {
  const list = $("#jobList");
  if (!state.jobs.length) {
    list.innerHTML = '<div class="empty-state"><span>＋</span><p>まだ仕事がありません。</p></div>';
    return;
  }
  list.innerHTML = state.jobs.map((job) => {
    const stateName = job.status === "completed" ? "completed" : job.status === "failed" ? "failed" : terminalStates.has(job.status) ? "failed" : "running";
    return `<button class="job-row ${job.job_id === state.currentJobId ? "is-selected" : ""}" data-job-id="${escapeHtml(job.job_id)}" type="button">
      <span class="job-state ${stateName}"></span>
      <span class="job-main"><strong>${escapeHtml(job.objective || "目的を取得中")}</strong><small>${escapeHtml(shortId(job.job_id))}</small></span>
      <span class="job-cell"><strong>${escapeHtml(statusLabels[job.status] || job.status)}</strong><br>${escapeHtml(dateLabel(job.updated_at))}</span>
      <span class="job-cell">TEST<br><strong>${Number(job.passed_test_count || 0)}</strong></span>
      <span class="job-cell">外部作用<br><strong>${job.external_actions_performed ? "あり" : "0"}</strong></span>
    </button>`;
  }).join("");
  $$(".job-row").forEach((button) => button.addEventListener("click", () => selectJob(button.dataset.jobId)));
}

async function loadJobs({selectFirst = true} = {}) {
  try {
    const response = await fetch("/v1/guildless/jobs?limit=20");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.jobs = data.jobs || [];
    renderJobs();
    const exists = state.jobs.some((job) => job.job_id === state.currentJobId);
    if (selectFirst && state.jobs.length) {
      await selectJob(exists ? state.currentJobId : state.jobs[0].job_id);
    }
  } catch (error) {
    $("#jobList").innerHTML = `<div class="empty-state"><span>!</span><p>履歴を取得できません。<br>${escapeHtml(error.message)}</p></div>`;
  }
}

async function selectJob(jobId) {
  clearTimeout(state.timer);
  state.currentJobId = jobId;
  state.events = [];
  state.after = 0;
  localStorage.setItem("guildless.currentJob", jobId);
  renderJobs();
  await pollCurrent();
}

async function pollCurrent() {
  if (!state.currentJobId) return;
  try {
    const [jobResponse, eventResponse] = await Promise.all([
      fetch(`/v1/guildless/jobs/${encodeURIComponent(state.currentJobId)}`),
      fetch(`/v1/guildless/jobs/${encodeURIComponent(state.currentJobId)}/events?after=${state.after}`)
    ]);
    if (!jobResponse.ok) throw new Error(`ジョブ取得 ${jobResponse.status}`);
    const payload = await jobResponse.json();
    if (eventResponse.ok) {
      const eventData = await eventResponse.json();
      state.events.push(...(eventData.events || []));
      state.after = eventData.next_after || state.after;
    }
    renderActivity(state.events);
    renderCurrent(payload);
    if (!terminalStates.has(payload.status)) state.timer = setTimeout(pollCurrent, 900);
    else await loadJobs({selectFirst:false});
  } catch (error) {
    $("#formMessage").textContent = error.message;
  }
}

async function startJob(event) {
  event.preventDefault();
  const objective = $("#objective").value.trim();
  const queries = $("#githubQueries").value.split("\n").map((value) => value.trim()).filter(Boolean);
  const providers = $$('input[name="provider"]:checked').map((input) => input.value);
  const message = $("#formMessage");
  if (!objective) { message.textContent = "Guildlessへの指示を入力してください。"; return; }
  if (!queries.length) { message.textContent = "GitHub検索語を1件以上入力してください。"; return; }
  if (providers.length < 2) { message.textContent = "Councilには2つ以上の知能を選んでください。"; return; }
  message.textContent = "";
  const button = $("#runButton");
  button.disabled = true;
  button.querySelector("span:last-child").textContent = "開始中…";
  try {
    const response = await fetch("/v1/guildless/jobs", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        objective, github_queries: queries, context: {}, allowed_providers: providers,
        workspace_label: "ui", max_rounds: 1, max_execution_minutes: 20,
        constraints: {license_allowlist:["MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause"], min_stars:0, max_candidates:10, active_within_days:730}
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : `HTTP ${response.status}`);
    await loadJobs({selectFirst:false});
    await selectJob(data.run_id);
  } catch (error) { message.textContent = `開始できません: ${error.message}`; }
  finally { button.disabled = false; button.querySelector("span:last-child").textContent = "実行する"; }
}

function updateClock() { $("#clock").textContent = new Intl.DateTimeFormat("ja-JP", {hour:"2-digit", minute:"2-digit", second:"2-digit"}).format(new Date()); }
$("#jobForm").addEventListener("submit", startJob);
$("#refreshButton").addEventListener("click", () => { loadJobs({selectFirst:false}); pollCurrent(); });
$("#historyRefresh").addEventListener("click", () => loadJobs({selectFirst:false}));
$$('.nav-item').forEach((button) => button.addEventListener("click", () => { $$('.nav-item').forEach((item) => item.classList.remove("is-active")); button.classList.add("is-active"); }));
updateClock(); setInterval(updateClock, 1000); loadJobs();
