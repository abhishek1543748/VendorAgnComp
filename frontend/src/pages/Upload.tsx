import { useState, useCallback, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

interface UploadedDevice {
  id: string;
  filename: string;
  vendor: string;
  os_hint: string | null;
  detection_confidence: number;
  uploaded_at: string;
  duplicate?: boolean;
}

interface ParseResult {
  device_id: string;
  status: string;
  source_lane?: string;
  fields_count?: number;
  message?: string;
}

interface UploadProps {
  onNavigateToFindings?: () => void;
}

export default function Upload({ onNavigateToFindings }: UploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState<string | null>(null);
  const [devices, setDevices] = useState<UploadedDevice[]>([]);
  const [parseResults, setParseResults] = useState<Record<string, ParseResult>>({});
  const [dragActive, setDragActive] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const fetchDevices = async () => {
    try {
      const res = await fetch(`${API_BASE}/devices`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setDevices(data);
        }
      }
    } catch (err) {
      console.error('Failed to fetch existing devices:', err);
    }
  };

  useEffect(() => {
    fetchDevices();
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

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) {
      setFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  const removeFile = (idx: number) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);

    try {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f));

      const res = await fetch(`${API_BASE}/devices/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
      const data = await res.json();
      setDevices(prev => [...prev, ...data.uploaded]);
      setFiles([]);
    } catch (err) {
      console.error('Upload error:', err);
      alert('Upload failed. Is the backend running on port 8000?');
    } finally {
      setUploading(false);
    }
  };

  const handleParse = async (deviceId: string) => {
    setParsing(deviceId);
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/parse`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`Parse failed: ${res.statusText}`);
      const data: ParseResult = await res.json();
      setParseResults(prev => ({ ...prev, [deviceId]: data }));
    } catch (err) {
      console.error('Parse error:', err);
      alert('Parse failed.');
    } finally {
      setParsing(null);
    }
  };

  const confidenceColor = (c: number) => {
    if (c >= 0.8) return 'text-emerald-400';
    if (c >= 0.5) return 'text-amber-400';
    return 'text-red-400';
  };

  const statusBadge = (status: string) => {
    if (status === 'parsed')
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
    if (status === 'needs_llm_fallback')
      return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
    return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  };

  return (
    <div className="space-y-8">
      {/* Upload Zone */}
      <div className="space-y-3">
        <h2 className="text-2xl font-semibold text-white">Upload Configurations</h2>
        <p className="text-slate-400 text-sm">
          Upload network device configuration files for compliance analysis. Supports Cisco IOS, Juniper Junos, Palo Alto, Fortinet, and more.
        </p>
      </div>

      <div
        id="dropzone"
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 ${
          dragActive
            ? 'border-cyan-400 bg-cyan-500/10 scale-[1.01]'
            : 'border-white/15 bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.04]'
        }`}
      >
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <div>
            <p className="text-white font-medium">Drop config files here or click to browse</p>
            <p className="text-slate-500 text-sm mt-1">Supports .txt, .cfg, .conf, .rsc, .json</p>
          </div>
          <div className="flex items-center gap-3">
            <label
              htmlFor="file-input"
              className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-medium rounded-xl cursor-pointer hover:from-cyan-400 hover:to-blue-400 transition-all duration-200 shadow-lg shadow-cyan-500/20"
            >
              Browse Files
            </label>
            <button
              type="button"
              onClick={handleSeedSamples}
              disabled={seeding}
              className="px-5 py-2.5 bg-white/10 hover:bg-white/15 border border-white/20 text-white text-sm font-medium rounded-xl transition-all cursor-pointer disabled:opacity-50"
            >
              {seeding ? 'Loading Samples…' : 'Load Sample Configs'}
            </button>
          </div>
          <input
            id="file-input"
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept=".txt,.cfg,.conf,.rsc,.json,.log"
          />
        </div>
      </div>

      {/* Staged Files */}
      {files.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] overflow-hidden">
          <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
            <h3 className="font-medium text-white">{files.length} file{files.length > 1 ? 's' : ''} staged</h3>
            <button
              id="upload-btn"
              onClick={handleUpload}
              disabled={uploading}
              className="px-5 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-medium rounded-xl disabled:opacity-50 hover:from-cyan-400 hover:to-blue-400 transition-all duration-200 shadow-lg shadow-cyan-500/20 cursor-pointer"
            >
              {uploading ? 'Uploading…' : 'Upload All'}
            </button>
          </div>
          <div className="divide-y divide-white/5">
            {files.map((f, i) => (
              <div key={i} className="px-6 py-3 flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center text-xs text-slate-400 font-mono">
                    {f.name.split('.').pop()?.toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm text-white">{f.name}</p>
                    <p className="text-xs text-slate-500">{(f.size / 1024).toFixed(1)} KB</p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(i)}
                  className="text-slate-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Uploaded Devices */}
      {devices.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Uploaded Devices ({devices.length})</h3>
            {onNavigateToFindings && (
              <button
                onClick={onNavigateToFindings}
                className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-cyan-500/10 cursor-pointer flex items-center gap-1.5"
              >
                <span>View Findings & Reports</span>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            )}
          </div>
          <div className="grid gap-4">
            {devices.map(device => (
              <div
                key={device.id}
                className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 hover:bg-white/[0.05] transition-all duration-200"
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <h4 className="font-medium text-white">{device.filename}</h4>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/20">
                        {device.vendor}
                      </span>
                      {device.duplicate && (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/15 text-amber-300 border border-amber-500/20">
                          Existing Duplicate
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-slate-400">
                      {device.os_hint && <span>OS: {device.os_hint}</span>}
                      <span className={confidenceColor(device.detection_confidence)}>
                        Confidence: {(device.detection_confidence * 100).toFixed(0)}%
                      </span>
                      <span className="text-slate-600 font-mono text-xs">{device.id.slice(0, 8)}…</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {parseResults[device.id] && (
                      <span className={`px-3 py-1 rounded-full text-xs font-medium border ${statusBadge(parseResults[device.id].status)}`}>
                        {parseResults[device.id].status === 'parsed'
                          ? `✓ ${parseResults[device.id].fields_count} fields`
                          : parseResults[device.id].status}
                      </span>
                    )}
                    <button
                      id={`parse-${device.id}`}
                      onClick={() => handleParse(device.id)}
                      disabled={parsing === device.id}
                      className="px-4 py-2 rounded-xl text-sm font-medium bg-white/5 border border-white/10 text-white hover:bg-white/10 transition-all disabled:opacity-50 cursor-pointer"
                    >
                      {parsing === device.id ? 'Parsing…' : 'Parse'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
