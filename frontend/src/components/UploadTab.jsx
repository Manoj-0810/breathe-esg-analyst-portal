import React, { useState, useEffect } from 'react';
import { ingestFile, getRuns } from '../api';
import { 
  UploadCloud, 
  FileText, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  RefreshCw, 
  HelpCircle,
  Database,
  ArrowRight
} from 'lucide-react';

export default function UploadTab() {
  const [sourceType, setSourceType] = useState('sap_mm');
  const [file, setFile] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const fetchRuns = async () => {
    try {
      setLoadingRuns(true);
      const res = await getRuns();
      setRuns(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingRuns(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
      setError(null);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    try {
      setUploading(true);
      setProgress(15);
      setError(null);

      // Simulated ingestion progress
      const interval = setInterval(() => {
        setProgress(prev => (prev < 90 ? prev + 15 : prev));
      }, 400);

      const res = await ingestFile(sourceType, file, '');
      
      clearInterval(interval);
      setProgress(100);
      setResult(res.data);
      setFile(null);
      fetchRuns(); // Reload list
    } catch (err) {
      console.error(err);
      const errMsg = err.response?.data?.error || 'Failed to parse file. Verify format is correct.';
      setError(errMsg);
    } finally {
      setUploading(false);
    }
  };

  const getSourceLabel = (type) => {
    if (type === 'sap_mm') return 'SAP MM Goods Receipt';
    if (type === 'utility_hh') return 'Stark Electricity HH';
    if (type === 'travel_navan') return 'Navan Travel CSV';
    return type;
  };

  return (
    <div className="space-y-8">
      {/* Upload Block */}
      <div className="glass-card rounded-2xl p-6">
        <h4 className="text-lg font-semibold text-white mb-6">Carbon Data Ingestion Portal</h4>
        
        {/* Source Tabs */}
        <div className="flex space-x-2 p-1 bg-gray-950/80 rounded-xl border border-gray-800 mb-6 max-w-md">
          {['sap_mm', 'utility_hh', 'travel_navan'].map(type => (
            <button
              key={type}
              onClick={() => {
                setSourceType(type);
                setFile(null);
                setResult(null);
                setError(null);
              }}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                sourceType === type 
                  ? 'bg-blue-600 text-white shadow-md' 
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {type === 'sap_mm' ? 'SAP MM' : type === 'utility_hh' ? 'Utility HH' : 'Navan Travel'}
            </button>
          ))}
        </div>

        {/* Dropzone / Upload Form */}
        <form onSubmit={handleUpload} className="space-y-6">
          <div className="border-2 border-dashed border-gray-800 rounded-2xl p-8 hover:border-blue-500/50 transition-colors duration-200 flex flex-col items-center justify-center relative cursor-pointer group bg-gray-900/10">
            <input 
              type="file" 
              onChange={handleFileChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              disabled={uploading}
            />
            <UploadCloud className="w-12 h-12 text-gray-500 group-hover:text-blue-400 transition-colors mb-4" />
            
            {file ? (
              <div className="text-center">
                <p className="text-sm font-semibold text-white mb-1 flex items-center justify-center space-x-2">
                  <FileText className="w-4 h-4 text-blue-400" />
                  <span>{file.name}</span>
                </p>
                <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-sm font-medium text-gray-300">Drag & drop your procurement report or click to browse</p>
                <p className="text-xs text-gray-500 mt-1">
                  {sourceType === 'sap_mm' ? 'ALV export (.txt tab-separated or .csv)' : 
                   sourceType === 'utility_hh' ? 'Stark Energy portal export (.csv)' : 
                   'Navan travel export (.csv)'}
                </p>
              </div>
            )}
          </div>

          {/* Guidelines hint */}
          <div className="p-3 bg-gray-900/30 rounded-xl border border-gray-800/40 text-xs text-gray-400 flex items-start space-x-2">
            <HelpCircle className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <span>
              {sourceType === 'sap_mm' ? 'SAP MM parser negates movement type 102 reversals and normalizes German decimal notations automatically.' :
               sourceType === 'utility_hh' ? 'Utility parser Skip stark headers, melt 48 interval periods and aggregate to daily totals.' :
               'Navan travel parser resolves flights coordinates via Haversine great-circle calculation and flags missing ground distances.'}
            </span>
          </div>

          {/* Progress / Status display */}
          {uploading && (
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-gray-400">
                <span>Ingesting & parsing carbon ledger...</span>
                <span>{progress}%</span>
              </div>
              <div className="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
                <div className="bg-blue-600 h-full rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-950/40 border border-red-900/60 rounded-xl text-red-300 flex items-start space-x-3 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {result && (
            <div className="p-4 bg-emerald-950/30 border border-emerald-900/50 rounded-2xl space-y-3">
              <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-sm">
                <CheckCircle className="w-5 h-5" />
                <span>Ingestion Completed Successfully!</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs mt-2">
                <div className="p-2 bg-gray-900/50 rounded-xl border border-gray-800">
                  <span className="text-gray-400 block">Status</span>
                  <span className="text-white font-semibold capitalize mt-1 block">{result.status}</span>
                </div>
                <div className="p-2 bg-gray-900/50 rounded-xl border border-gray-800">
                  <span className="text-gray-400 block">Total Rows</span>
                  <span className="text-white font-semibold mt-1 block">{result.row_count_total}</span>
                </div>
                <div className="p-2 bg-gray-900/50 rounded-xl border border-gray-800">
                  <span className="text-gray-400 block">Successfully Ingested</span>
                  <span className="text-white font-semibold mt-1 block text-emerald-400">{result.row_count_success}</span>
                </div>
                <div className="p-2 bg-gray-900/50 rounded-xl border border-gray-800">
                  <span className="text-gray-400 block">Errors Found</span>
                  <span className={`font-semibold mt-1 block ${result.row_count_error > 0 ? 'text-red-400' : 'text-gray-400'}`}>
                    {result.row_count_error}
                  </span>
                </div>
              </div>
              
              {result.row_count_error > 0 && result.error_detail && (
                <div className="mt-4 pt-3 border-t border-emerald-900/30">
                  <p className="text-xs font-semibold text-red-300 mb-2">Ingestion Error Details:</p>
                  <div className="max-h-36 overflow-y-auto space-y-2 pr-2">
                    {result.error_detail.map((err, i) => (
                      <div key={i} className="text-2xs bg-red-950/20 border border-red-900/30 p-2 rounded-lg text-red-200">
                        <span className="font-semibold">Row {err.row_number}:</span> {err.error}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {file && !uploading && (
            <button 
              type="submit" 
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white rounded-xl font-semibold transition-all flex items-center justify-center space-x-2 shadow-lg shadow-blue-500/10"
            >
              <span>Ingest Carbon File</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </form>
      </div>

      {/* Ingestion runs list */}
      <div className="glass-card rounded-2xl p-6">
        <div className="flex justify-between items-center mb-6">
          <h4 className="text-lg font-semibold text-white flex items-center space-x-2">
            <Database className="w-5 h-5 text-blue-400" />
            <span>Ingestion Job History</span>
          </h4>
          <button 
            onClick={fetchRuns}
            className="p-2 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
            title="Refresh logs"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {loadingRuns ? (
          <div className="py-8 flex justify-center items-center">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-600" />
          </div>
        ) : runs.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-xs">
            No ingestion jobs found. Upload a file above to register runs.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-2xs uppercase tracking-wider">
                  <th className="py-3 px-4">Job ID</th>
                  <th className="py-3 px-4">Source Type</th>
                  <th className="py-3 px-4">Filename</th>
                  <th className="py-3 px-4">Upload Time</th>
                  <th className="py-3 px-4 text-center">Row Stats</th>
                  <th className="py-3 px-4 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-850 text-xs text-gray-300">
                {runs.map((job) => {
                  let statusBadge = 'bg-gray-800 text-gray-400';
                  if (job.status === 'complete') statusBadge = 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
                  if (job.status === 'failed') statusBadge = 'bg-red-500/10 text-red-400 border border-red-500/20';
                  if (job.status === 'partial') statusBadge = 'bg-amber-500/10 text-amber-400 border border-amber-500/20';

                  return (
                    <tr key={job.id} className="hover:bg-gray-900/20 transition-all">
                      <td className="py-3 px-4 font-mono text-2xs text-gray-500">{job.id.substring(0, 8)}...</td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-white">{getSourceLabel(job.source_type)}</span>
                      </td>
                      <td className="py-3 px-4 text-gray-400 max-w-xs truncate" title={job.original_filename}>
                        {job.original_filename}
                      </td>
                      <td className="py-3 px-4 text-2xs text-gray-500 flex items-center space-x-1 mt-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(job.uploaded_at).toLocaleString()}</span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        {job.row_count_total ? (
                          <div className="inline-flex space-x-1.5 text-2xs">
                            <span className="text-gray-400" title="Success">{job.row_count_success}</span>
                            <span className="text-gray-600">/</span>
                            <span className="text-gray-400" title="Total">{job.row_count_total}</span>
                            {job.row_count_error > 0 && (
                              <span className="text-red-400 font-semibold" title="Failed">({job.row_count_error} Err)</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-600">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className={`text-2xs font-semibold px-2 py-0.5 rounded-md ${statusBadge}`}>
                          {job.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
