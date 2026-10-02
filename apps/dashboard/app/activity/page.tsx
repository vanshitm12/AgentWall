"use client";

import { useEffect, useState } from "react";
import { fetchAPI } from "../../lib/api";

export default function ActivityPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [decisionFilter, setDecisionFilter] = useState("");
  const [toolFilter, setToolFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 20;

  const load = async () => {
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (decisionFilter) params.set("decision", decisionFilter);
      if (toolFilter) params.set("tool_name", toolFilter);
      const data = await fetchAPI(`/audit?${params}`);
      setEvents(data.events);
      setTotal(data.total);
    } catch (err: any) { setError(err.message); }
  };

  useEffect(() => { load(); }, [page, decisionFilter, toolFilter]);
  useEffect(() => {
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [page, decisionFilter, toolFilter]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Activity Log</h2>
        <span className="text-sm text-gray-400">{total} events</span>
      </div>

      {error && <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 mb-4 text-red-200 text-sm">{error}</div>}

      <div className="flex gap-3 mb-4">
        <select value={decisionFilter} onChange={(e) => { setDecisionFilter(e.target.value); setPage(1); }}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
          <option value="">All Decisions</option>
          <option value="ALLOW">ALLOW</option>
          <option value="DENY">DENY</option>
          <option value="APPROVAL_REQUIRED">APPROVAL_REQUIRED</option>
          <option value="ALLOW_APPROVED">ALLOW_APPROVED</option>
        </select>
        <input value={toolFilter} onChange={(e) => { setToolFilter(e.target.value); setPage(1); }}
          placeholder="Filter by tool..." className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-gray-400">
              <th className="text-left py-3 px-4">Time</th>
              <th className="text-left py-3 px-4">Tool</th>
              <th className="text-left py-3 px-4">Decision</th>
              <th className="text-left py-3 px-4">Risk</th>
              <th className="text-left py-3 px-4">Latency</th>
              <th className="text-left py-3 px-4">DLP</th>
              <th className="text-left py-3 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer"
                onClick={() => setSelectedEvent(selectedEvent?.id === e.id ? null : e)}>
                <td className="py-2 px-4 text-gray-400 text-xs">{new Date(e.timestamp).toLocaleString()}</td>
                <td className="py-2 px-4 font-mono text-gray-300 text-xs">{e.tool_name}</td>
                <td className="py-2 px-4">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${decisionBadge(e.decision)}`}>{e.decision}</span>
                </td>
                <td className="py-2 px-4">
                  {e.risk_score !== null && (
                    <span className={`text-xs ${riskColor(e.risk_level)}`}>{e.risk_score}</span>
                  )}
                </td>
                <td className="py-2 px-4 text-xs text-gray-400">{e.latency_ms}ms</td>
                <td className="py-2 px-4">
                  {e.metadata?.dlp_findings?.length > 0 && (
                    <span className="px-1.5 py-0.5 rounded text-xs bg-purple-900 text-purple-300">
                      {e.metadata.dlp_findings.length} DLP
                    </span>
                  )}
                </td>
                <td className="py-2 px-4 text-xs text-gray-500">{selectedEvent?.id === e.id ? "▲" : "▼"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length === 0 && <p className="text-gray-500 p-4 text-center">No events found.</p>}
      </div>

      {selectedEvent && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mt-4">
          <h3 className="text-sm font-semibold mb-3">Event Details</h3>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div><span className="text-gray-500">ID:</span> <span className="font-mono">{selectedEvent.id}</span></div>
            <div><span className="text-gray-500">Agent:</span> <span className="font-mono">{selectedEvent.agent_id}</span></div>
            <div><span className="text-gray-500">Session:</span> <span className="font-mono">{selectedEvent.session_id}</span></div>
            <div><span className="text-gray-500">Policy:</span> <span className="font-mono">{selectedEvent.policy_id || "—"}</span></div>
            <div><span className="text-gray-500">Server:</span> <span className="font-mono">{selectedEvent.server_id || "—"}</span></div>
            <div><span className="text-gray-500">Approval:</span> <span className="font-mono">{selectedEvent.approval_id || "—"}</span></div>
          </div>
          {selectedEvent.error && (
            <div className="mt-3">
              <span className="text-xs text-gray-500">Error:</span>
              <p className="text-xs text-red-400 mt-1">{selectedEvent.error}</p>
            </div>
          )}
          {selectedEvent.arguments && (
            <div className="mt-3">
              <span className="text-xs text-gray-500">Arguments:</span>
              <pre className="bg-black/30 rounded p-2 text-xs font-mono text-gray-400 mt-1 overflow-x-auto max-h-40">
                {JSON.stringify(selectedEvent.arguments, null, 2)}
              </pre>
            </div>
          )}
          {selectedEvent.metadata?.dlp_findings?.length > 0 && (
            <div className="mt-3">
              <span className="text-xs text-gray-500">DLP Findings:</span>
              <div className="mt-1 space-y-1">
                {selectedEvent.metadata.dlp_findings.map((f: any, i: number) => (
                  <div key={i} className="text-xs bg-purple-900/30 rounded px-2 py-1">
                    <span className="text-purple-300 font-medium">{f.pattern}</span>
                    <span className="text-gray-400 ml-2">{f.category}</span>
                    <span className={`ml-2 ${f.action === "BLOCK" ? "text-red-400" : f.action === "REDACT" ? "text-yellow-400" : "text-blue-400"}`}>{f.action}</span>
                    {f.field && <span className="text-gray-500 ml-2">in {f.field}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-50">Prev</button>
          <span className="text-sm text-gray-400">Page {page} of {totalPages}</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}
            className="px-3 py-1.5 rounded-lg text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-50">Next</button>
        </div>
      )}
    </div>
  );
}

function decisionBadge(d: string) {
  switch (d) {
    case "ALLOW": case "ALLOW_APPROVED": return "bg-green-900 text-green-300";
    case "DENY": return "bg-red-900 text-red-300";
    case "APPROVAL_REQUIRED": return "bg-yellow-900 text-yellow-300";
    default: return "bg-gray-800 text-gray-300";
  }
}

function riskColor(level: string) {
  switch (level) {
    case "LOW": return "text-green-400";
    case "MEDIUM": return "text-yellow-400";
    case "HIGH": return "text-orange-400";
    case "CRITICAL": return "text-red-400";
    default: return "text-gray-400";
  }
}
