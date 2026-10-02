"use client";

import { useEffect, useState } from "react";
import { fetchAPI } from "../../lib/api";

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", cedar_policy: "", priority: 0, description: "", is_approval: false });
  const [error, setError] = useState<string | null>(null);
  const [validateResult, setValidateResult] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await fetchAPI("/policies");
      setPolicies(data);
    } catch (err: any) { setError(err.message); }
  };

  useEffect(() => { load(); }, []);

  const createPolicy = async () => {
    try {
      setError(null);
      const body: any = {
        name: form.name,
        cedar_policy: form.cedar_policy,
        priority: form.priority,
        description: form.description || undefined,
      };
      if (form.is_approval) body.metadata = { decision: "approval" };
      await fetchAPI("/policies", { method: "POST", body: JSON.stringify(body) });
      setShowCreate(false);
      setForm({ name: "", cedar_policy: "", priority: 0, description: "", is_approval: false });
      load();
    } catch (err: any) { setError(err.message); }
  };

  const deletePolicy = async (id: string) => {
    try {
      await fetchAPI(`/policies/${id}`, { method: "DELETE" });
      load();
    } catch (err: any) { setError(err.message); }
  };

  const togglePolicy = async (id: string, enabled: boolean) => {
    try {
      await fetchAPI(`/policies/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !enabled }),
      });
      load();
    } catch (err: any) { setError(err.message); }
  };

  const validateCedar = async () => {
    try {
      const result = await fetchAPI("/policies/validate", {
        method: "POST",
        body: JSON.stringify({ cedar_policy: form.cedar_policy }),
      });
      setValidateResult(result.valid ? "Valid Cedar policy" : `Invalid: ${result.error}`);
    } catch (err: any) { setValidateResult(`Error: ${err.message}`); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Policies</h2>
        <button onClick={() => setShowCreate(!showCreate)} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium">
          + New Policy
        </button>
      </div>

      {error && <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 mb-4 text-red-200 text-sm">{error}</div>}

      {showCreate && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Create Policy</h3>
          <div className="space-y-3">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Policy name"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
            <textarea value={form.cedar_policy} onChange={(e) => setForm({ ...form, cedar_policy: e.target.value })}
              placeholder={'permit(principal, action == Action::"call", resource == Tool::"github.read_file");'}
              rows={4} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono" />
            <div className="flex gap-4 items-center">
              <div>
                <label className="text-xs text-gray-400">Priority</label>
                <input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 0 })}
                  className="w-24 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm ml-2" />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.is_approval} onChange={(e) => setForm({ ...form, is_approval: e.target.checked })} />
                <span className="text-gray-300">Approval policy</span>
              </label>
            </div>
            {validateResult && (
              <p className={`text-xs ${validateResult.startsWith("Valid") ? "text-green-400" : "text-red-400"}`}>{validateResult}</p>
            )}
            <div className="flex gap-2">
              <button onClick={validateCedar} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm">Validate</button>
              <button onClick={createPolicy} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm">Create</button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {policies.map((p) => (
          <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <h3 className="font-semibold">{p.name}</h3>
                <span className="text-xs text-gray-500">priority: {p.priority}</span>
                {p.metadata?.decision === "approval" && (
                  <span className="px-2 py-0.5 rounded text-xs bg-yellow-900 text-yellow-300">APPROVAL</span>
                )}
                <span className={`px-2 py-0.5 rounded text-xs ${p.enabled ? "bg-green-900 text-green-300" : "bg-gray-800 text-gray-400"}`}>
                  {p.enabled ? "ENABLED" : "DISABLED"}
                </span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => togglePolicy(p.id, p.enabled)}
                  className="px-2 py-1 rounded text-xs bg-gray-800 hover:bg-gray-700 text-gray-300">
                  {p.enabled ? "Disable" : "Enable"}
                </button>
                <button onClick={() => deletePolicy(p.id)} className="px-2 py-1 rounded text-xs bg-red-900/50 hover:bg-red-900 text-red-300">
                  Delete
                </button>
              </div>
            </div>
            {p.description && <p className="text-xs text-gray-400 mb-2">{p.description}</p>}
            <pre className="bg-black/30 rounded-lg p-3 text-xs font-mono text-gray-300 overflow-x-auto">{p.cedar_policy}</pre>
          </div>
        ))}
        {policies.length === 0 && <p className="text-gray-500">No policies configured. Default-deny is active.</p>}
      </div>
    </div>
  );
}
