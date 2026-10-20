'use client';

import * as React from 'react';
import { getAccessToken } from '@/lib/auth';
import { EmptyState } from '@/components/ui/empty-state';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const SUGGESTED_FIELDS = [
  'event_type',
  'ledger',
  'event_index',
  'tx_hash',
  'amount',
  'from',
  'to',
  'asset',
  'sender',
  'recipient',
];

type DedupConfig = { enabled: boolean; fields: string[] };

export interface DuplicateRecord {
  id: string;
  contractId: string;
  eventType: string;
  ledger: number;
  txHash: string;
  reason: string;
  timestamp: string;
}

async function apiFetch(path: string, init: RequestInit = {}) {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return body;
}

export default function DedupConfigPage() {
  const [contractId, setContractId] = React.useState('');
  const [config, setConfig] = React.useState<DedupConfig>({ enabled: true, fields: ['event_type', 'tx_hash'] });
  const [selected, setSelected] = React.useState<string[]>(['event_type', 'tx_hash']);
  const [customField, setCustomField] = React.useState('');
  const [testPayload, setTestPayload] = React.useState(
    '{\n  "event_type": "transfer",\n  "ledger": 100,\n  "tx_hash": "abc",\n  "payload": { "amount": 10 }\n}'
  );
  const [testResult, setTestResult] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  // Duplicate records state
  const [duplicateRecords] = React.useState<DuplicateRecord[]>([]);
  const [filterQuery, setFilterQuery] = React.useState('');
  const [recordsLoading] = React.useState(false);
  const [recordsError] = React.useState<string | null>(null);

  const filteredRecords = React.useMemo(() => {
    if (!filterQuery.trim()) return duplicateRecords;
    const q = filterQuery.toLowerCase();
    return duplicateRecords.filter(
      (r) =>
        r.contractId.toLowerCase().includes(q) ||
        r.eventType.toLowerCase().includes(q) ||
        r.txHash.toLowerCase().includes(q) ||
        r.reason.toLowerCase().includes(q)
    );
  }, [duplicateRecords, filterQuery]);

  const loadConfig = async () => {
    if (!contractId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch(`/api/ingest/contracts/${encodeURIComponent(contractId.trim())}/dedup-config/`);
      setConfig(data);
      setSelected(data.fields || []);
      setMessage('Loaded dedup configuration');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load config');
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    if (!contractId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch(`/api/ingest/contracts/${encodeURIComponent(contractId.trim())}/dedup-config/`, {
        method: 'PUT',
        body: JSON.stringify({ enabled: config.enabled, fields: selected }),
      });
      setConfig(data);
      setMessage('Saved dedup configuration');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save config');
    } finally {
      setLoading(false);
    }
  };

  const runTest = async () => {
    if (!contractId.trim()) return;
    setLoading(true);
    setError(null);
    setTestResult(null);
    try {
      const payload = JSON.parse(testPayload);
      const data = await apiFetch(`/api/ingest/contracts/${encodeURIComponent(contractId.trim())}/dedup-test/`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setTestResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleField = (field: string) => {
    setSelected((prev) =>
      prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]
    );
  };

  const addCustom = () => {
    const name = customField.trim();
    if (!name) return;
    setSelected((prev) => (prev.includes(name) ? prev : [...prev, name]));
    setCustomField('');
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6" data-testid="dedup-config-page">
      <div>
        <h1 className="text-base font-mono font-semibold text-green-400">Event Deduplication</h1>
        <p className="text-xs font-mono text-gray-500 mt-0.5">
          Configure which fields make an event unique, then test the fingerprint endpoint.
        </p>
      </div>

      <div className="space-y-3 border border-green-900/40 p-4 bg-black/40">
        <label className="block text-xs font-mono text-gray-400">Contract ID or PK</label>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-gray-950 border border-green-900/50 px-3 py-2 text-sm font-mono text-green-300"
            value={contractId}
            onChange={(e) => setContractId(e.target.value)}
            placeholder="Contract primary key"
            data-testid="dedup-contract-id"
          />
          <button
            type="button"
            onClick={loadConfig}
            disabled={loading}
            className="px-3 py-2 text-xs font-mono border border-green-800 text-green-400 hover:bg-green-900/30"
          >
            Load
          </button>
        </div>

        <label className="flex items-center gap-2 text-xs font-mono text-gray-300">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => setConfig((c) => ({ ...c, enabled: e.target.checked }))}
          />
          Enabled
        </label>

        <div>
          <p className="text-xs font-mono text-gray-400 mb-2">Field selection</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_FIELDS.map((field) => (
              <button
                key={field}
                type="button"
                onClick={() => toggleField(field)}
                className={`px-2 py-1 text-xs font-mono border ${
                  selected.includes(field)
                    ? 'border-green-500 text-green-300 bg-green-900/40'
                    : 'border-gray-700 text-gray-500'
                }`}
              >
                {field}
              </button>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <input
              className="flex-1 bg-gray-950 border border-green-900/50 px-3 py-2 text-sm font-mono text-green-300"
              value={customField}
              onChange={(e) => setCustomField(e.target.value)}
              placeholder="Custom payload field"
            />
            <button
              type="button"
              onClick={addCustom}
              className="px-3 py-2 text-xs font-mono border border-green-800 text-green-400"
            >
              Add
            </button>
          </div>
          <p className="text-xs font-mono text-gray-500 mt-2">Selected: {selected.join(', ') || 'none'}</p>
        </div>

        <button
          type="button"
          onClick={saveConfig}
          disabled={loading}
          className="px-3 py-2 text-xs font-mono border border-green-700 bg-green-950 text-green-300"
          data-testid="dedup-save"
        >
          Save configuration
        </button>
      </div>

      <div className="space-y-3 border border-green-900/40 p-4 bg-black/40">
        <h2 className="text-sm font-mono text-green-400">Testing endpoint</h2>
        <textarea
          className="w-full h-40 bg-gray-950 border border-green-900/50 p-3 text-xs font-mono text-green-200"
          value={testPayload}
          onChange={(e) => setTestPayload(e.target.value)}
          data-testid="dedup-test-payload"
        />
        <button
          type="button"
          onClick={runTest}
          disabled={loading}
          className="px-3 py-2 text-xs font-mono border border-green-800 text-green-400"
          data-testid="dedup-test-run"
        >
          Run dedup test
        </button>
        {testResult && (
          <pre className="text-xs font-mono text-green-200 whitespace-pre-wrap border border-green-900/30 p-3">
            {testResult}
          </pre>
        )}
      </div>

      {/* Duplicate Records Table Section */}
      <div className="space-y-4 border border-green-900/40 p-4 bg-black/40" data-testid="dedup-records-section">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-sm font-mono text-green-400">Duplicate Records Log</h2>
            <p className="text-xs font-mono text-gray-500">Filtered deduplication audit log events</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              className="bg-gray-950 border border-green-900/50 px-3 py-1.5 text-xs font-mono text-green-300 placeholder:text-gray-600 rounded"
              placeholder="Filter duplicate records…"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              data-testid="dedup-filter-input"
            />
            {filterQuery && (
              <button
                type="button"
                onClick={() => setFilterQuery('')}
                className="text-xs font-mono text-gray-400 hover:text-green-300 px-2 py-1"
                data-testid="dedup-reset-filters"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {recordsLoading ? (
          <div className="text-xs font-mono text-gray-500 animate-pulse py-8 text-center" data-testid="dedup-loading">
            Loading deduplication records…
          </div>
        ) : recordsError ? (
          <div className="text-xs font-mono text-red-400 py-4" data-testid="dedup-error">
            {recordsError}
          </div>
        ) : filteredRecords.length === 0 ? (
          <EmptyState
            data-testid="dedup-empty-state"
            variant="terminal"
            title="No duplicate records"
            description="No duplicate records match the current filters."
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
            <table className="w-full text-xs font-mono" data-testid="dedup-table">
              <thead className="bg-gray-950 border-b border-green-900/40">
                <tr className="text-gray-400">
                  <th className="text-left px-3 py-2">Contract</th>
                  <th className="text-left px-3 py-2">Event Type</th>
                  <th className="text-right px-3 py-2">Ledger</th>
                  <th className="text-left px-3 py-2">Tx Hash</th>
                  <th className="text-left px-3 py-2">Reason</th>
                  <th className="text-left px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {filteredRecords.map((r) => (
                  <tr key={r.id} className="border-t border-gray-900 hover:bg-gray-900/40">
                    <td className="px-3 py-2 text-green-300 font-semibold">{r.contractId}</td>
                    <td className="px-3 py-2 text-cyan-400">{r.eventType}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{r.ledger}</td>
                    <td className="px-3 py-2 text-gray-400">{r.txHash}</td>
                    <td className="px-3 py-2 text-yellow-400">{r.reason}</td>
                    <td className="px-3 py-2 text-gray-500">{new Date(r.timestamp).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {message && <p className="text-xs font-mono text-green-500">{message}</p>}
      {error && <p className="text-xs font-mono text-red-400">{error}</p>}
    </div>
  );
}
