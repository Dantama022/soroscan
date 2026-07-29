"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ContractDependencyGraph, { GraphNode, GraphEdge } from "@/components/graph/ContractDependencyGraph";

const mockNodes: GraphNode[] = [
  { id: "Router", label: "Router", status: "healthy" },
  { id: "Vault", label: "Vault", status: "healthy" },
  { id: "Oracle", label: "Oracle", status: "degraded" },
  { id: "Token", label: "Token", status: "healthy" },
  { id: "FeeCollector", label: "FeeCollector", status: "healthy" },
  { id: "Treasury", label: "Treasury", status: "healthy" },
  { id: "PriceFeed", label: "PriceFeed", status: "failed" },
];

const mockEdges: GraphEdge[] = [
  { from: "Router", to: "Vault", calls: 1820 },
  { from: "Router", to: "Oracle", calls: 910 },
  { from: "Vault", to: "Token", calls: 2210 },
  { from: "Vault", to: "FeeCollector", calls: 640 },
  { from: "FeeCollector", to: "Treasury", calls: 620 },
  { from: "Oracle", to: "PriceFeed", calls: 905 },
];

export default function ContractDependenciesPage() {
  const router = useRouter();
  const [layout, setLayout] = useState<"cose" | "breadthfirst" | "circle">("cose");

  const handleNodeClick = (nodeId: string) => {
    // Navigate to contract details page
    router.push(`/contracts/${nodeId}`);
  };

  return (
    <main className="min-h-screen bg-terminal-black p-8 text-terminal-green font-terminal-mono">
      <div className="mx-auto max-w-6xl space-y-6">
        <header>
          <p className="text-xs text-terminal-gray tracking-[0.2em]">[INTERACTIVE_DEPENDENCY_GRAPH]</p>
          <h1 className="text-3xl mt-2">Contract Call Dependency Explorer</h1>
          <p className="text-sm text-terminal-gray mt-2">
            Pan and zoom the graph. Hover over a node to highlight its dependencies. Click a node to view its details.
          </p>
        </header>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-4">
          <aside className="rounded border border-terminal-green/20 p-4 lg:col-span-1 flex flex-col space-y-6">
            <div>
              <h2 className="text-sm text-terminal-gray mb-3 uppercase tracking-widest">Layout</h2>
              <select
                value={layout}
                onChange={(e) => setLayout(e.target.value as any)}
                className="w-full rounded border border-terminal-green/30 bg-black/60 px-3 py-2 text-sm text-terminal-green outline-none focus:border-terminal-green"
              >
                <option value="cose">Force Directed</option>
                <option value="breadthfirst">Hierarchical</option>
                <option value="circle">Circular</option>
              </select>
            </div>

            <div>
              <h2 className="text-sm text-terminal-gray mb-3 uppercase tracking-widest">Legend</h2>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center space-x-2">
                  <div className="h-3 w-3 rounded-full bg-green-400"></div>
                  <span>Healthy</span>
                </li>
                <li className="flex items-center space-x-2">
                  <div className="h-3 w-3 rounded-full bg-yellow-400"></div>
                  <span>Degraded</span>
                </li>
                <li className="flex items-center space-x-2">
                  <div className="h-3 w-3 rounded-full bg-red-400"></div>
                  <span>Failed</span>
                </li>
              </ul>
            </div>
          </aside>

          <div className="lg:col-span-3">
            <ContractDependencyGraph
              nodes={mockNodes}
              edges={mockEdges}
              layout={layout}
              onNodeClick={handleNodeClick}
            />
          </div>
        </section>
      </div>
    </main>
  );
}
