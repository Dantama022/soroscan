'use client';

import * as React from 'react';
import { getAccessToken } from '@/lib/auth';
import { EmptyState } from '@/components/ui/empty-state';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ImportRecord {
  id: string;
  filename: string;
  format: string;
  dryRun: boolean;
  total: number;
  created: number;
  updated: number;
  errors: number;
  timestamp: string;
}

export default function ContractsImportPage() {
  const [file, setFile] = React.useState<File | null>(null);
  const [format, setFormat] = React.useState('');
  const [onError, setOnError] = React.useState('rollback');
  const [dryRun, setDryRun] = React.useState(true);
  const [report, setReport] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  // Import history records state
  const [importHistory] = React.useState<ImportRecord[]>([]);
  const [filterQuery, setFilterQuery] = React.useState('');
  const [historyLoading] = React.useState(false);
  const [historyError] = React.useState<string | null>(null);

  const filteredImports = React.useMemo(() => {
    if (!filterQuery.trim()) return importHistory;
    const q = filterQuery.toLowerCase();
    return importHistory.filter(
      (r) =>
        r.filename.toLowerCase().includes(q) ||
        r.format.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q)
    );
  }, [importHistory, filterQuery]);

  const submit = async () => {
    if (!file) {
      setError('Choose a CSV or JSON file first.');
      return;
    }
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const token = getAccessToken();
      const body = new FormData();
      body.append('file', file);
      body.append('dry_run', String(dryRun));
      body.append('on_error', onError);
      if (format) body.append('format', format);

      const res = await fetch(`${API_BASE}/api/ingest/contracts/metadata/bulk-import/`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || JSON.stringify(data) || `Import failed (${res.status})`);
      }
      setReport(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6" data-testid="contracts-import-page">
      <div>
        <h1 className="text-base font-mono font-semibold text-green-400">Bulk Import Metadata</h1>
        <p className="text-xs font-mono text-gray-500 mt-0.5">
          CSV/JSON import with validation, rollback-on-error, and import reporting.
        </p>
      </div>

      <div className="space-y-3 border border-green-900/40 p-4 bg-black/40">
        <input
          type="file"
          accept=".csv,.json,text/csv,application/json"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          data-testid="import-file"
          className="block w-full text-xs font-mono text-gray-300"
        />

        <label className="block text-xs font-mono text-gray-400">
          Format
          <select
            className="mt-1 block w-full bg-gray-950 border border-green-900/50 px-3 py-2 text-sm font-mono text-green-300"
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            <option value="">Auto-detect</option>
            <option value="csv">CSV</option>
            <option value="json">JSON</option>
          </select>
        </label>

        <label className="block text-xs font-mono text-gray-400">
          On error
          <select
            className="mt-1 block w-full bg-gray-950 border border-green-900/50 px-3 py-2 text-sm font-mono text-green-300"
            value={onError}
            onChange={(e) => setOnError(e.target.value)}
          >
            <option value="rollback">Rollback</option>
            <option value="skip">Skip row</option>
          </select>
        </label>

        <label className="flex items-center gap-2 text-xs font-mono text-gray-300">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          Dry run (validate only)
        </label>

        <button
          type="button"
          onClick={submit}
          disabled={loading}
          className="px-3 py-2 text-xs font-mono border border-green-700 bg-green-950 text-green-300"
          data-testid="import-submit"
        >
          {loading ? 'Importing…' : 'Run import'}
        </button>
      </div>

      {error && <p className="text-xs font-mono text-red-400">{error}</p>}
      {report && (
        <pre className="text-xs font-mono text-green-200 whitespace-pre-wrap border border-green-900/30 p-3">
          {report}
        </pre>
      )}

      {/* Import History Table Section */}
      <div className="space-y-4 border border-green-900/40 p-4 bg-black/40" data-testid="contracts-import-section">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-sm font-mono text-green-400">Import History</h2>
            <p className="text-xs font-mono text-gray-500">Recent bulk metadata import operations</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              className="bg-gray-950 border border-green-900/50 px-3 py-1.5 text-xs font-mono text-green-300 placeholder:text-gray-600 rounded"
              placeholder="Filter contract imports…"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              data-testid="import-filter-input"
            />
            {filterQuery && (
              <button
                type="button"
                onClick={() => setFilterQuery('')}
                className="text-xs font-mono text-gray-400 hover:text-green-300 px-2 py-1"
                data-testid="import-reset-filters"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {historyLoading ? (
          <div className="text-xs font-mono text-gray-500 animate-pulse py-8 text-center" data-testid="import-loading">
            Loading contract imports…
          </div>
        ) : historyError ? (
          <div className="text-xs font-mono text-red-400 py-4" data-testid="import-error">
            {historyError}
          </div>
        ) : filteredImports.length === 0 ? (
          <EmptyState
            data-testid="contracts-import-empty"
            variant="terminal"
            title="No contract imports"
            description="No contract imports match the current filters."
            action={
              filterQuery
                ? {
                    label: "Reset filters",
                    onClick: () => setFilterQuery(""),
                    terminalVariant: "primary",
                  }
                : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto rounded border border-green-900/40">
            <table className="w-full text-xs font-mono" data-testid="import-table">
              <thead className="bg-gray-950 border-b border-green-900/40">
                <tr className="text-gray-400">
                  <th className="text-left px-3 py-2">Batch ID</th>
                  <th className="text-left px-3 py-2">File</th>
                  <th className="text-left px-3 py-2">Format</th>
                  <th className="text-left px-3 py-2">Dry Run</th>
                  <th className="text-right px-3 py-2">Created</th>
                  <th className="text-right px-3 py-2">Updated</th>
                  <th className="text-right px-3 py-2">Errors</th>
                  <th className="text-left px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {filteredImports.map((r) => (
                  <tr key={r.id} className="border-t border-gray-900 hover:bg-gray-900/40">
                    <td className="px-3 py-2 text-green-300 font-semibold">{r.id}</td>
                    <td className="px-3 py-2 text-cyan-400 truncate max-w-[120px]">{r.filename}</td>
                    <td className="px-3 py-2 text-gray-300 uppercase">{r.format}</td>
                    <td className="px-3 py-2 text-yellow-400">{r.dryRun ? 'Yes' : 'No'}</td>
                    <td className="px-3 py-2 text-right text-green-400">{r.created}</td>
                    <td className="px-3 py-2 text-right text-blue-400">{r.updated}</td>
                    <td className="px-3 py-2 text-right text-red-400">{r.errors}</td>
                    <td className="px-3 py-2 text-gray-500">{new Date(r.timestamp).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
