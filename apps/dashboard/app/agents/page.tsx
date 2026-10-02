"use client";

import { useEffect, useState } from "react";
import { fetchAPI } from "../../lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<any[]>([]);
  const [killStatus, setKillStatus] = useState<Record<string, boolean>>({});
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await fetchAPI("/agents");
      setAgents(data);
      const statuses: Record<string, boolean> = {};
      for (const a of data) {
        try {
          const ks = await fetchAPI(`/killswitch/agent/${a.id}`);
          statuses[a.id] = ks.active;
        } catch { statuses[a.id] = false; }
      }
      setKillStatus(statuses);
    } catch (err: any) { setError(err.message); }
  };

  useEffect(() => { load(); }, []);

  const createAgent = async () => {
    try {
      const data = await fetchAPI("/agents", {
        method: "POST",
        body: JSON.stringify({ name: newName, description: newDesc }),
      });
      setCreatedKey(data.api_key);
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      load();
    } catch (err: any) { setError(err.message); }
  };

  const toggleKillSwitch = async (agentId: string, active: boolean) => {
    try {
      if (active) {
        await fetchAPI(`/killswitch/agent/${agentId}`, { method: "DELETE" });
      } else {
        await fetchAPI(`/killswitch/agent/${agentId}`, {
          method: "POST",
          body: JSON.stringify({ reason: "Manual kill from dashboard" }),
        });
      }
      load();
    } catch (err: any) { setError(err.message); }
  };

  const updateStatus = async (agentId: string, status: string) => {
    try {
      await fetchAPI(`/agents/${agentId}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      load();
    } catch (err: any) { setError(err.message); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Agents</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
        >
          + New Agent
        </button>
      </div>

      {error && <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 mb-4 text-red-200 text-sm">{error}</div>}

      {createdKey && (
        <div className="bg-green-900/50 border border-green-700 rounded-lg p-4 mb-4">
          <p className="text-green-200 text-sm font-medium">Agent created! Save this API key — it won't be shown again:</p>
          <code className="text-green-300 text-sm mt-1 block font-mono bg-black/30 p-2 rounded">{createdKey}</code>
          <button onClick={() => setCreatedKey(null)} className="mt-2 text-xs text-green-400 hover:underline">Dismiss</button>
        </div>
      )}

      {showCreate && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Create Agent</h3>
          <div className="space-y-3">
            <input
              value={newName} onChange={(e) => setNewName(e.target.value)}
              placeholder="Agent name" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
            />
            <input
              value={newDesc} onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description (optional)" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
            />
            <button onClick={createAgent} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm">Create</button>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {agents.map((agent) => (
          <div key={agent.id} className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-semibold">{agent.name}</h3>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    agent.status === "ACTIVE" ? "bg-green-900 text-green-300" :
                    agent.status === "KILLED" ? "bg-red-900 text-red-300" :
                    "bg-yellow-900 text-yellow-300"
                  }`}>{agent.status}</span>
                  {killStatus[agent.id] && (
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-900 text-red-300 animate-pulse">
                      KILL SWITCH
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-400 mt-1">{agent.description || "No description"}</p>
                <p className="text-xs text-gray-500 mt-1 font-mono">ID: {agent.id} | Key: {agent.api_key_prefix}...</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleKillSwitch(agent.id, killStatus[agent.id])}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                    killStatus[agent.id]
                      ? "bg-green-900 hover:bg-green-800 text-green-300"
                      : "bg-red-900 hover:bg-red-800 text-red-300"
                  }`}
                >
                  {killStatus[agent.id] ? "Restore" : "Kill"}
                </button>
                {agent.status === "ACTIVE" ? (
                  <button onClick={() => updateStatus(agent.id, "SUSPENDED")} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-yellow-900 hover:bg-yellow-800 text-yellow-300">
                    Suspend
                  </button>
                ) : agent.status === "SUSPENDED" ? (
                  <button onClick={() => updateStatus(agent.id, "ACTIVE")} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-900 hover:bg-green-800 text-green-300">
                    Activate
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        ))}
        {agents.length === 0 && <p className="text-gray-500">No agents registered.</p>}
      </div>
    </div>
  );
}
