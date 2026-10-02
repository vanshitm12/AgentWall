"use client";

import { useEffect, useState } from "react";
import { fetchAPI } from "../../lib/api";

export default function ToolsPage() {
  const [servers, setServers] = useState<any[]>([]);
  const [tools, setTools] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [s, t] = await Promise.all([
        fetchAPI("/servers"),
        fetchAPI(`/tools?${search ? `search=${search}&` : ""}${riskFilter ? `risk=${riskFilter}` : ""}`),
      ]);
      setServers(s);
      setTools(t);
    } catch (err: any) { setError(err.message); }
  };

  useEffect(() => { load(); }, [search, riskFilter]);

  const toggleTool = async (toolId: string, enabled: boolean) => {
    try {
      await fetchAPI(`/tools/${toolId}/${enabled ? "disable" : "enable"}`, { method: "POST" });
      load();
    } catch (err: any) { setError(err.message); }
  };

  const updateRisk = async (toolId: string, risk: string) => {
    try {
      await fetchAPI(`/tools/${toolId}`, {
        method: "PATCH",
        body: JSON.stringify({ risk_classification: risk }),
      });
      load();
    } catch (err: any) { setError(err.message); }
  };

  const scanAll = async () => {
    try {
      await fetchAPI("/discovery/scan", { method: "POST" });
      load();
    } catch (err: any) { setError(err.message); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Tools & Servers</h2>
        <button onClick={scanAll} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium">
          Scan Servers
        </button>
      </div>

      {error && <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 mb-4 text-red-200 text-sm">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {servers.map((s) => (
          <div key={s.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{s.name}</h3>
              <span className={`px-2 py-0.5 rounded text-xs ${
                s.status === "ACTIVE" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"
              }`}>{s.status}</span>
            </div>
            <p className="text-xs text-gray-500 mt-1 font-mono">{s.endpoint}</p>
            <p className="text-xs text-gray-400 mt-1">Trust: {s.trust_level}</p>
          </div>
        ))}
        {servers.length === 0 && <p className="text-gray-500 col-span-3">No servers registered.</p>}
      </div>

      <div className="flex gap-3 mb-4">
        <input
          value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tools..." className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
        />
        <select
          value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">All Risk Levels</option>
          <option value="LOW">LOW</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="HIGH">HIGH</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-gray-400">
              <th className="text-left py-3 px-4">Tool</th>
              <th className="text-left py-3 px-4">Risk</th>
              <th className="text-left py-3 px-4">Audit Level</th>
              <th className="text-left py-3 px-4">Enabled</th>
              <th className="text-left py-3 px-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => (
              <tr key={tool.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-3 px-4">
                  <span className="font-mono text-gray-200">{tool.name}</span>
                  {tool.description && (
                    <p className="text-xs text-gray-500 mt-0.5 truncate max-w-md">{tool.description}</p>
                  )}
                </td>
                <td className="py-3 px-4">
                  <select
                    value={tool.risk_classification}
                    onChange={(e) => updateRisk(tool.id, e.target.value)}
                    className={`bg-transparent text-xs font-medium px-2 py-1 rounded ${riskBadge(tool.risk_classification)}`}
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </td>
                <td className="py-3 px-4 text-xs text-gray-400">{tool.audit_log_level || "DEFAULT"}</td>
                <td className="py-3 px-4">
                  <span className={`text-xs ${tool.enabled ? "text-green-400" : "text-red-400"}`}>
                    {tool.enabled ? "Yes" : "No"}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <button
                    onClick={() => toggleTool(tool.id, tool.enabled)}
                    className={`px-2 py-1 rounded text-xs ${
                      tool.enabled ? "bg-red-900/50 text-red-300 hover:bg-red-900" : "bg-green-900/50 text-green-300 hover:bg-green-900"
                    }`}
                  >
                    {tool.enabled ? "Disable" : "Enable"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {tools.length === 0 && <p className="text-gray-500 p-4">No tools found.</p>}
      </div>
    </div>
  );
}

function riskBadge(risk: string) {
  switch (risk) {
    case "LOW": return "text-green-400";
    case "MEDIUM": return "text-yellow-400";
    case "HIGH": return "text-orange-400";
    case "CRITICAL": return "text-red-400";
    default: return "text-gray-400";
  }
}
