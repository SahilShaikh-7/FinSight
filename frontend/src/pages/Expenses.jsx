import React, { useEffect, useRef, useState } from "react";
import { api, formatINR } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Upload, Download } from "lucide-react";

const CATS = [
  "Food & Dining", "Groceries", "Transport", "Shopping", "Entertainment",
  "Bills & Utilities", "Rent", "Education", "Healthcare", "Investments",
  "Transfers", "Travel", "Personal Care", "Other",
];

export default function Expenses() {
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ amount: "", merchant: "", category: "", date: "", notes: "" });
  const [submitting, setSubmitting] = useState(false);
  const [filterCat, setFilterCat] = useState("");
  const fileRef = useRef();

  const load = async () => {
    setLoading(true);
    try {
      const q = filterCat ? `?category=${encodeURIComponent(filterCat)}` : "";
      const r = await api.get(`/expenses${q}`);
      setExpenses(r.data);
    } catch (e) { toast.error("Failed to load expenses"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterCat]);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.amount || Number(form.amount) <= 0) return toast.error("Amount must be > 0");
    setSubmitting(true);
    try {
      const payload = {
        amount: Number(form.amount),
        merchant: form.merchant,
        category: form.category || null,
        date: form.date ? new Date(form.date).toISOString() : null,
        notes: form.notes,
      };
      await api.post("/expenses", payload);
      toast.success("Expense added");
      setForm({ amount: "", merchant: "", category: "", date: "", notes: "" });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    } finally { setSubmitting(false); }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this expense?")) return;
    try {
      await api.delete(`/expenses/${id}`);
      toast.success("Deleted");
      load();
    } catch { toast.error("Failed to delete"); }
  };

  const onCsvUpload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await api.post("/expenses/csv", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Imported ${r.data.inserted} (skipped ${r.data.skipped})`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "CSV upload failed");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const downloadSample = () => {
    const csv = "date,amount,merchant,notes\n" +
      "2026-01-15,250,Swiggy,Dinner\n" +
      "2026-01-16,1200,BigBasket,Weekly groceries\n" +
      "2026-01-16,99,Netflix,Monthly subscription\n";
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "sample_expenses.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8 fade-up" data-testid="expenses-root">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="overline">Expenses</div>
          <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight mt-1">Every rupee, tracked.</h1>
          <p className="text-[color:var(--text-secondary)] mt-2 max-w-xl">Add manually or upload your bank CSV — we auto-categorise everything from Swiggy to Zerodha.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={downloadSample} data-testid="csv-sample-btn" className="btn-ghost inline-flex items-center gap-2 text-sm">
            <Download size={16} /> Sample CSV
          </button>
          <label className="btn-primary inline-flex items-center gap-2 text-sm cursor-pointer" data-testid="csv-upload-btn">
            <Upload size={16} /> Upload CSV
            <input ref={fileRef} type="file" accept=".csv" onChange={onCsvUpload} className="hidden" />
          </label>
        </div>
      </div>

      {/* Quick add */}
      <form onSubmit={onSubmit} className="card-surface p-6" data-testid="expense-add-form">
        <div className="overline mb-4">Quick add</div>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <input required type="number" step="0.01" placeholder="₹ Amount" value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            data-testid="expense-amount-input"
            className="bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }} />
          <input placeholder="Merchant (e.g. Swiggy)" value={form.merchant}
            onChange={(e) => setForm({ ...form, merchant: e.target.value })}
            data-testid="expense-merchant-input"
            className="md:col-span-2 bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }} />
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
            data-testid="expense-category-select"
            className="bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }}>
            <option value="" style={{ background: "#121316" }}>Auto-detect</option>
            {CATS.map((c) => <option key={c} value={c} style={{ background: "#121316" }}>{c}</option>)}
          </select>
          <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })}
            data-testid="expense-date-input"
            className="bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }} />
          <button type="submit" disabled={submitting} data-testid="expense-submit-btn"
            className="btn-primary inline-flex items-center justify-center gap-2">
            <Plus size={16} /> Add
          </button>
        </div>
        <input placeholder="Notes (optional)" value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          data-testid="expense-notes-input"
          className="mt-3 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
          style={{ borderColor: "var(--border)" }} />
      </form>

      {/* Filter */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="overline">Filter</span>
        <select value={filterCat} onChange={(e) => setFilterCat(e.target.value)}
          data-testid="expense-filter-category"
          className="bg-transparent border rounded-lg px-3 py-2 text-sm outline-none"
          style={{ borderColor: "var(--border)" }}>
          <option value="" style={{ background: "#121316" }}>All categories</option>
          {CATS.map((c) => <option key={c} value={c} style={{ background: "#121316" }}>{c}</option>)}
        </select>
      </div>

      {/* List */}
      <div className="card-surface overflow-hidden" data-testid="expenses-list">
        {loading ? (
          <div className="p-8 text-center text-[color:var(--text-secondary)]">Loading…</div>
        ) : expenses.length === 0 ? (
          <div className="p-10 text-center">
            <div className="text-[color:var(--text-secondary)] mb-2">No expenses yet.</div>
            <p className="text-sm text-[color:var(--text-muted)]">Add your first expense above or upload a CSV to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead>
              <tr className="text-left text-[color:var(--text-muted)] border-b" style={{ borderColor: "var(--border)" }}>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Merchant</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium text-right">Amount</th>
                <th className="px-4 py-3 font-medium w-12"></th>
              </tr>
            </thead>
            <tbody>
              {expenses.map((e) => (
                <tr key={e.id} className="border-b hover:bg-[color:var(--bg-surface-hover)]" style={{ borderColor: "var(--border)" }} data-testid={`expense-row-${e.id}`}>
                  <td className="px-4 py-3 text-[color:var(--text-secondary)]">{(e.date || "").slice(0, 10)}</td>
                  <td className="px-4 py-3">{e.merchant || "—"}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-1 rounded-md" style={{ background: "rgba(255,85,0,0.1)", color: "var(--brand)", border: "1px solid rgba(255,85,0,0.25)" }}>
                      {e.category}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">{formatINR(e.amount)}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => onDelete(e.id)} data-testid={`expense-delete-${e.id}`}
                      className="text-[color:var(--text-muted)] hover:text-red-400"><Trash2 size={16} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  );
}
