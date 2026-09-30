import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentWall — Security Dashboard",
  description: "Runtime Security Firewall for AI Agents",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <div className="flex min-h-screen">
          <nav className="w-64 bg-gray-900 border-r border-gray-800 p-6">
            <h1 className="text-xl font-bold text-white mb-8">
              AgentWall
            </h1>
            <ul className="space-y-2">
              <li>
                <a
                  href="/"
                  className="block px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800"
                >
                  Overview
                </a>
              </li>
              <li>
                <a
                  href="/agents"
                  className="block px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800"
                >
                  Agents
                </a>
              </li>
              <li>
                <a
                  href="/tools"
                  className="block px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800"
                >
                  Tools & Servers
                </a>
              </li>
              <li>
                <a
                  href="/policies"
                  className="block px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800"
                >
                  Policies
                </a>
              </li>
              <li>
                <a
                  href="/approvals"
                  className="block px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800"
                >
                  Approvals
                </a>
              </li>
              <li>
                <a
                  href="/activity"
                  className="block px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800"
                >
                  Activity
                </a>
              </li>
              <li>
                <a
                  href="/attack-lab"
                  className="block px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800"
                >
                  Attack Lab
                </a>
              </li>
            </ul>
          </nav>
          <main className="flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
