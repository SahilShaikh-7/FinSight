import React, { useEffect, useState } from "react";
import { api, formatINR } from "../lib/api";
import { Trophy, Sparkles, Share2 } from "lucide-react";
import { toast } from "sonner";

export default function ChallengeCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [celebrate, setCelebrate] = useState(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const r = await api.get("/challenge");
        if (!active) return;
        setData(r.data);
        if (r.data.new_milestones && r.data.new_milestones.length > 0) {
          const m = r.data.new_milestones[r.data.new_milestones.length - 1];
          setCelebrate(m);
          toast.success(`🎉 You unlocked the ₹${m.toLocaleString()} milestone!`);
        }
      } catch (e) { /* ignore */ }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, []);

  const share = async () => {
    if (!data) return;
    const text = `I just saved ${formatINR(data.saved)} with FinSight — India's AI money coach. Join the First ₹10k Challenge!`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "FinSight Challenge", text, url: window.location.origin });
      } else {
        await navigator.clipboard.writeText(text + " " + window.location.origin);
        toast.success("Copied share text to clipboard");
      }
    } catch { /* user cancelled */ }
  };

  if (loading) return null;
  if (!data) return null;

  if (!data.income_set) {
    return (
      <div className="card-surface p-6" data-testid="challenge-card-no-income">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg grid place-items-center" style={{ background: "rgba(255,85,0,0.14)", color: "var(--brand)" }}>
            <Trophy size={20} />
          </div>
          <div>
            <div className="overline">First ₹10k Challenge</div>
            <h3 className="font-display text-lg font-semibold mt-1">Unlock your savings game</h3>
            <p className="text-sm text-[color:var(--text-secondary)] mt-2">Set your monthly income in <a href="/app/settings" className="text-brand font-semibold">Settings</a> to start the challenge and earn milestones at ₹1k, ₹5k, and ₹10k.</p>
          </div>
        </div>
      </div>
    );
  }

  const milestones = data.milestones || [1000, 5000, 10000];
  const achieved = new Set(data.achieved_milestones || []);

  return (
    <div className="card-surface p-6 grain-overlay relative overflow-hidden" data-testid="challenge-card">
      {celebrate && (
        <div className="absolute top-2 right-3 text-xs px-2 py-1 rounded-md font-bold" style={{ background: "var(--brand)", color: "#fff" }}>
          🎉 New: ₹{celebrate.toLocaleString()}
        </div>
      )}
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-lg grid place-items-center shrink-0" style={{ background: "rgba(255,85,0,0.14)", color: "var(--brand)" }}>
          <Trophy size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="overline">First ₹10k Challenge</div>
              <h3 className="font-display text-xl font-semibold mt-1">
                {formatINR(data.saved)} <span className="text-[color:var(--text-secondary)] text-base font-normal">/ {formatINR(data.next_milestone)}</span>
              </h3>
            </div>
            <button onClick={share} data-testid="challenge-share-btn" className="btn-ghost text-sm inline-flex items-center gap-2">
              <Share2 size={14} /> Share
            </button>
          </div>

          {/* Progress bar */}
          <div className="mt-4 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-surface-hover)" }}>
            <div className="h-full transition-all duration-700"
              style={{ width: `${data.progress_pct}%`, background: "linear-gradient(90deg, #FF5500, #00E5FF)" }}
              data-testid="challenge-progress-bar" />
          </div>

          {/* Milestones */}
          <div className="mt-5 grid grid-cols-3 gap-3" data-testid="challenge-milestones">
            {milestones.map((m) => {
              const done = achieved.has(m);
              return (
                <div key={m} className={`p-3 rounded-lg border text-center ${done ? "border-[color:var(--brand)]" : ""}`}
                  style={{ borderColor: done ? "var(--brand)" : "var(--border)", background: done ? "rgba(255,85,0,0.08)" : "transparent" }}
                  data-testid={`milestone-${m}`}>
                  <div className={`font-display font-bold ${done ? "text-brand" : ""}`}>₹{m.toLocaleString()}</div>
                  <div className="text-xs mt-1" style={{ color: done ? "#10B981" : "var(--text-muted)" }}>
                    {done ? "✓ Unlocked" : "Locked"}
                  </div>
                </div>
              );
            })}
          </div>

          {data.is_completed && (
            <div className="mt-4 text-sm text-[color:var(--text-secondary)] flex items-center gap-2">
              <Sparkles size={14} className="text-brand" /> You completed the First ₹10k Challenge — incredible!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
