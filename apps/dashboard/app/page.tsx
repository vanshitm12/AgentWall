export default function OverviewPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Overview</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400">Active Agents</p>
          <p className="text-3xl font-bold text-white mt-2">0</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400">Blocked Actions</p>
          <p className="text-3xl font-bold text-red-400 mt-2">0</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400">Pending Approvals</p>
          <p className="text-3xl font-bold text-yellow-400 mt-2">0</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400">Risk Events</p>
          <p className="text-3xl font-bold text-orange-400 mt-2">0</p>
        </div>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
        <p className="text-gray-500">No activity yet. Connect an agent to get started.</p>
      </div>
    </div>
  );
}
