import React, { useState, useEffect } from 'react';
import { getRuns, getRunRows, approveRow, flagRow } from '../api';
import { 
  Check, 
  Flag, 
  Lock, 
  HelpCircle, 
  Search, 
  Filter, 
  AlertTriangle, 
  AlertCircle, 
  Clock, 
  RefreshCw,
  FolderOpen,
  Calendar,
  Layers,
  ChevronRight
} from 'lucide-react';

export default function ReviewQueueTab() {
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submittingId, setSubmittingId] = useState(null);

  // Filter States
  const [sourceFilter, setSourceFilter] = useState('all');
  const [scopeFilter, setScopeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Modal/Note states for action
  const [actioningRowId, setActioningRowId] = useState(null);
  const [actionType, setActionType] = useState(''); // 'approve' or 'flag'
  const [auditNote, setAuditNote] = useState('');
  const [flagReasonInput, setFlagReasonInput] = useState('');

  const fetchRunsList = async () => {
    try {
      const res = await getRuns();
      setRuns(res.data);
      if (res.data.length > 0 && !selectedRunId) {
        setSelectedRunId(res.data[0].id); // Default select latest run
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchRowsList = async (runId) => {
    if (!runId) return;
    try {
      setLoading(true);
      const res = await getRunRows(runId);
      setRows(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRunsList();
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      fetchRowsList(selectedRunId);
    }
  }, [selectedRunId]);

  const handleApprove = async (rowId) => {
    try {
      setSubmittingId(rowId);
      await approveRow(rowId, auditNote);
      setActioningRowId(null);
      setAuditNote('');
      fetchRowsList(selectedRunId); // Reload
    } catch (err) {
      console.error(err);
      alert('Failed to approve row.');
    } finally {
      setSubmittingId(null);
    }
  };

  const handleFlag = async (rowId) => {
    if (!flagReasonInput) {
      alert('A flag reason is required.');
      return;
    }
    try {
      setSubmittingId(rowId);
      await flagRow(rowId, flagReasonInput, auditNote);
      setActioningRowId(null);
      setAuditNote('');
      setFlagReasonInput('');
      fetchRowsList(selectedRunId); // Reload
    } catch (err) {
      console.error(err);
      alert('Failed to flag row.');
    } finally {
      setSubmittingId(null);
    }
  };

  // --- Plain English Formatting Rules ---
  const formatPlainEnglish = (row) => {
    const rawVal = parseFloat(row.raw_value);
    const formattedVal = !isNaN(rawVal) ? rawVal.toLocaleString() : '—';
    const rawUnit = row.raw_unit || '';

    if (row.source_type === 'sap_mm') {
      const materialText = row.source_raw?.material_kurztext || row.source_raw?.material_text || row.material_code || 'Fuel Delivery';
      return `${materialText} — ${formattedVal} ${rawUnit}`;
    }

    if (row.source_type === 'utility_hh') {
      return `Electricity Grid Consumption (MPAN: ${row.mpan || '—'}) — ${formattedVal} kWh`;
    }

    if (row.source_type === 'travel_navan') {
      const cat = row.travel_category || 'Travel Expense';
      if (cat === 'flight') {
        const origin = row.origin_iata || '—';
        const dest = row.destination_iata || '—';
        const cabin = row.cabin_class ? row.cabin_class.charAt(0).toUpperCase() + row.cabin_class.slice(1) : 'Economy';
        return `Flight (${origin} → ${dest}) — ${cabin} Cabin (${formattedVal} km)`;
      }
      if (cat === 'hotel') {
        const country = row.hotel_country || '—';
        const hotelName = row.source_raw?.hotel_name || 'Hotel Stay';
        return `${hotelName} (${country}) — ${row.nights || formattedVal} room nights`;
      }
      if (cat === 'ground_transport' || cat === 'ground' || cat === 'rail') {
        const groundType = row.source_raw?.ground_type || 'Taxi/Train';
        const capitalizedType = groundType.charAt(0).toUpperCase() + groundType.slice(1);
        return `${capitalizedType} Land Travel — ${formattedVal} km`;
      }
      return `${cat.charAt(0).toUpperCase() + cat.slice(1)} Travel Expense — ${formattedVal} ${rawUnit}`;
    }

    return `Ingested Row — ${formattedVal} ${rawUnit}`;
  };

  // Get filtered items
  const filteredRows = rows.filter(row => {
    const matchSource = sourceFilter === 'all' || row.source_type === sourceFilter;
    
    // Scope Filter mapping
    let scopeVal = 'all';
    if (row.scope === '1') scopeVal = '1';
    if (row.scope === '2') scopeVal = '2';
    if (row.scope === '3') scopeVal = '3';
    const matchScope = scopeFilter === 'all' || scopeVal === scopeFilter;

    // Status Filter mapping
    let statusVal = 'pending';
    if (row.is_approved) statusVal = 'approved';
    else if (row.is_flagged) statusVal = 'flagged';
    const matchStatus = statusFilter === 'all' || statusVal === statusFilter;

    return matchSource && matchScope && matchStatus;
  });

  // Calculate quick summary metrics for selected job
  const totalCount = rows.length;
  const approvedCount = rows.filter(r => r.is_approved).length;
  const flaggedCount = rows.filter(r => r.is_flagged).length;
  const pendingCount = totalCount - approvedCount - flaggedCount;

  return (
    <div className="space-y-6">
      {/* Run selector bar */}
      <div className="glass-card rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <FolderOpen className="w-5 h-5 text-blue-400" />
          <span className="text-sm font-semibold text-white">Select Ingestion Run:</span>
          <select
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
            className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 max-w-xs"
          >
            {runs.map(run => (
              <option key={run.id} value={run.id}>
                {run.original_filename} ({new Date(run.uploaded_at).toLocaleDateString()})
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={() => fetchRowsList(selectedRunId)}
          className="p-2 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
          title="Reload rows"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Summary counters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Rows', count: totalCount, color: 'text-white border-gray-800' },
          { label: 'Pending Audit', count: pendingCount, color: 'text-amber-400 border-amber-500/20 bg-amber-500/5' },
          { label: 'Flagged / Blocked', count: flaggedCount, color: 'text-red-400 border-red-500/20 bg-red-500/5' },
          { label: 'Approved', count: approvedCount, color: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5' }
        ].map((c, i) => (
          <div key={i} className={`p-4 border rounded-2xl glass-card text-center ${c.color}`}>
            <span className="text-3xs uppercase tracking-wider text-gray-400 font-semibold block">{c.label}</span>
            <span className="text-2xl font-bold mt-1 block">{c.count}</span>
          </div>
        ))}
      </div>

      {/* Filters bar */}
      <div className="glass-card rounded-2xl p-4 flex flex-wrap gap-4 items-center">
        <div className="flex items-center space-x-2 text-xs text-gray-400">
          <Filter className="w-4 h-4" />
          <span>Filters:</span>
        </div>

        {/* Source filter */}
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Sources</option>
          <option value="sap_mm">SAP MM (Scope 1)</option>
          <option value="utility_hh">Utility Meter (Scope 2)</option>
          <option value="travel_navan">Navan Travel (Scope 3)</option>
        </select>

        {/* Scope filter */}
        <select
          value={scopeFilter}
          onChange={(e) => setScopeFilter(e.target.value)}
          className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Scopes</option>
          <option value="1">Scope 1 — Direct</option>
          <option value="2">Scope 2 — Purchased Energy</option>
          <option value="3">Scope 3 — Value Chain</option>
        </select>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Status</option>
          <option value="pending">Pending Audit</option>
          <option value="approved">Approved</option>
          <option value="flagged">Flagged</option>
        </select>
      </div>

      {/* Main Review Table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        {loading ? (
          <div className="py-12 flex justify-center items-center">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        ) : filteredRows.length === 0 ? (
          <div className="text-center py-12 text-gray-500 text-xs">
            No rows match your active filter criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-2xs uppercase tracking-wider">
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Scope</th>
                  <th className="py-3 px-4">Ledger Item (Plain English)</th>
                  <th className="py-3 px-4">Calculated Carbon</th>
                  <th className="py-3 px-4">Data Quality Flags</th>
                  <th className="py-3 px-4 text-right">Audit Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-850 text-xs text-gray-300">
                {filteredRows.map((row) => {
                  const isApproved = row.is_approved;
                  const isFlagged = row.is_flagged;
                  
                  // estimated flag
                  const isEstimated = row.has_estimated_periods || row.source_raw?.has_estimated_periods === true;
                  // policy flag
                  const isOutOfPolicy = row.source_raw?.policy_status === 'out_of_policy';

                  return (
                    <tr key={row.id} className={`hover:bg-gray-900/10 transition-all ${isApproved ? 'opacity-70' : ''}`}>
                      <td className="py-4 px-4 text-2xs text-gray-500 whitespace-nowrap">
                        {new Date(row.activity_date).toLocaleDateString()}
                      </td>
                      <td className="py-4 px-4 whitespace-nowrap">
                        <span className={`text-2xs font-semibold px-2 py-0.5 rounded ${
                          row.scope === '1' ? 'bg-red-500/10 text-red-400' :
                          row.scope === '2' ? 'bg-amber-500/10 text-amber-400' :
                          'bg-purple-500/10 text-purple-400'
                        }`}>
                          Scope {row.scope || '—'}
                        </span>
                      </td>
                      <td className="py-4 px-4 font-medium text-white max-w-sm">
                        <div>
                          {formatPlainEnglish(row)}
                          {isFlagged && row.flag_reason && (
                            <span className="block text-2xs text-red-400 mt-1 font-normal">
                              ⚠️ Flag Reason: {row.flag_reason}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-4 px-4 whitespace-nowrap">
                        {row.normalized_kgco2e === null ? (
                          <span className="inline-flex items-center space-x-1 text-2xs font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
                            <AlertCircle className="w-3.5 h-3.5" />
                            <span>Needs review</span>
                          </span>
                        ) : (
                          <span className="font-mono font-bold text-white">
                            {parseFloat(row.normalized_kgco2e).toLocaleString(undefined, { minimumFractionDigits: 2 })} <span className="text-3xs font-normal text-gray-500">kgCO2e</span>
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4 whitespace-nowrap">
                        <div className="flex flex-col space-y-1">
                          {/* Estimated readings badge */}
                          {isEstimated && (
                            <span className="inline-flex items-center space-x-1 text-3xs font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                              <AlertTriangle className="w-3 h-3" />
                              <span>Contains estimated readings</span>
                            </span>
                          )}
                          {/* Policy badge */}
                          {isOutOfPolicy && (
                            <span className="inline-flex items-center space-x-1 text-3xs font-semibold text-orange-400 bg-orange-500/10 border border-orange-500/20 px-2 py-0.5 rounded">
                              <AlertCircle className="w-3 h-3" />
                              <span>Out of policy</span>
                            </span>
                          )}
                          {!isEstimated && !isOutOfPolicy && (
                            <span className="text-3xs text-gray-600">Verified metered data</span>
                          )}
                        </div>
                      </td>
                      <td className="py-4 px-4 text-right whitespace-nowrap">
                        {isApproved ? (
                          <span className="inline-flex items-center space-x-1.5 text-2xs font-semibold text-emerald-400 bg-emerald-500/5 px-2.5 py-1 rounded-xl border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.05)]">
                            <Lock className="w-3.5 h-3.5" />
                            <span>Audited & Locked</span>
                          </span>
                        ) : actioningRowId === row.id ? (
                          <div className="bg-gray-950 p-3 rounded-xl border border-gray-800 inline-block text-left min-w-[200px] shadow-2xl relative z-10">
                            <span className="text-3xs uppercase tracking-wider text-gray-400 font-semibold block mb-2">
                              {actionType === 'approve' ? 'Verify Ingestion Row' : 'Flag Ingestion Row'}
                            </span>
                            
                            {actionType === 'flag' && (
                              <input
                                type="text"
                                placeholder="Flag reason (required)"
                                value={flagReasonInput}
                                onChange={(e) => setFlagReasonInput(e.target.value)}
                                className="w-full bg-gray-900 border border-gray-800 rounded px-2.5 py-1 text-xs text-white mb-2 focus:outline-none focus:border-blue-500 placeholder-gray-600"
                              />
                            )}

                            <input
                              type="text"
                              placeholder="Audit trail note (optional)"
                              value={auditNote}
                              onChange={(e) => setAuditNote(e.target.value)}
                              className="w-full bg-gray-900 border border-gray-800 rounded px-2.5 py-1 text-xs text-white mb-3 focus:outline-none focus:border-blue-500 placeholder-gray-600"
                            />

                            <div className="flex justify-end space-x-2 text-2xs">
                              <button
                                onClick={() => setActioningRowId(null)}
                                className="px-2 py-1 text-gray-400 hover:text-white"
                                disabled={submittingId !== null}
                              >
                                Cancel
                              </button>
                              <button
                                onClick={() => actionType === 'approve' ? handleApprove(row.id) : handleFlag(row.id)}
                                className={`px-2 py-1 text-white font-semibold rounded ${
                                  actionType === 'approve' ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-red-600 hover:bg-red-500'
                                }`}
                                disabled={submittingId !== null}
                              >
                                {submittingId !== null ? 'Saving...' : 'Submit'}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="inline-flex space-x-1.5">
                            <button
                              onClick={() => {
                                setActioningRowId(row.id);
                                setActionType('approve');
                              }}
                              className="p-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 text-emerald-400 rounded-lg transition-colors"
                              title="Verify Row"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => {
                                setActioningRowId(row.id);
                                setActionType('flag');
                                setFlagReasonInput(row.flag_reason || '');
                              }}
                              className="p-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 rounded-lg transition-colors"
                              title="Flag Row"
                            >
                              <Flag className="w-4 h-4" />
                            </button>
                          </div>
                        )}
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
