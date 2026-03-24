"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { IdeaInput } from "./IdeaInput";
import { RefinementChat, ChatMessage } from "./RefinementChat";
import { RefinementSpecPreview } from "./RefinementSpecPreview";
import { SpecReview } from "./SpecReview";
import type { IntegrationCheck } from "./IntegrationStatusBar";
import { apiFetch, ApiError } from "@/lib/api";

type WizardStep = "describe" | "clarify" | "review";

interface QuestionItem {
  text: string;
  choices: string[];
  allow_freeform: boolean;
}

interface SessionInfo {
  sessionId: string;
  completeness: number;
  phase: string;
}

interface QuestionResponse {
  questions: QuestionItem[];
  session: SessionInfo;
  review_ready: boolean;
}

interface DraftResponse {
  yaml: string;
  summary: {
    title: string;
    goal: string;
    deliverables: string[];
    agents: string[];
    acceptance_criteria: string[];
    constraints: string[];
    input_sources: string[];
  };
}

interface LaunchResponse {
  workflow_id: string;
  status: string;
}

interface CreateWorkflowWizardProps {
  persona?: string | null;
}

export function CreateWorkflowWizard({ persona }: CreateWorkflowWizardProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const refineFrom = searchParams.get("refine_from");
  const initialIdea = searchParams.get("idea");
  const autoRefineIdea = searchParams.get("refine");
  const templateName = searchParams.get("template");
  const [step, setStep] = useState<WizardStep>("describe");
  const autoRefineTriggered = useRef(false);
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("claude-sonnet-4-20250514");
  const [error, setError] = useState<string | null>(null);

  // Load user default provider/model from preferences
  useEffect(() => {
    apiFetch<{ preferences: Record<string, string> }>("/api/me/preferences")
      .then((res) => {
        if (res.preferences?.default_provider) setProvider(res.preferences.default_provider);
        if (res.preferences?.default_model) setModel(res.preferences.default_model);
      })
      .catch(() => {});
  }, []);

  // Refinement state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [completeness, setCompleteness] = useState(0);
  const [phase, setPhase] = useState("starting");
  const [isThinking, setIsThinking] = useState(false);
  const [isReviewReady, setIsReviewReady] = useState(false);
  const [questionQueue, setQuestionQueue] = useState<QuestionItem[]>([]);
  const [pendingReviewReady, setPendingReviewReady] = useState(false);

  // Spec review state
  const [specYaml, setSpecYaml] = useState("");
  const [specSummary, setSpecSummary] = useState({
    title: "",
    goal: "",
    deliverables: [] as string[],
    agents: [] as string[],
    acceptanceCriteria: [] as string[],
    constraints: [] as string[],
    inputSources: [] as string[],
  });
  const [isLaunching, setIsLaunching] = useState(false);
  const [integrationChecks, setIntegrationChecks] = useState<IntegrationCheck[]>([]);

  // Context inputs (files + URLs)
  const [contextFiles, setContextFiles] = useState<File[]>([]);
  const [contextUrl, setContextUrl] = useState("");
  const [contextUrls, setContextUrls] = useState<string[]>([]);

  // --- Auto-refine from template selection: skip IdeaInput, go straight to chat ---
  useEffect(() => {
    if (!autoRefineIdea || autoRefineTriggered.current) return;
    autoRefineTriggered.current = true;
    handleDescribe(autoRefineIdea);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefineIdea]);

  // --- Auto-refine from existing spec: skip IdeaInput, go straight to chat ---
  const autoRefineFromSpec = useRef(false);
  useEffect(() => {
    if (!refineFrom || autoRefineFromSpec.current) return;
    autoRefineFromSpec.current = true;
    apiFetch<{ spec_yaml: string; spec_metadata: Record<string, unknown> }>(
      `/api/workflows/${refineFrom}/spec`,
    )
      .then((res) => {
        // Extract only user-facing fields from spec_metadata — NOT the raw
        // YAML, which contains Rooben internals (agent transports, MCP
        // servers, verification config) that pollute the refinement context.
        const meta = (res.spec_metadata ?? {}) as Record<string, unknown>;
        const parts: string[] = [];
        if (meta.title) parts.push(`Title: ${meta.title}`);
        if (meta.goal) parts.push(`Goal: ${meta.goal}`);
        if (meta.context) parts.push(`Context: ${meta.context}`);
        if (Array.isArray(meta.deliverables) && meta.deliverables.length > 0) {
          const names = meta.deliverables.map((d: Record<string, string>) => d.name || d.description || String(d)).join(", ");
          parts.push(`Deliverables: ${names}`);
        }
        if (Array.isArray(meta.acceptance_criteria) && meta.acceptance_criteria.length > 0) {
          const items = meta.acceptance_criteria.map((ac: Record<string, string>) => ac.description || String(ac)).join("; ");
          parts.push(`Acceptance criteria: ${items}`);
        }
        if (Array.isArray(meta.constraints) && meta.constraints.length > 0) {
          const items = meta.constraints.map((c: Record<string, string>) => c.description || String(c)).join("; ");
          parts.push(`Constraints: ${items}`);
        }

        const description = parts.length > 0
          ? "Refine this existing project:\n\n" + parts.join("\n")
          : res.spec_yaml
            ? "Refine this project:\n\n" + res.spec_yaml
            : null;

        if (description) handleDescribe(description);
      })
      .catch(() => {
        // Workflow has no spec — just show normal create flow
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refineFrom]);

  // --- Auto-refine from template: fetch template spec and seed refinement ---
  const autoRefineFromTemplate = useRef(false);
  useEffect(() => {
    if (!templateName || autoRefineFromTemplate.current) return;
    autoRefineFromTemplate.current = true;
    apiFetch<{
      name: string;
      description?: string;
      prefill?: string;
      spec_yaml?: string;
      template_agents?: unknown[];
      template_workflow_hints?: unknown[];
      template_input_sources?: unknown[];
      template_deliverables?: unknown[];
      template_acceptance_criteria?: unknown[];
    }>(
      `/api/extensions/${encodeURIComponent(templateName)}`,
    )
      .then((res) => {
        const specYaml = res.spec_yaml || "";
        const description = res.prefill || res.description || templateName;
        // Start refinement with template context
        setIsThinking(true);
        setStep("clarify");
        apiFetch<QuestionResponse>("/api/refine/start", {
          method: "POST",
          body: JSON.stringify({
            description,
            provider,
            model,
            template_spec_yaml: specYaml,
            template_name: templateName,
          }),
        })
          .then((refineRes) => {
            setSessionId(refineRes.session.sessionId);
            setCompleteness(refineRes.session.completeness);
            setPhase(refineRes.session.phase);
            enqueueQuestions(refineRes.questions, refineRes.review_ready);
          })
          .catch((err) => {
            setError(err instanceof Error ? err.message : "Failed to start from template");
            setStep("describe");
          })
          .finally(() => setIsThinking(false));
      })
      .catch(() => {
        // Template not found — fall back to normal flow
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateName]);

  // --- Helpers to update chat messages ---
  const enqueueQuestions = useCallback(
    (questions: QuestionItem[], reviewReady: boolean) => {
      if (questions.length === 0) {
        if (reviewReady) setIsReviewReady(true);
        return;
      }
      const [first, ...rest] = questions;
      setMessages((prev) => [
        ...prev,
        {
          id: `sys-${Date.now()}-0`,
          role: "system" as const,
          content: first.text,
          choices: first.choices.length > 0 ? first.choices : undefined,
          allowFreeform: first.allow_freeform,
          timestamp: Date.now(),
        },
      ]);
      setQuestionQueue(rest);
      setPendingReviewReady(reviewReady);
    },
    [],
  );

  const addUserMessage = useCallback((answer: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        role: "user" as const,
        content: answer,
        timestamp: Date.now(),
      },
    ]);
  }, []);

  const buildContextInputs = async () => {
    const inputs: { type: string; filename?: string; content_base64?: string; url?: string }[] = [];
    for (const file of contextFiles) {
      const buf = await file.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let binary = "";
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      inputs.push({
        type: "file",
        filename: file.name,
        content_base64: btoa(binary),
      });
    }
    for (const url of contextUrls) {
      inputs.push({ type: "url", url });
    }
    return inputs.length > 0 ? inputs : undefined;
  };

  const handleAddUrl = () => {
    const url = contextUrl.trim();
    if (url && !contextUrls.includes(url)) {
      setContextUrls([...contextUrls, url]);
      setContextUrl("");
    }
  };

  // --- YOLO: build immediately ---
  const handleBuild = async (idea: string) => {
    setIsLaunching(true);
    setError(null);
    try {
      const ci = await buildContextInputs();
      const res = await apiFetch<{ workflow_id: string }>("/api/workflows", {
        method: "POST",
        body: JSON.stringify({
          description: idea,
          provider,
          model,
          context_inputs: ci,
        }),
      });
      // API returns immediately — redirect to workflow detail page
      router.push(`/workflows/${res.workflow_id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError("Database unavailable. Please ensure the backend database is running.");
      } else if (err instanceof ApiError && err.status === 401) {
        setError("API key invalid or expired. Please update it in Settings.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to create workflow");
      }
      setIsLaunching(false);
    }
  };

  const handleExampleLaunch = (idea: string) => {
    handleBuild(idea);
  };

  // --- Refine: guided path ---
  const handleDescribe = async (idea: string) => {
    setError(null);
    setIsThinking(true);
    setStep("clarify");
    try {
      const ci = await buildContextInputs();
      const res = await apiFetch<QuestionResponse>("/api/refine/start", {
        method: "POST",
        body: JSON.stringify({
          description: idea,
          provider,
          model,
          context_inputs: ci,
        }),
      });
      setSessionId(res.session.sessionId);
      setCompleteness(res.session.completeness);
      setPhase(res.session.phase);
      enqueueQuestions(res.questions, res.review_ready);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError("Database unavailable. Please ensure the backend database is running.");
      } else if (err instanceof ApiError && err.status === 401) {
        setError("API key invalid or expired. Please update it in Settings.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to start refinement");
      }
      setStep("describe");
    } finally {
      setIsThinking(false);
    }
  };

  const handleAnswer = async (answer: string) => {
    if (!sessionId) return;
    addUserMessage(answer);

    const lastSystem = [...messages].reverse().find((m) => m.role === "system");
    const answerParts = answer.split(",").map((s) => s.trim()).filter(Boolean);
    const isChoiceSelection =
      lastSystem?.choices &&
      answerParts.length > 0 &&
      answerParts.every((part) => lastSystem.choices!.includes(part));

    if (isChoiceSelection && questionQueue.length > 0) {
      const [next, ...rest] = questionQueue;
      setMessages((prev) => [
        ...prev,
        {
          id: `sys-${Date.now()}-q`,
          role: "system" as const,
          content: next.text,
          choices: next.choices.length > 0 ? next.choices : undefined,
          allowFreeform: next.allow_freeform,
          timestamp: Date.now(),
        },
      ]);
      setQuestionQueue(rest);
      if (rest.length === 0 && pendingReviewReady) {
        setIsReviewReady(true);
        setPendingReviewReady(false);
      }
      return;
    }

    setQuestionQueue([]);
    setPendingReviewReady(false);
    setIsThinking(true);
    setError(null);
    try {
      const res = await apiFetch<QuestionResponse>("/api/refine/answer", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, answer }),
      });
      setCompleteness(res.session.completeness);
      setPhase(res.session.phase);
      if (res.questions.length > 0) {
        enqueueQuestions(res.questions, res.review_ready);
      } else if (res.review_ready) {
        setIsReviewReady(true);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to process answer",
      );
    } finally {
      setIsThinking(false);
    }
  };

  const handleAccept = async () => {
    if (!sessionId) return;
    setIsThinking(true);
    setError(null);
    try {
      const [draftRes, integrationRes] = await Promise.all([
        apiFetch<DraftResponse>("/api/refine/draft", {
          method: "POST",
          body: JSON.stringify({ session_id: sessionId }),
        }),
        apiFetch<{ sources: IntegrationCheck[] }>(
          `/api/refine/integration-check?session_id=${sessionId}`,
        ).catch(() => ({ sources: [] })),
      ]);
      setSpecYaml(draftRes.yaml);
      setSpecSummary({
        title: draftRes.summary.title,
        goal: draftRes.summary.goal,
        deliverables: draftRes.summary.deliverables,
        agents: draftRes.summary.agents,
        acceptanceCriteria: draftRes.summary.acceptance_criteria,
        constraints: draftRes.summary.constraints,
        inputSources: draftRes.summary.input_sources,
      });
      setIntegrationChecks(integrationRes.sources);
      setStep("review");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate draft",
      );
    } finally {
      setIsThinking(false);
    }
  };

  const handleContinue = async () => {
    if (!sessionId) return;
    setIsReviewReady(false);
    setPendingReviewReady(false);
    setIsThinking(true);
    setError(null);
    try {
      const res = await apiFetch<QuestionResponse>("/api/refine/continue", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
      setCompleteness(res.session.completeness);
      setPhase(res.session.phase);
      if (res.questions.length > 0) {
        enqueueQuestions(res.questions, res.review_ready);
      } else if (res.review_ready) {
        setIsReviewReady(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to continue");
    } finally {
      setIsThinking(false);
    }
  };

  const handleLaunch = async () => {
    if (!sessionId) return;
    setIsLaunching(true);
    setError(null);
    try {
      const res = await apiFetch<LaunchResponse>("/api/refine/launch", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
      // API returns immediately — redirect to workflow detail page
      router.push(`/workflows/${res.workflow_id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to launch workflow",
      );
      setIsLaunching(false);
    }
  };

  const handleBack = () => {
    if (step === "review") {
      setStep("clarify");
      setIsReviewReady(true);
    }
  };

  // Provider/model now set from user preferences (loaded via useEffect above)

  return (
    <div>
      {/* Error banner */}
      {error && (
        <div
          className="animate-fade-in"
          style={{
            maxWidth: 640,
            margin: "0 auto 16px",
            padding: "10px 14px",
            borderRadius: 6,
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#dc2626",
            fontFamily: "var(--font-ui)",
            fontSize: 13,
          }}
        >
          {error.includes("Settings") ? (
            <>
              {error.split("Settings").map((part, i, arr) =>
                i < arr.length - 1 ? (
                  <span key={i}>
                    {part}
                    <a
                      href="/settings"
                      style={{ color: "#dc2626", fontWeight: 600, textDecoration: "underline" }}
                    >
                      Settings
                    </a>
                  </span>
                ) : (
                  <span key={i}>{part}</span>
                )
              )}
            </>
          ) : (
            error
          )}
        </div>
      )}

      {/* Step content */}
      {step === "describe" && (
        <div className="animate-fade-in-up">
          <IdeaInput
            onBuild={handleBuild}
            onRefine={handleDescribe}
            onExampleLaunch={handleExampleLaunch}
            isLaunching={isLaunching}
            initialIdea={initialIdea ?? undefined}
          />

          {/* Context inputs — files & URLs */}
          <div
            style={{
              maxWidth: 640,
              margin: "16px auto 0",
              padding: "12px 16px",
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-base)",
            }}
          >
            <div
              style={{
                color: "var(--color-text-secondary)",
                fontFamily: "var(--font-ui)",
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              Attach Context (optional)
            </div>

            {/* File picker */}
            <div className="flex items-center gap-2 mb-2">
              <input
                type="file"
                multiple
                onChange={(e) => {
                  if (e.target.files) {
                    setContextFiles([...contextFiles, ...Array.from(e.target.files)]);
                  }
                }}
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: 12,
                  color: "var(--color-text-secondary)",
                }}
              />
            </div>

            {/* File list */}
            {contextFiles.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {contextFiles.map((f, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded px-2 py-0.5"
                    style={{
                      backgroundColor: "var(--color-surface-2)",
                      border: "1px solid var(--color-border)",
                      fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                      fontSize: 11,
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {f.name}
                    <button
                      onClick={() => setContextFiles(contextFiles.filter((_, j) => j !== i))}
                      style={{ color: "var(--color-text-muted)", cursor: "pointer", border: "none", background: "none", padding: 0, fontSize: 14 }}
                    >
                      x
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* URL input */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={contextUrl}
                onChange={(e) => setContextUrl(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddUrl(); } }}
                placeholder="Add a URL..."
                style={{
                  flex: 1,
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  fontFamily: "var(--font-ui)",
                  fontSize: 12,
                  color: "var(--color-text-primary)",
                  outline: "none",
                }}
              />
              <button
                onClick={handleAddUrl}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-base)",
                  fontFamily: "var(--font-ui)",
                  fontSize: 12,
                  color: "var(--color-text-secondary)",
                  cursor: "pointer",
                }}
              >
                Add
              </button>
            </div>

            {/* URL list */}
            {contextUrls.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {contextUrls.map((url, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded px-2 py-0.5"
                    style={{
                      backgroundColor: "var(--color-surface-2)",
                      border: "1px solid var(--color-border)",
                      fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                      fontSize: 11,
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {url.length > 40 ? url.slice(0, 40) + "..." : url}
                    <button
                      onClick={() => setContextUrls(contextUrls.filter((_, j) => j !== i))}
                      style={{ color: "var(--color-text-muted)", cursor: "pointer", border: "none", background: "none", padding: 0, fontSize: 14 }}
                    >
                      x
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Provider/model configured in Settings page */}
        </div>
      )}

      {step === "clarify" && (
        <div style={{ display: "flex", gap: 16, maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <RefinementChat
              messages={messages}
              completeness={completeness}
              phase={phase}
              onAnswer={handleAnswer}
              onAccept={handleAccept}
              onContinue={handleContinue}
              isThinking={isThinking}
              isReviewReady={isReviewReady}
            />
          </div>
          {completeness >= 0.3 && (
            <div style={{ width: 320, flexShrink: 0 }} className="hidden lg:block">
              <RefinementSpecPreview
                sessionId={sessionId}
                completeness={completeness}
              />
            </div>
          )}
        </div>
      )}

      {step === "review" && (
        <div
          className="animate-fade-in-up"
          style={{ maxWidth: 640, margin: "0 auto" }}
        >
          <SpecReview
            specYaml={specYaml}
            specSummary={specSummary}
            integrationChecks={integrationChecks}
            onLaunch={handleLaunch}
            onBack={handleBack}
            isLaunching={isLaunching}
          />
        </div>
      )}

      {/* Execute step removed — workflows now redirect immediately to /workflows/:id */}
    </div>
  );
}
