"use client";

import { useEffect, useState } from "react";
import { fetchAPI, fetchHealth } from "../lib/api";

interface AuditStats {
  total_events: number;
  by_decision: Record<string, number>;
  top_tools: { tool_name: string; count: number }[];
  avg_latency_ms: number | null;
}

interface HealthData {
  status: string;
  downstream_servers: number;
  available_tools: number;
}

export default function OverviewPage() {
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, h, a, p, e] = await Promise.all([
          fetchAPI("/audit/stats"),
          fetchHealth(),
          fetchAPI("/agents"),
          fetchAPI("/approvals/pending"),
          fetchAPI("/audit?page_size=10"),
        ]);
        setStats(s);
        setHealth(h);
        setAgents(a);
        setPendingApprovals(p);
        setRecentEvents(e.events || []);
      } catch (err: any) {
        setError(err.message);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Overview</h2>
        {health && (
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
            health.status === "healthy" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"
          }`}>
            {health.status}
          </span>
        )}
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 mb-6 text-red-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard label="Active Agents" value={agents.filter((a) => a.status === "ACTIVE").length} color="text-white" />
        <StatCard label="Blocked Actions" value={stats?.by_decision?.DENY || 0} color="text-red-400" />
        <StatCard label="Pending Approvals" value={pendingApprovals.length} color="text-yellow-400" />
        <StatCard label="Total Events" value={stats?.total_events || 0} color="text-blue-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Decision Breakdown</h3>
          {stats && Object.keys(stats.by_decision).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(stats.by_decision).map(([decision, count]) => (
                <div key={decision} className="flex items-center justify-between">
                  <span className={`text-sm font-medium ${decisionColor(decision)}`}>{decision}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-gray-800 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${decisionBg(decision)}`}
                        style={{ width: `${Math.min(100, (count / stats.total_events) * 100)}%` }}
                      />
                    </div>
                    <span className="text-sm text-gray-400 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No events yet.</p>
          )}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Top Tools</h3>
          {stats?.top_tools && stats.top_tools.length > 0 ? (
            <div className="space-y-2">
              {stats.top_tools.slice(0, 5).map((t: any) => (
                <div key={t.tool_name} className="flex items-center justify-between text-sm">
                  <span className="text-gray-300 font-mono">{t.tool_name}</span>
                  <span className="text-gray-400">{t.count} calls</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No tool calls yet.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <InfoCard label="Downstream Servers" value={health?.downstream_servers ?? 0} />
        <InfoCard label="Available Tools" value={health?.available_tools ?? 0} />
        <InfoCard label="Avg Latency" value={stats?.avg_latency_ms ? `${stats.avg_latency_ms.toFixed(1)}ms` : "—"} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
        {recentEvents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400">
                  <th className="text-left py-2 pr-4">Time</th>
                  <th className="text-left py-2 pr-4">Tool</th>
                  <th className="text-left py-2 pr-4">Decision</th>
                  <th className="text-left py-2 pr-4">Risk</th>
                  <th className="text-left py-2">Latency</th>
                </tr>
              </thead>
              <tbody>
                {recentEvents.map((e: any) => (
                  <tr key={e.id} className="border-b border-gray-800/50">
                    <td className="py-2 pr-4 text-gray-400">{new Date(e.timestamp).toLocaleTimeString()}</td>
                    <td className="py-2 pr-4 font-mono text-gray-300">{e.tool_name}</td>
                    <td className="py-2 pr-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${decisionBadge(e.decision)}`}>
                        {e.decision}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      {e.risk_score !== null ? (
                        <span className={`text-xs ${riskColor(e.risk_level)}`}>
                          {e.risk_score} ({e.risk_level})
                        </span>
                      ) : "—"}
                    </td>
                    <td className="py-2 text-gray-400">{e.latency_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500">No activity yet. Connect an agent to get started.</p>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <p className="text-sm text-gray-400">{label}</p>
      <p className={`text-3xl font-bold mt-2 ${color}`}>{value}</p>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-lg font-semibold text-gray-200 mt-1">{value}</p>
    </div>
  );
}

function decisionColor(d: string) {
  switch (d) {
    case "ALLOW": case "ALLOW_APPROVED": return "text-green-400";
    case "DENY": return "text-red-400";
    case "APPROVAL_REQUIRED": return "text-yellow-400";
    default: return "text-gray-400";
  }
}

function decisionBg(d: string) {
  switch (d) {
    case "ALLOW": case "ALLOW_APPROVED": return "bg-green-500";
    case "DENY": return "bg-red-500";
    case "APPROVAL_REQUIRED": return "bg-yellow-500";
    default: return "bg-gray-500";
  }
}

function decisionBadge(d: string) {
  switch (d) {
    case "ALLOW": return "bg-green-900 text-green-300";
    case "ALLOW_APPROVED": return "bg-green-900 text-green-300";
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
