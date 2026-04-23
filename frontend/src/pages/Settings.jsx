import React, { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";

export default function Settings() {
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [income, setIncome] = useState(user?.monthly_income || "");
  const [saving, setSaving] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.patch("/auth/profile", { name, monthly_income: Number(income || 0) });
      await refreshUser();
      toast.success("Saved");
    } catch { toast.error("Failed to save"); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-8 fade-up" data-testid="settings-root">
      <div>
        <div className="overline">Settings</div>
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight mt-1">Your profile</h1>
      </div>

      <form onSubmit={save} className="card-surface p-6 max-w-lg space-y-4" data-testid="settings-form">
        <div>
          <label className="text-sm">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} data-testid="settings-name-input"
            className="mt-1 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }} />
        </div>
        <div>
          <label className="text-sm">Email</label>
          <input disabled value={user?.email} className="mt-1 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none opacity-60" style={{ borderColor: "var(--border)" }} />
        </div>
        <div>
          <label className="text-sm">Monthly income (₹)</label>
          <input type="number" value={income} onChange={(e) => setIncome(e.target.value)}
            placeholder="e.g. 30000" data-testid="settings-income-input"
            className="mt-1 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }} />
          <p className="text-xs text-[color:var(--text-muted)] mt-1">Used to calculate your savings rate & Health Score.</p>
        </div>
        <button type="submit" disabled={saving} data-testid="settings-save-btn" className="btn-primary">
          {saving ? "Saving…" : "Save changes"}
        </button>
      </form>

      <div className="card-surface p-6 max-w-lg" data-testid="plan-info-card">
        <div className="overline">Plan</div>
        <div className="font-display text-xl mt-2 capitalize">{user?.plan}</div>
        <p className="text-sm text-[color:var(--text-secondary)] mt-2">
          {user?.plan === "free" ? "Upgrade to unlock predictive insights & investment analytics." : "Premium features active."}
        </p>
      </div>
    </div>
  );
}
