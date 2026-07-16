import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Bot, Loader2 } from "lucide-react";
import { api, type CopilotResponse } from "../lib/api";

const SUGGESTIONS = [
  "Which shelter should we reinforce first, and why?",
  "What happens to Block A if the transformer floods?",
  "How long can the clinic annexe run on stored energy?",
];

/** Grounded copilot. Answers come from the backend's RAG pipeline over live model output. */
export function CopilotPanel() {
  const [question, setQuestion] = useState(SUGGESTIONS[0]);
  const [answer, setAnswer] = useState<CopilotResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await api.copilot(question));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-sidebar-border/30 bg-gradient-to-br from-sidebar via-sidebar to-sidebar-accent">
      <CardHeader>
        <CardTitle className="text-sidebar-foreground flex items-center gap-2">
          <Bot className="size-4" /> Copilot
        </CardTitle>
        <p className="text-xs text-sidebar-foreground/70">
          Answers are grounded in retrieved guidelines plus live model output. Without a
          GROQ_API_KEY the backend returns the grounded evidence instead of prose.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setQuestion(s)}
              className="rounded-full border border-sidebar-border/40 px-3 py-1 text-xs text-sidebar-foreground/80 hover:border-sidebar-primary/50 hover:bg-sidebar-accent/40"
            >
              {s}
            </button>
          ))}
        </div>

        <Textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="Ask about shelter readiness, backup duration, or repair order…"
        />

        <Button onClick={ask} disabled={loading || !question.trim()}>
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Thinking…
            </>
          ) : (
            "Ask"
          )}
        </Button>

        {error && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
            Copilot request failed: {error}
          </div>
        )}

        {answer && (
          <div className="space-y-2 rounded-lg border border-sidebar-border/30 bg-sidebar-accent/30 p-3">
            <p className="whitespace-pre-wrap text-sm text-sidebar-foreground">{answer.answer}</p>
            <div className="flex flex-wrap items-center gap-2 border-t border-sidebar-border/30 pt-2">
              <Badge variant="outline" className="text-xs">
                {answer.llm}
              </Badge>
              <Badge variant="outline" className="text-xs">
                retrieval: {answer.retrieval}
              </Badge>
              {answer.sources.map((s) => (
                <Badge key={s} variant="secondary" className="text-xs">
                  {s}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
