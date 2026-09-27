"use client";
import { useEffect, useState } from "react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Orbit,
  LayoutDashboard,
  Network,
  ClipboardList,
  FlaskConical,
  History,
  ArrowUpRight,
  Plus,
  Check,
  Play,
  RotateCcw,
  Download,
  CircleDot,
} from "lucide-react";

type Report = {
  summary: string;
  draft: string;
  needs_review: boolean;
  findings: {
    title: string;
    detail: string;
    sources: string[];
    severity: string;
  }[];
};
type Mission = {
  id: string;
  title: string;
  goal: string;
  mode: string;
  version: number;
  status: string;
  active_role: string | null;
  calls: number;
  call_limit: number;
  package_hash: string;
  error: string | null;
  artifacts: Record<string, { version: number; report: Report }>;
  events: { sequence: number; time: string; type: string; detail: string }[];
  input: { sources: { id: string; text: string }[] };
  route: { roles: string[]; reason: string; workflow: string };
  traces: {
    id: string;
    role: string;
    status: string;
    reason: string;
    duration_ms: number;
    tools: { tool: string; status: string; result_count: number }[];
    evaluation: { passed: boolean } | null;
  }[];
  usage: {
    trace_id: string;
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number | null;
  }[];
};
const team = [
  { id: "pd", name: "Milo", role: "총괄 PD", letter: "M", color: "#b59cff" },
  {
    id: "story",
    name: "Story",
    role: "글작가 · 편집",
    letter: "S",
    color: "#f3bd7d",
  },
  {
    id: "audience",
    name: "Audience",
    role: "독자 분석",
    letter: "A",
    color: "#8acac1",
  },
  {
    id: "campaign",
    name: "Campaign",
    role: "마케팅",
    letter: "C",
    color: "#e9a2b8",
  },
  { id: "qa", name: "QA", role: "최종 검수", letter: "Q", color: "#aabbea" },
];
const statuses: Record<string, string> = {
  draft: "실행 준비",
  queued: "실행 대기",
  running: "작업 중",
  review_required: "운영자 검토",
  approved: "승인 완료",
  exported: "내보내기 완료",
  failed: "실행 중단",
};
async function api(path: string, body?: unknown) {
  const r = await fetch(
    "/api" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  const data = await r.json();
  if (!r.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "요청을 처리하지 못했습니다.",
    );
  return data;
}
export default function Studio() {
  const [workflow, setWorkflow] = useState("auto");
  const [tab, setTab] = useState("Studio"),
    [missions, setMissions] = useState<Mission[]>([]),
    [selected, setSelected] = useState<string | null>(null),
    [role, setRole] = useState("story"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [form, setForm] = useState(false),
    [goal, setGoal] = useState(
      "EP.12의 설정 충돌을 수정하고 스포일러 없는 공개 준비 패키지를 만들어 주세요.",
    ),
    [title, setTitle] = useState("별빛식당 · EP.12 공개 준비"),
    [mode, setMode] = useState("mock"),
    [instruction, setInstruction] = useState(""),
    [revRole, setRevRole] = useState("campaign"),
    [health, setHealth] = useState<{
      live_configured: boolean;
      storage: string;
    } | null>(null);
  const m = missions.find((x) => x.id === selected) || missions[0];
  async function refresh() {
    const data = await api("/missions");
    setMissions(data);
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    api("/health")
      .then(setHealth)
      .catch(() =>
        setError("API 서버에 연결할 수 없습니다. 실행 상태를 확인하세요."),
      );
  }, []);
  useEffect(() => {
    if (!m) return;
    const es = new EventSource("/api/missions/" + m.id + "/events");
    es.onmessage = () => refresh().catch(() => {});
    return () => es.close();
  }, [m?.id]);
  useEffect(() => {
    if (!m || !["queued", "running"].includes(m.status)) return;
    const timer = setInterval(() => refresh().catch(() => {}), 1500);
    return () => clearInterval(timer);
  }, [m?.id, m?.status]);
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "요청 실패");
    } finally {
      setBusy(false);
    }
  }
  const report = m?.artifacts[role]?.report;
  const working = m && ["queued", "running"].includes(m.status);
  const completed = m ? Object.keys(m.artifacts).length : 0;
  const totalTokens =
    m?.usage.reduce((sum, u) => sum + u.input_tokens + u.output_tokens, 0) || 0;
  const qa = m?.artifacts.qa?.report;
  const canApprove =
    m?.status === "review_required" &&
    qa &&
    !qa.needs_review &&
    !qa.findings.some((f) => ["warning", "blocker"].includes(f.severity));
  const activeTeam = team.filter((t) => !m || m.route.roles.includes(t.id));
  const nodes = activeTeam.map((t, i) => ({
    id: t.id,
    position: { x: i * 195, y: i % 2 ? 65 : 0 },
    data: { label: t.name + " · " + t.role },
    style: {
      background: m?.artifacts[t.id] ? "#ede8fa" : "#fff",
      border: "1px solid #d5cbe8",
      borderRadius: 14,
      padding: 12,
      width: 178,
      fontSize: 12,
    },
  }));
  const edges = activeTeam
    .slice(1)
    .map((t, i) => ({
      id: "e" + i,
      source: activeTeam[i].id,
      target: t.id,
      animated: !!working,
    }));
  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <Orbit size={30} />
          <span>
            ORBIT<small>STUDIO OPERATING SYSTEM</small>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">N</span>
          <div>
            NOVA INK Studios<small>가상 스튜디오 · 실험 환경</small>
          </div>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {[
            [LayoutDashboard, "Studio"],
            [Network, "Organization"],
            [ClipboardList, "Missions"],
            [FlaskConical, "Agent Lab"],
            [History, "Audit"],
          ].map(([Icon, label]) => {
            const I = Icon as typeof Orbit;
            return (
              <button
                key={label as string}
                className={tab === label ? "active" : ""}
                onClick={() => setTab(label as string)}
              >
                <I size={18} />
                {label as string}
                {label === "Studio" && <span className="nav-dot" />}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-note">
          <CircleDot size={19} />
          <strong>Stories, run differently.</strong>
          <p>
            하나의 목표.
            <br />
            함께 움직이는 AI 팀.
          </p>
          <span>LOCAL PROTOTYPE · v0.3</span>
        </div>
        <div className="operator">
          <div className="avatar">OP</div>
          <div>
            Studio Operator<small>최종 결정은 운영자가 합니다</small>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            Workspace <span>/</span> {tab}
          </div>
          <div className="connection">
            <i /> {health ? "API 연결됨" : "연결 확인 중"}{" "}
            <span>{health?.storage || "—"}</span>
          </div>
        </header>
        <div className="content">
          <div className="page-title">
            <div>
              <div className="eyebrow">NOVA INK STUDIOS / CONTROL ROOM</div>
              <h1>{tab === "Studio" ? "Your studio, in orbit." : tab}</h1>
              <p>팀의 작업을 살펴보고, 다음 이야기를 위한 결정을 내리세요.</p>
            </div>
            <button className="primary" onClick={() => setForm(true)}>
              <Plus size={17} />새 미션
            </button>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          {form && (
            <section className="create">
              <div className="section-heading">
                <h2>새 공개 준비 미션</h2>
                <button className="text-btn" onClick={() => setForm(false)}>
                  닫기
                </button>
              </div>
              <label>
                미션 이름
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={100}
                />
              </label>
              <label>
                PD에게 전달할 목표
                <textarea
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  maxLength={2000}
                />
              </label>
              <label>
                작업 범위
                <select
                  value={workflow}
                  onChange={(e) => setWorkflow(e.target.value)}
                >
                  <option value="auto">목표에서 자동 라우팅</option>
                  <option value="full">전체 공개 준비</option>
                  <option value="story">원고·설정 검토</option>
                  <option value="campaign">홍보 준비</option>
                </select>
              </label>
              <div className="form-row">
                <label>
                  실행 모드
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="mock">모의 응답 · 비용 없음</option>
                    <option value="live" disabled={!health?.live_configured}>
                      OpenAI · 비활성화됨
                    </option>
                  </select>
                </label>
                <p>
                  합성 EP.12 자료 사용 · 최대 12회 호출
                  <br />
                  실제 모델 호출은 서버에서 잠겨 있습니다.
                </p>
                <button
                  className="primary"
                  disabled={busy || !title.trim() || goal.trim().length < 5}
                  onClick={() =>
                    action(async () => {
                      const n = await api("/missions", {
                        title,
                        goal,
                        mode,
                        workflow,
                      });
                      setSelected(n.id);
                      setForm(false);
                      setTab("Studio");
                    })
                  }
                >
                  미션 만들기 <ArrowUpRight size={16} />
                </button>
              </div>
            </section>
          )}
          <div className="metrics">
            <div>
              <span>ACTIVE MISSION</span>
              <strong>
                {missions
                  .filter((x) => !["approved", "exported"].includes(x.status))
                  .length.toString()
                  .padStart(2, "0")}
              </strong>
              <small>검토와 실행을 기다리는 목표</small>
            </div>
            <div>
              <span>YOUR AI TEAM</span>
              <strong>
                05 <em>agents</em>
              </strong>
              <small>PD · 스토리 · 독자 · 마케팅 · QA</small>
            </div>
            <div>
              <span>MISSION PROGRESS</span>
              <strong>
                {completed}
                <em> / {m?.route.roles.length || 5}</em>
              </strong>
              <small>라우팅된 역할 중 완료</small>
            </div>
            <div>
              <span>MODEL USAGE</span>
              <strong>
                {totalTokens.toLocaleString()} <em>tokens</em>
              </strong>
              <small>
                {m
                  ? m.calls + " / " + m.call_limit + " 호출 사용"
                  : "실행 후 사용량 표시"}{" "}
                · 금액 미산정
              </small>
            </div>
          </div>
          {tab === "Agent Lab" ? (
            <section className="panel empty">
              <FlaskConical size={36} />
              <h2>좋은 동료는 검증에서 시작됩니다.</h2>
              <p>
                후보 모델 비교·역할 설정 활성화는 다음 단계입니다.
                <br />
                현재는 고정된 5개 역할로 첫 미션을 검증합니다.
              </p>
              <span className="badge">설계 단계 · 아직 구현되지 않음</span>
            </section>
          ) : tab === "Organization" ? (
            <section className="panel">
              <div className="section-heading">
                <h2>스튜디오 조직과 실행 순서</h2>
                <span className="muted">
                  규칙 기반 라우팅 · 선택한 역할 순차 실행
                </span>
              </div>
              <div style={{ height: 270 }}>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  fitView
                  nodesDraggable={false}
                >
                  <Background color="#e6e0ee" />
                  <Controls showInteractive={false} />
                </ReactFlow>
              </div>
              <p className="muted">
                운영자 → 총괄 PD Milo → 글작가·편집 → 독자 분석 → 마케팅 → QA →
                운영자 승인
              </p>
            </section>
          ) : tab === "Audit" ? (
            <section className="panel">
              <div className="section-heading">
                <h2>실행 이력</h2>
                <span className="badge">실제 저장된 이벤트</span>
              </div>
              {m ? (
                <>
                  <select
                    aria-label="감사 미션 선택"
                    value={m.id}
                    onChange={(e) => setSelected(e.target.value)}
                  >
                    {missions.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.title}
                      </option>
                    ))}
                  </select>
                  <div className="trace-grid">
                    {m.traces.map((t) => (
                      <article className="trace" key={t.id}>
                        <strong>
                          {t.role} · {t.status}
                        </strong>
                        <p>{t.reason}</p>
                        <p>
                          {m.usage.filter(u => u.trace_id === t.id).reduce((n,u) => n+u.input_tokens+u.output_tokens,0)} tokens · 비용 {m.mode === "mock" ? "$0 (모의 응답)" : m.usage.filter(u => u.trace_id === t.id).length && m.usage.filter(u => u.trace_id === t.id).every(u => u.estimated_cost_usd !== null) ? "$" + m.usage.filter(u => u.trace_id === t.id).reduce((n,u) => n+(u.estimated_cost_usd ?? 0),0).toFixed(6) + " (추정)" : "미산정"}
                        </p>
                        <small>
                          {t.duration_ms ?? "—"} ms · 평가{" "}
                          {t.evaluation
                            ? t.evaluation.passed
                              ? "통과"
                              : "실패"
                            : "대기"}
                        </small>
                        <ul>
                          {t.tools.map((tool, i) => (
                            <li key={i}>
                              {tool.tool} · {tool.status} · {tool.result_count}
                              건
                            </li>
                          ))}
                        </ul>
                      </article>
                    ))}
                  </div>
                  {[...m.events].reverse().map((e) => (
                    <div className="event" key={e.sequence}>
                      <span>#{e.sequence}</span>
                      <div>
                        <strong>{e.detail}</strong>
                        <small>
                          {new Date(e.time).toLocaleString("ko-KR")} · {e.type}
                        </small>
                      </div>
                    </div>
                  ))}
                </>
              ) : (
                <p className="muted">미션을 만들면 실행 이력이 표시됩니다.</p>
              )}
            </section>
          ) : (
            <>
              <section className="mission-banner">
                <div className="mission-art">
                  <Orbit size={58} strokeWidth={1} />
                  <span>EP.12</span>
                </div>
                <div className="mission-copy">
                  <div className="eyebrow">
                    CURRENT MISSION{" "}
                    <span className="badge">
                      {m ? statuses[m.status] : "첫 미션을 기다리는 중"}
                    </span>
                  </div>
                  <h2>{m?.title || "별빛식당의 다음 회차를 준비해 볼까요?"}</h2>
                  <p>
                    {m?.goal ||
                      "가상의 원고와 독자 반응으로 팀의 협업을 실험해 보세요."}
                  </p>
                  {m && (
                    <p className="routing-note">
                      ROUTING · {m.route.reason}
                      <br />
                      {m.route.roles.join(" → ")}
                    </p>
                  )}
                  <div className="mission-meta">
                    합성 데이터 <span>·</span>{" "}
                    {m?.mode === "live" ? "OpenAI 실제 실행" : "모의 응답"}{" "}
                    <span>·</span>{" "}
                    {m ? "버전 " + m.version : "새 미션에서 시작"}
                  </div>
                </div>
                <div className="mission-actions">
                  {m && (
                    <select
                      aria-label="미션 선택"
                      value={m.id}
                      onChange={(e) => setSelected(e.target.value)}
                    >
                      {missions.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.title}
                        </option>
                      ))}
                    </select>
                  )}
                  {m && ["draft", "failed"].includes(m.status) && (
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() =>
                        action(() => api("/missions/" + m.id + "/start", {}))
                      }
                    >
                      <Play size={15} />
                      {m.status === "failed"
                        ? "완료 결과 유지하고 재개"
                        : "계획 확인 · 실행"}
                    </button>
                  )}
                  {!m && (
                    <button className="primary" onClick={() => setForm(true)}>
                      첫 미션 만들기 <ArrowUpRight size={16} />
                    </button>
                  )}
                </div>
              </section>
              <div className="section-heading team-heading">
                <h2>
                  Your crew <span>팀 현황</span>
                </h2>
                <span className="muted">
                  {working
                    ? "작업 진행 중"
                    : "작업 상태는 실행 결과에서 표시됩니다"}
                </span>
              </div>
              <div className="team-grid">
                {team.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setRole(t.id)}
                    className={"agent " + (role === t.id ? "selected" : "")}
                  >
                    <div className="agent-top">
                      <span
                        className="agent-avatar"
                        style={{ background: t.color }}
                      >
                        {t.letter}
                      </span>
                      <span
                        className={
                          "status " + (m?.artifacts[t.id] ? "done" : "")
                        }
                      >
                        {m?.active_role === t.id
                          ? "● 작업 중"
                          : m?.artifacts[t.id]
                            ? "✓ 완료"
                            : m && !m.route.roles.includes(t.id)
                              ? "배정 제외"
                              : "대기"}
                      </span>
                    </div>
                    <strong>{t.name}</strong>
                    <span className="role">{t.role}</span>
                    <div className="agent-foot">
                      {m?.artifacts[t.id]
                        ? "산출물 v" + m.artifacts[t.id].version
                        : "산출물 대기"}
                      <ArrowUpRight size={14} />
                    </div>
                  </button>
                ))}
              </div>
              <div className="bottom-grid">
                <section className="panel output">
                  <div className="section-heading">
                    <h2>
                      {team.find((t) => t.id === role)?.role}{" "}
                      <span>산출물</span>
                    </h2>
                    <span className="badge">
                      {report ? "검토 가능" : "대기"}
                    </span>
                  </div>
                  {report ? (
                    <>
                      <h3>{report.summary}</h3>
                      {report.findings.map((f, i) => (
                        <div className="finding" key={i}>
                          <strong>{f.title}</strong>
                          <p>{f.detail}</p>
                          <div className="source-tags">
                            {f.sources.map((s) => (
                              <details key={s}>
                                <summary>{s}</summary>
                                <p>
                                  {
                                    m.input.sources.find((x) => x.id === s)
                                      ?.text
                                  }
                                </p>
                              </details>
                            ))}
                          </div>
                        </div>
                      ))}
                      <pre className="draft">{report.draft}</pre>
                    </>
                  ) : (
                    <div className="empty-output">
                      <ClipboardList size={30} />
                      <h3>다음 이야기를 기다리고 있어요.</h3>
                      <p>
                        미션을 실행하면 이곳에서 결과와 근거를
                        <br />
                        함께 확인할 수 있습니다.
                      </p>
                    </div>
                  )}
                </section>
                <section className="panel decisions">
                  <div className="section-heading">
                    <h2>Operator desk</h2>
                    <span className="badge">사람의 결정</span>
                  </div>
                  <p className="muted">
                    결과를 검토하고, 필요한 작업만 다시 요청하세요.
                  </p>
                  {m?.error && <p className="error">{m.error}</p>}
                  {m &&
                  ["review_required", "approved", "exported"].includes(
                    m.status,
                  ) ? (
                    <>
                      <label>
                        다시 맡길 역할
                        <select
                          value={
                            m.route.roles.includes(revRole) ? revRole : "story"
                          }
                          onChange={(e) => setRevRole(e.target.value)}
                        >
                          {m.route.roles.includes("campaign") && (
                            <option value="campaign">마케팅 → QA</option>
                          )}
                          {m.route.roles.includes("story") && (
                            <option value="story">
                              글작가·편집과 후속 작업
                            </option>
                          )}
                        </select>
                      </label>
                      <label>
                        수정 요청
                        <textarea
                          placeholder="예: 문안을 더 짧고 따뜻하게 써 주세요."
                          value={instruction}
                          onChange={(e) => setInstruction(e.target.value)}
                        />
                      </label>
                      <button
                        className="secondary"
                        disabled={busy || instruction.trim().length < 3}
                        onClick={() =>
                          action(async () => {
                            await api("/missions/" + m.id + "/revisions", {
                              version: m.version,
                              role: m.route.roles.includes(revRole)
                                ? revRole
                                : "story",
                              instruction,
                            });
                            setInstruction("");
                          })
                        }
                      >
                        <RotateCcw size={15} />
                        선택한 작업 다시 맡기기
                      </button>
                      {m.status === "review_required" && (
                        <>
                          <button
                            className="primary full"
                            disabled={busy || !canApprove}
                            onClick={() =>
                              action(() =>
                                api("/missions/" + m.id + "/approvals", {
                                  version: m.version,
                                  package_hash: m.package_hash,
                                }),
                              )
                            }
                          >
                            <Check size={16} />
                            패키지 승인
                          </button>
                          {!canApprove && (
                            <p className="muted">
                              QA의 미해결 항목을 수정한 뒤 승인할 수 있습니다.
                            </p>
                          )}
                        </>
                      )}
                      {["approved", "exported"].includes(m.status) && (
                        <button
                          className="primary full"
                          onClick={() =>
                            action(async () => {
                              const result = await api(
                                "/missions/" + m.id + "/export", {},
                              );
                              const url = URL.createObjectURL(
                                new Blob([JSON.stringify(result, null, 2)], {
                                  type: "application/json",
                                }),
                              );
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = "orbit-package.json";
                              a.click();
                              URL.revokeObjectURL(url);
                            })
                          }
                        >
                          <Download size={16} />
                          승인 패키지 내보내기
                        </button>
                      )}
                    </>
                  ) : (
                    <div className="waiting">
                      <CircleDot size={22} />
                      <p>
                        팀의 검수가 끝나면
                        <br />
                        승인할 패키지가 도착합니다.
                      </p>
                    </div>
                  )}
                  <div className="decision-note">
                    최종 승인과 외부 게시는 다릅니다.
                    <br />이 프로토타입은 파일 내보내기까지만 수행합니다.
                  </div>
                </section>
              </div>
            </>
          )}
          <footer>
            <span>ORBIT · AI Studio Operating System</span>
            <span>Fictional studio. Real experiments.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
