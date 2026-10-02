"use client";

import { useEffect, useState } from "react";
import { fetchAPI } from "../../lib/api";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const endpoint = statusFilter === "PENDING" ? "/approvals/pending" : `/approvals?status=${statusFilter}`;
      const data = await fetchAPI(endpoint);
      setApprovals(data);
    } catch (err: any) { setError(err.message); }
  };

  useEffect(() => { load(); }, [statusFilter]);
  useEffect(() => {
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [statusFilter]);

  const decide = async (id: string, status: string) => {
    try {
      await fetchAPI(`/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ status, reviewer: "dashboard-admin" }),
      });
      load();
    } catch (err: any) { setError(err.message); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Approvals</h2>
        <div className="flex gap-2">
          {["PENDING", "APPROVED", "REJECTED", "EXECUTED", "EXPIRED"].map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                statusFilter === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
              }`}>{s}</button>
          ))}
        </div>
      </div>

      {error && <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 mb-4 text-red-200 text-sm">{error}</div>}

      <div className="space-y-4">
        {approvals.map((a) => (
          <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-gray-200">{a.tool_name}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusBadge(a.status)}`}>{a.status}</span>
                {a.risk_score !== null && (
                  <span className={`text-xs ${riskColor(a.risk_level)}`}>
                    Risk: {a.risk_score} ({a.risk_level})
                  </span>
                )}
              </div>
              {a.status === "PENDING" && (
                <div className="flex gap-2">
                  <button onClick={() => decide(a.id, "APPROVED")}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-900 hover:bg-green-800 text-green-300">
                    Approve
                  </button>
                  <button onClick={() => decide(a.id, "REJECTED")}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-900 hover:bg-red-800 text-red-300">
                    Reject
                  </button>
                </div>
              )}
            </div>
            <div className="text-xs text-gray-500 space-y-1">
              <p>Agent: {a.agent_id}</p>
              {a.reason && <p>Reason: {a.reason}</p>}
              {a.reviewer && <p>Reviewer: {a.reviewer}</p>}
              <p>Created: {new Date(a.created_at).toLocaleString()}</p>
              {a.expires_at && <p>Expires: {new Date(a.expires_at).toLocaleString()}</p>}
            </div>
            {a.arguments && (
              <pre className="bg-black/30 rounded-lg p-3 text-xs font-mono text-gray-400 mt-3 overflow-x-auto max-h-32">
                {JSON.stringify(a.arguments, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {approvals.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            No {statusFilter.toLowerCase()} approvals.
          </div>
        )}
      </div>
    </div>
  );
}

function statusBadge(s: string) {
  switch (s) {
    case "PENDING": return "bg-yellow-900 text-yellow-300";
    case "APPROVED": return "bg-blue-900 text-blue-300";
    case "REJECTED": return "bg-red-900 text-red-300";
    case "EXECUTED": return "bg-green-900 text-green-300";
    case "EXPIRED": return "bg-gray-800 text-gray-400";
    default: return "bg-gray-800 text-gray-400";
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
