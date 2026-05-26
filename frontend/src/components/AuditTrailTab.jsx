import React, { useState, useEffect } from 'react';
import { getAuditLogs } from '../api';
import { 
  History, 
  User, 
  FileText, 
  CheckSquare, 
  Flag, 
  Upload, 
  Info, 
  RefreshCw, 
  Search,
  Eye
} from 'lucide-react';

export default function AuditTrailTab() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const res = await getAuditLogs();
      setLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const getActionBadge = (action) => {
    let color = 'bg-gray-800 text-gray-400 border border-gray-700/50';
    let icon = <Info className="w-3.5 h-3.5" />;
    
    if (action === 'approve') {
      color = 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      icon = <CheckSquare className="w-3.5 h-3.5" />;
    } else if (action === 'flag') {
      color = 'bg-red-500/10 text-red-400 border border-red-500/20';
      icon = <Flag className="w-3.5 h-3.5" />;
    } else if (action === 'upload') {
      color = 'bg-blue-500/10 text-blue-400 border border-blue-500/20';
      icon = <Upload className="w-3.5 h-3.5" />;
    }
    
    return (
      <span className={`inline-flex items-center space-x-1 text-2xs font-semibold px-2.5 py-0.5 rounded-lg capitalize ${color}`}>
        {icon}
        <span>{action}</span>
      </span>
    );
  };

  const getTargetType = (log) => {
    if (log.emission_row) return 'Emission Row';
    if (log.ingestion_job) return 'Ingestion Job';
    return 'System';
  };

  const filteredLogs = logs.filter(log => {
    const term = search.toLowerCase();
    const actionMatch = log.action.toLowerCase().includes(term);
    const userMatch = log.user?.username.toLowerCase().includes(term);
    const noteMatch = log.note?.toLowerCase().includes(term);
    return actionMatch || userMatch || noteMatch;
  });

  return (
    <div className="space-y-6">
      {/* Search and Refresh */}
      <div className="glass-card rounded-2xl p-4 flex flex-col sm:flex-row justify-between items-center gap-4">
        <div className="relative w-full sm:max-w-xs">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search audit trail logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded-xl pl-9 pr-4 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 placeholder-gray-600"
          />
        </div>
        <button
          onClick={fetchLogs}
          className="p-2 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors self-end sm:self-auto flex items-center space-x-1.5 text-xs font-semibold"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Reload Timeline</span>
        </button>
      </div>

      {/* Timeline logs */}
      <div className="glass-card rounded-2xl p-6">
        <h4 className="text-lg font-semibold text-white mb-6 flex items-center space-x-2">
          <History className="w-5 h-5 text-blue-400" />
          <span>Append-Only Chronological Audit Log</span>
        </h4>

        {loading ? (
          <div className="py-12 flex justify-center items-center">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="text-center py-12 text-gray-500 text-xs">
            No audit logs found matching terms.
          </div>
        ) : (
          <div className="relative border-l border-gray-800 ml-4 space-y-6">
            {filteredLogs.map((log) => (
              <div key={log.id} className="relative pl-6 group">
                {/* Timeline circle marker */}
                <div className={`absolute -left-2 top-1.5 w-4 h-4 rounded-full border-2 bg-esg-dark ${
                  log.action === 'approve' ? 'border-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.3)]' :
                  log.action === 'flag' ? 'border-red-500 shadow-[0_0_8px_rgba(239,68,68,0.3)]' :
                  'border-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.3)]'
                }`} />

                <div className="bg-gray-900/30 border border-gray-800/40 rounded-2xl p-4 space-y-3 hover:border-gray-800 hover:bg-gray-900/40 transition-all duration-300">
                  <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2">
                    <div className="flex items-center space-x-2.5">
                      {getActionBadge(log.action)}
                      <span className="text-2xs text-gray-400 font-semibold flex items-center space-x-1">
                        <User className="w-3.5 h-3.5" />
                        <span>Analyst: {log.user?.username || 'System Ingest'}</span>
                      </span>
                    </div>
                    <span className="text-3xs text-gray-500 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleString()}
                    </span>
                  </div>

                  {log.note && (
                    <div className="p-3 bg-gray-950/60 rounded-xl border border-gray-900/80 text-xs text-gray-300 italic">
                      "{log.note}"
                    </div>
                  )}

                  {/* Target reference details */}
                  <div className="flex items-center space-x-2 text-2xs text-gray-500">
                    <FileText className="w-3.5 h-3.5 text-gray-600" />
                    <span>Target:</span>
                    <span className="font-semibold text-gray-400 capitalize">{getTargetType(log)}</span>
                    <span className="text-gray-700 font-mono">•</span>
                    <span className="font-mono text-3xs text-gray-600">{log.emission_row || log.ingestion_job || 'Global'}</span>
                  </div>

                  {/* Before / After state payload displays */}
                  {(log.before_value || log.after_value) && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-3xs pt-2 border-t border-gray-850/40">
                      {log.before_value && (
                        <div className="p-2.5 bg-gray-950/30 rounded-lg border border-gray-850/30">
                          <span className="text-gray-500 font-bold block mb-1">State Before Change</span>
                          <div className="space-y-0.5 max-h-24 overflow-y-auto">
                            {Object.entries(log.before_value).map(([k, v]) => (
                              <div key={k} className="flex justify-between font-mono">
                                <span className="text-gray-500">{k}:</span>
                                <span className="text-red-300 truncate pl-2">{v === null ? 'null' : String(v)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {log.after_value && (
                        <div className="p-2.5 bg-gray-950/30 rounded-lg border border-gray-850/30">
                          <span className="text-gray-500 font-bold block mb-1">State After Change</span>
                          <div className="space-y-0.5 max-h-24 overflow-y-auto">
                            {Object.entries(log.after_value).map(([k, v]) => (
                              <div key={k} className="flex justify-between font-mono">
                                <span className="text-gray-500">{k}:</span>
                                <span className="text-emerald-300 truncate pl-2">{v === null ? 'null' : String(v)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
