import { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

interface Device {
  id: string;
  filename: string;
  vendor: string;
  os_hint: string | null;
  hostname?: string | null;
  model?: string | null;
  serial_number?: string | null;
  firmware_version?: string | null;
}

interface Finding {
  id: string;
  device_id: string;
  control_id: string;
  status: 'pass' | 'fail' | 'needs_review';
  observed_value: string | null;
  severity: string | null;
  remediation_cli: string | null;
  raw_line: string | null;
}

interface FindingsProps {
  onNavigateToUpload?: () => void;
}

export default function Findings({ onNavigateToUpload }: FindingsProps) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null);
  const [selectedDeviceDetails, setSelectedDeviceDetails] = useState<Device | null>(null);
  const [selectedFramework, setSelectedFramework] = useState<string>('CIS');
  const [findings, setFindings] = useState<Finding[]>([]);
  const [evaluating, setEvaluating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  const [frameworks, setFrameworks] = useState<string[]>(['CIS', 'NIST_800_53', 'STIG']);

  const fetchFrameworks = async () => {
    try {
      const res = await fetch(`${API_BASE}/frameworks`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setFrameworks(data);
          if (!data.includes(selectedFramework)) {
            setSelectedFramework(data[0]);
          }
        }
      }
    } catch (err) {
      console.error('Failed to fetch frameworks, using default list:', err);
    }
  };

  const fetchDevices = async () => {
    setLoadingDevices(true);
    setDeviceError(null);
    try {
      const res = await fetch(`${API_BASE}/devices`);
      if (!res.ok) {
        throw new Error(`Failed to fetch devices: HTTP ${res.status}`);
      }
      const data = await res.json();
      if (Array.isArray(data)) {
        setDevices(data);
        if (data.length > 0 && !selectedDevice) {
          setSelectedDevice(data[0].id);
        }
      } else {
        setDevices([]);
      }
    } catch (err) {
      console.error('Failed to fetch devices:', err);
      setDeviceError(
        err instanceof Error ? err.message : 'Failed to connect to backend server at http://localhost:8000'
      );
    } finally {
      setLoadingDevices(false);
    }
  };

  useEffect(() => {
    fetchDevices();
    fetchFrameworks();
  }, []);

  const handleSeedSamples = async () => {
    setSeeding(true);
    try {
      const res = await fetch(`${API_BASE}/devices/seed-samples`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to seed sample devices');
      await fetchDevices();
    } catch (err) {
      console.error('Seeding error:', err);
      alert('Failed to load sample devices. Ensure backend is running.');
    } finally {
      setSeeding(false);
    }
  };

  const fetchFindings = async () => {
    if (!selectedDevice) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/devices/${selectedDevice}/findings`);
      if (!res.ok) throw new Error('Failed to fetch findings');
      const data = await res.json();
      setFindings(data);
    } catch (err) {
      console.error('Fetch findings error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedDevice) {
      const dev = devices.find(d => d.id === selectedDevice) || null;
      setSelectedDeviceDetails(dev);
      fetchFindings();
    } else {
      setSelectedDeviceDetails(null);
      setFindings([]);
    }
  }, [selectedDevice, devices]);

  const handleEvaluate = async () => {
    if (!selectedDevice) return;
    setEvaluating(true);
    try {
      const res = await fetch(
        `${API_BASE}/devices/${selectedDevice}/evaluate?framework=${selectedFramework}`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error(`Evaluate failed: ${res.statusText}`);
      await fetchFindings();
    } catch (err) {
      console.error('Evaluation error:', err);
      alert('Evaluation failed.');
    } finally {
      setEvaluating(false);
    }
  };

  const handleDownloadPdf = () => {
    if (!selectedDevice) return;
    const reportUrl = `${API_BASE}/devices/${selectedDevice}/report.pdf`;
    window.open(reportUrl, '_blank');
  };

  const statusStyle = (s: string) => {
    if (s === 'pass') return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
    if (s === 'fail') return 'bg-red-500/20 text-red-300 border-red-500/30';
    return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
  };

  const severityStyle = (s: string | null) => {
    if (s === 'critical') return 'text-red-400';
    if (s === 'high') return 'text-orange-400';
    if (s === 'medium') return 'text-amber-400';
    return 'text-slate-400';
  };

  const passCount = findings.filter(f => f.status === 'pass').length;
  const failCount = findings.filter(f => f.status === 'fail').length;
  const reviewCount = findings.filter(f => f.status === 'needs_review').length;

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h2 className="text-2xl font-semibold text-white">Compliance Findings & PDF Reports</h2>
        <p className="text-slate-400 text-sm">
          Select a device and compliance framework to evaluate rules and export official PDF reports.
        </p>
      </div>

      {/* Connection Error Banner */}
      {deviceError && (
        <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-300 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-white">Backend Connection Issue</p>
              <p className="text-xs text-red-300/80 mt-0.5">{deviceError}. Make sure FastAPI is running on port 8000.</p>
            </div>
          </div>
          <button
            onClick={fetchDevices}
            className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 rounded-lg text-xs font-medium text-white transition-colors cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* No Devices Notice Banner */}
      {!loadingDevices && !deviceError && devices.length === 0 && (
        <div className="p-5 rounded-2xl border border-amber-500/30 bg-amber-500/10 text-amber-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-white">No devices found in database</p>
              <p className="text-xs text-slate-300 mt-0.5">
                Upload network configuration files first or load sample Cisco & Juniper devices to test immediately.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onNavigateToUpload && (
              <button
                onClick={onNavigateToUpload}
                className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-cyan-500/10 cursor-pointer"
              >
                Go to Upload
              </button>
            )}
            <button
              onClick={handleSeedSamples}
              disabled={seeding}
              className="px-4 py-2 bg-white/10 hover:bg-white/15 border border-white/20 text-white text-xs font-semibold rounded-xl transition-all disabled:opacity-50 cursor-pointer"
            >
              {seeding ? 'Loading Samples…' : 'Load Sample Devices'}
            </button>
          </div>
        </div>
      )}

      {/* Control Toolbar */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Target Device</label>
                <button
                  onClick={fetchDevices}
                  disabled={loadingDevices}
                  title="Refresh device list"
                  className="text-slate-400 hover:text-cyan-400 text-xs flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <svg className={`w-3.5 h-3.5 ${loadingDevices ? 'animate-spin text-cyan-400' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span>{loadingDevices ? 'Loading' : 'Refresh'}</span>
                </button>
              </div>
              <select
                id="device-select"
                value={selectedDevice || ''}
                onChange={e => setSelectedDevice(e.target.value || null)}
                disabled={loadingDevices || devices.length === 0}
                className="block px-4 py-2.5 rounded-xl bg-slate-900 border border-white/15 text-white text-sm focus:outline-none focus:border-cyan-500/50 min-w-[280px] disabled:opacity-60"
              >
                {loadingDevices ? (
                  <option value="">Loading devices…</option>
                ) : devices.length === 0 ? (
                  <option value="">No devices available — upload one first</option>
                ) : (
                  <>
                    <option value="">Select a device…</option>
                    {devices.map(d => (
                      <option key={d.id} value={d.id}>
                        {d.filename} ({d.vendor ? d.vendor.toUpperCase() : 'UNKNOWN'}{d.hostname ? ` - ${d.hostname}` : ''})
                      </option>
                    ))}
                  </>
                )}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Compliance Framework</label>
              <select
                id="framework-select"
                value={selectedFramework}
                onChange={e => setSelectedFramework(e.target.value)}
                className="block px-4 py-2.5 rounded-xl bg-slate-900 border border-white/15 text-white text-sm focus:outline-none focus:border-cyan-500/50"
              >
                {frameworks.map(f => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>

            <button
              id="evaluate-btn"
              onClick={handleEvaluate}
              disabled={!selectedDevice || evaluating}
              className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-medium rounded-xl disabled:opacity-50 hover:from-cyan-400 hover:to-blue-400 transition-all duration-200 shadow-lg shadow-cyan-500/20 cursor-pointer flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {evaluating ? 'Evaluating…' : 'Evaluate Rules'}
            </button>
          </div>

          {/* Action: Export PDF */}
          <button
            id="download-pdf-btn"
            onClick={handleDownloadPdf}
            disabled={!selectedDevice}
            className="px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-sm font-medium rounded-xl disabled:opacity-40 hover:from-emerald-400 hover:to-teal-500 transition-all duration-200 shadow-lg shadow-emerald-500/20 cursor-pointer flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Export PDF Report
          </button>
        </div>

        {/* Selected Device Metadata Badge */}
        {selectedDeviceDetails && (
          <div className="pt-4 border-t border-white/10 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs text-slate-300">
            <div>
              <span className="text-slate-500 block">Hostname</span>
              <span className="font-semibold text-white">{selectedDeviceDetails.hostname || 'Not Parsed'}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Model</span>
              <span className="font-semibold text-white">{selectedDeviceDetails.model || 'Not Parsed'}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Firmware</span>
              <span className="font-semibold text-white">{selectedDeviceDetails.firmware_version || 'Not Parsed'}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Vendor / OS</span>
              <span className="font-semibold text-cyan-300">{selectedDeviceDetails.vendor || 'N/A'} ({selectedDeviceDetails.os_hint || 'N/A'})</span>
            </div>
          </div>
        )}
      </div>

      {/* Summary Stats */}
      {findings.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-5 text-center">
            <p className="text-3xl font-bold text-emerald-400">{passCount}</p>
            <p className="text-sm text-emerald-300/70 mt-1">Passed Controls</p>
          </div>
          <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-5 text-center">
            <p className="text-3xl font-bold text-red-400">{failCount}</p>
            <p className="text-sm text-red-300/70 mt-1">Failed Controls</p>
          </div>
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5 text-center">
            <p className="text-3xl font-bold text-amber-400">{reviewCount}</p>
            <p className="text-sm text-amber-300/70 mt-1">Needs Review</p>
          </div>
        </div>
      )}

      {/* Findings Table */}
      {loading ? (
        <p className="text-slate-500 text-center py-12">Loading findings…</p>
      ) : findings.length > 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left">
                <th className="px-6 py-4 text-xs font-medium text-slate-400 uppercase tracking-wider">Control</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-400 uppercase tracking-wider">Severity</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-400 uppercase tracking-wider">Observed Value</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-400 uppercase tracking-wider">Remediation Path</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {findings.map(f => (
                <tr key={f.id} className="hover:bg-white/[0.03] transition-colors">
                  <td className="px-6 py-4 font-mono text-white">{f.control_id}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${statusStyle(f.status)}`}>
                      {f.status}
                    </span>
                  </td>
                  <td className={`px-6 py-4 font-medium ${severityStyle(f.severity)}`}>
                    {f.severity}
                  </td>
                  <td className="px-6 py-4 text-slate-300 max-w-[200px] truncate">{f.observed_value || '—'}</td>
                  <td className="px-6 py-4">
                    {f.remediation_cli ? (
                      <code className="text-xs bg-slate-900 text-cyan-300 px-2.5 py-1 rounded-md border border-cyan-500/20 font-mono">
                        {f.remediation_cli}
                      </code>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : selectedDevice ? (
        <div className="text-center py-16 text-slate-500 rounded-2xl border border-dashed border-white/10">
          <p className="text-slate-400">No evaluation findings recorded for this device yet.</p>
          <p className="text-xs mt-1 text-slate-500">Select a framework above and click <strong>Evaluate Rules</strong>.</p>
        </div>
      ) : (
        <div className="text-center py-16 text-slate-500 rounded-2xl border border-dashed border-white/10">
          <p className="text-slate-400">Select a device from the dropdown above to manage findings and download PDF reports.</p>
        </div>
      )}
    </div>
  );
}
