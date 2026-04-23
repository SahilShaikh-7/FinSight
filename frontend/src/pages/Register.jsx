import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    if (password.length < 6) return toast.error("Password must be at least 6 characters");
    setLoading(true);
    try {
      await register(email, password, name);
      toast.success("Account created!");
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Registration failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2" style={{ background: "var(--bg-main)" }}>
      <div className="flex items-center justify-center p-6 md:p-12 order-2 md:order-1">
        <form onSubmit={onSubmit} className="w-full max-w-sm card-surface p-8" data-testid="register-form">
          <h1 className="font-display text-2xl font-bold mb-1">Create account</h1>
          <p className="text-sm text-[color:var(--text-secondary)] mb-6">Free forever. No card required.</p>

          <label className="text-sm font-medium">Name</label>
          <input
            type="text" required data-testid="register-name-input"
            value={name} onChange={(e) => setName(e.target.value)}
            className="mt-1 mb-4 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }}
          />
          <label className="text-sm font-medium">Email</label>
          <input
            type="email" required data-testid="register-email-input"
            value={email} onChange={(e) => setEmail(e.target.value)}
            className="mt-1 mb-4 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }}
          />
          <label className="text-sm font-medium">Password</label>
          <input
            type="password" required minLength={6} data-testid="register-password-input"
            value={password} onChange={(e) => setPassword(e.target.value)}
            className="mt-1 mb-6 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }}
          />
          <button type="submit" disabled={loading} data-testid="register-submit-btn"
            className="btn-primary w-full inline-flex items-center justify-center gap-2 py-3">
            {loading ? "Creating…" : <>Create account <ArrowRight size={16} /></>}
          </button>
          <div className="mt-6 text-sm text-[color:var(--text-secondary)] text-center">
            Already have one? <Link to="/login" className="text-brand font-semibold" data-testid="register-to-login">Login</Link>
          </div>
        </form>
      </div>

      <div className="hidden md:flex flex-col justify-between p-12 order-1 md:order-2 border-l" style={{ borderColor: "var(--border)" }}>
        <Link to="/" className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-md grid place-items-center font-bold text-white" style={{ background: "var(--brand)" }}>₹</div>
          <span className="font-display text-xl font-bold">PaisaIQ</span>
        </Link>
        <div>
          <div className="overline mb-3">Start here</div>
          <h2 className="font-display text-4xl lg:text-5xl font-bold tracking-tight leading-tight">
            Know your <span className="text-brand">score.</span><br />Own your money.
          </h2>
          <p className="mt-4 text-[color:var(--text-secondary)] max-w-sm">Get your Financial Health Score in under 2 minutes.</p>
        </div>
        <div className="text-sm text-[color:var(--text-muted)]">PaisaIQ · INR-native · Made for India</div>
      </div>
    </div>
  );
}
