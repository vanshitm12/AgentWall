import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentWall — Security Dashboard",
  description: "Runtime Security Firewall for AI Agents",
};

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/agents", label: "Agents" },
  { href: "/tools", label: "Tools & Servers" },
  { href: "/policies", label: "Policies" },
  { href: "/approvals", label: "Approvals" },
  { href: "/activity", label: "Activity" },
  { href: "/attack-lab", label: "Attack Lab" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <div className="flex min-h-screen">
          <nav className="w-64 bg-gray-900 border-r border-gray-800 p-6 flex flex-col">
            <div className="flex items-center gap-2 mb-8">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">AW</div>
              <h1 className="text-xl font-bold text-white">AgentWall</h1>
            </div>
            <ul className="space-y-1 flex-1">
              {NAV_ITEMS.map((item) => (
                <li key={item.href}>
                  <a
                    href={item.href}
                    className="block px-3 py-2 rounded-lg text-sm text-gray-300 hover:text-white hover:bg-gray-800 transition-colors"
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
            <div className="border-t border-gray-800 pt-4 mt-4">
              <p className="text-xs text-gray-500">AgentWall v0.1.0</p>
              <p className="text-xs text-gray-600">MCP Agent Firewall</p>
            </div>
          </nav>
          <main className="flex-1 p-8 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
