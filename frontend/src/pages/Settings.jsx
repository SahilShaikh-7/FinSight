import React, { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Mail, Send, MessageSquare, Shield } from "lucide-react";

const SUPPORT_EMAIL = "sahil68shaikh68@gmail.com";

export default function Settings() {
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [income, setIncome] = useState(user?.monthly_income || "");
  const [saving, setSaving] = useState(false);

  const [contact, setContact] = useState({ subject: "", message: "", reply_email: user?.email || "" });
  const [sending, setSending] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.patch("/auth/profile", { name, monthly_income: Number(income || 0) });
      await refreshUser();
      toast.success("Profile saved");
    } catch { toast.error("Failed to save"); }
    finally { setSaving(false); }
  };

  const sendContact = async (e) => {
    e.preventDefault();
    if (contact.subject.trim().length < 3) return toast.error("Add a subject (min 3 chars)");
    if (contact.message.trim().length < 10) return toast.error("Message too short (min 10 chars)");
    setSending(true);
    try {
      await api.post("/contact", {
        subject: contact.subject.trim(),
        message: contact.message.trim(),
        reply_email: contact.reply_email?.trim() || undefined,
      });
      toast.success("Message sent — check your email for confirmation");
      setContact({ subject: "", message: "", reply_email: user?.email || "" });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to send");
    } finally { setSending(false); }
  };

  return (
    <div className="space-y-8 fade-up" data-testid="settings-root">
      <div>
        <div className="overline">Settings</div>
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight mt-1">Your profile & support</h1>
      </div>

      <form onSubmit={save} className="card-surface p-6 max-w-2xl space-y-4" data-testid="settings-form">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-lg font-semibold">Profile</h2>
          {user?.is_admin && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: "rgba(0,229,255,0.12)", color: "#00E5FF", border: "1px solid rgba(0,229,255,0.3)" }}>
              <Shield size={10} /> ADMIN
            </span>
          )}
        </div>
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
          <input type="number" inputMode="numeric" value={income} onChange={(e) => setIncome(e.target.value)}
            placeholder="e.g. 30000" data-testid="settings-income-input"
            className="mt-1 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }} />
          <p className="text-xs text-[color:var(--text-muted)] mt-1">Powers your savings rate, Health Score & ₹10k Challenge.</p>
        </div>
        <button type="submit" disabled={saving} data-testid="settings-save-btn" className="btn-primary">
          {saving ? "Saving…" : "Save changes"}
        </button>
      </form>

      <div className="card-surface p-6 max-w-2xl" data-testid="plan-info-card">
        <div className="overline">Plan</div>
        <div className="font-display text-xl mt-2 capitalize">{user?.plan}</div>
        <p className="text-sm text-[color:var(--text-secondary)] mt-2">
          {user?.plan === "free" ? "Upgrade to unlock predictive insights & investment analytics." : "Premium features active."}
        </p>
      </div>

      {/* Contact Support */}
      <div className="card-surface p-6 max-w-2xl" data-testid="contact-section">
        <div className="flex items-center gap-2 mb-1">
          <MessageSquare size={18} className="text-brand" />
          <h2 className="font-display text-lg font-semibold">Contact support</h2>
        </div>
        <p className="text-sm text-[color:var(--text-secondary)]">Questions, bugs, feature requests — we're listening.</p>
        <div className="mt-4 flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Mail size={14} className="text-brand" />
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-brand font-medium" data-testid="support-email-link">{SUPPORT_EMAIL}</a>
        </div>

        <form onSubmit={sendContact} className="mt-5 space-y-3" data-testid="contact-form">
          <div>
            <label className="text-sm">Subject</label>
            <input value={contact.subject} onChange={(e) => setContact({ ...contact, subject: e.target.value })}
              required minLength={3} maxLength={200} data-testid="contact-subject-input"
              placeholder="e.g. Unable to upload CSV"
              className="mt-1 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
              style={{ borderColor: "var(--border)" }} />
          </div>
          <div>
            <label className="text-sm">Reply-to email</label>
            <input type="email" value={contact.reply_email} onChange={(e) => setContact({ ...contact, reply_email: e.target.value })}
              data-testid="contact-reply-email-input"
              className="mt-1 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
              style={{ borderColor: "var(--border)" }} />
            <p className="text-xs text-[color:var(--text-muted)] mt-1">We'll reply here. Defaults to your account email.</p>
          </div>
          <div>
            <label className="text-sm">Message</label>
            <textarea value={contact.message} onChange={(e) => setContact({ ...contact, message: e.target.value })}
              required minLength={10} rows={5} data-testid="contact-message-input"
              placeholder="Tell us what's on your mind…"
              className="mt-1 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)] resize-y"
              style={{ borderColor: "var(--border)" }} />
          </div>
          <button type="submit" disabled={sending} data-testid="contact-submit-btn"
            className="btn-primary inline-flex items-center gap-2">
            <Send size={16} /> {sending ? "Sending…" : "Send message"}
          </button>
        </form>
      </div>
    </div>
  );
}
