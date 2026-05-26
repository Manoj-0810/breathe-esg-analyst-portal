import React, { useEffect, useState } from 'react';
import { getDashboardData } from '../api';
import { 
  Activity, 
  ShieldCheck, 
  Layers, 
  Calendar,
  CloudLightning,
  Flame,
  Plane,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';

export default function DashboardTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getDashboardData();
      setData(res.data);
    } catch (err) {
      console.error(err);
      setError('Failed to load dashboard metrics. Ensure Django server is running at http://localhost:8000.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
        <span className="text-gray-400">Fetching carbon statistics...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-950/40 border border-red-900/60 rounded-xl text-red-300 flex items-center space-x-3">
        <AlertTriangle className="w-6 h-6 flex-shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  const { emissions_summary, emissions_by_scope, emissions_by_source, data_quality, monthly_trend } = data;

  const totalIngested = parseFloat(emissions_summary.total_ingested_kgco2e).toFixed(2);
  const totalApproved = parseFloat(emissions_summary.total_approved_kgco2e).toFixed(2);
  const completeness = parseFloat(data_quality.completeness_score_pct).toFixed(1);

  return (
    <div className="space-y-6">
      {/* Upper Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card rounded-2xl p-6 relative overflow-hidden group hover:scale-[1.01] transition-all duration-300">
          <div className="absolute right-0 top-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl -z-10 group-hover:bg-blue-500/20 transition-all duration-500" />
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-medium text-gray-400">Total Ingested Emissions</p>
              <h3 className="text-3xl font-bold mt-2 text-white">
                {parseFloat(totalIngested).toLocaleString()} <span className="text-sm font-normal text-gray-400">kgCO2e</span>
              </h3>
            </div>
            <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400 border border-blue-500/20">
              <Flame className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 text-xs text-gray-400 flex items-center space-x-1">
            <span className="text-blue-400 font-medium">SECR Compliant</span>
            <span>• carbon ledger dataset</span>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-6 relative overflow-hidden group hover:scale-[1.01] transition-all duration-300">
          <div className="absolute right-0 top-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl -z-10 group-hover:bg-emerald-500/20 transition-all duration-500" />
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-medium text-gray-400">Total Approved Emissions</p>
              <h3 className="text-3xl font-bold mt-2 text-white">
                {parseFloat(totalApproved).toLocaleString()} <span className="text-sm font-normal text-gray-400">kgCO2e</span>
              </h3>
            </div>
            <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 text-xs text-gray-400 flex items-center space-x-1">
            <span className="text-emerald-400 font-medium">Audited & Verified</span>
            <span>• ready for ESG export</span>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-6 relative overflow-hidden group hover:scale-[1.01] transition-all duration-300">
          <div className="absolute right-0 top-0 w-32 h-32 bg-purple-500/10 rounded-full blur-3xl -z-10 group-hover:bg-purple-500/20 transition-all duration-500" />
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-medium text-gray-400">Completeness Score</p>
              <h3 className="text-3xl font-bold mt-2 text-white">
                {completeness}%
              </h3>
            </div>
            <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400 border border-purple-500/20">
              <Activity className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div 
              className="bg-purple-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${completeness}%` }}
            />
          </div>
        </div>
      </div>

      {/* Middle Grid — Scope & Source charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Scope Breakdown */}
        <div className="glass-card rounded-2xl p-6">
          <h4 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
            <Layers className="w-5 h-5 text-emerald-400" />
            <span>Scope Analysis (GHG Protocol)</span>
          </h4>
          
          <div className="space-y-4">
            {Object.entries(emissions_by_scope).map(([scope, val]) => {
              const parsedVal = parseFloat(val);
              const percentage = totalIngested > 0 ? ((parsedVal / totalIngested) * 100).toFixed(1) : 0;
              let color = 'bg-blue-500';
              let badge = 'bg-blue-500/10 text-blue-400';
              let desc = '';

              if (scope === 'Scope 1') {
                color = 'bg-red-500';
                badge = 'bg-red-500/10 text-red-400';
                desc = 'Direct combustion (SAP MM)';
              } else if (scope === 'Scope 2') {
                color = 'bg-amber-500';
                badge = 'bg-amber-500/10 text-amber-400';
                desc = 'Purchased electricity (Grid)';
              } else {
                color = 'bg-purple-500';
                badge = 'bg-purple-500/10 text-purple-400';
                desc = 'Corporate travel chain';
              }

              return (
                <div key={scope} className="p-3 bg-gray-900/30 rounded-xl border border-gray-800/40">
                  <div className="flex justify-between items-center mb-1">
                    <div>
                      <span className={`text-xs px-2 py-0.5 rounded-md font-semibold ${badge}`}>{scope}</span>
                      <span className="text-xs text-gray-400 ml-2">{desc}</span>
                    </div>
                    <span className="text-sm font-semibold text-white">
                      {parsedVal.toLocaleString()} kgCO2e ({percentage}%)
                    </span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden mt-2">
                    <div 
                      className={`h-full rounded-full ${color}`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Source breakdown */}
        <div className="glass-card rounded-2xl p-6">
          <h4 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <span>Source Share Breakdown</span>
          </h4>

          <div className="grid grid-cols-3 gap-4 h-full items-center">
            {['sap_mm', 'utility_hh', 'travel_navan'].map((source) => {
              const val = emissions_by_source[source] ? parseFloat(emissions_by_source[source]) : 0;
              const percentage = totalIngested > 0 ? ((val / totalIngested) * 100).toFixed(1) : 0;
              let label = 'SAP MM';
              let icon = <Flame className="w-4 h-4" />;
              let color = 'text-red-400 bg-red-500/10';

              if (source === 'utility_hh') {
                label = 'Utility Meter';
                icon = <CloudLightning className="w-4 h-4" />;
                color = 'text-amber-400 bg-amber-500/10';
              } else if (source === 'travel_navan') {
                label = 'Navan Travel';
                icon = <Plane className="w-4 h-4" />;
                color = 'text-purple-400 bg-purple-500/10';
              }

              return (
                <div key={source} className="flex flex-col items-center justify-center p-4 bg-gray-900/30 border border-gray-800/40 rounded-2xl text-center">
                  <div className={`p-3 rounded-full mb-3 ${color}`}>
                    {icon}
                  </div>
                  <span className="text-xs text-gray-400 font-medium">{label}</span>
                  <span className="text-sm font-semibold text-white mt-1">{percentage}%</span>
                  <span className="text-2xs text-gray-500 mt-0.5">{val.toLocaleString()} kg</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Monthly Chart */}
      <div className="glass-card rounded-2xl p-6">
        <h4 className="text-lg font-semibold text-white mb-6 flex items-center space-x-2">
          <Calendar className="w-5 h-5 text-blue-400" />
          <span>Carbon Ingestion Trend (Monthly kgCO2e)</span>
        </h4>

        {monthly_trend.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-gray-500">
            No processed activity data on record to map trend.
          </div>
        ) : (
          <div>
            <div className="flex items-end justify-between h-48 px-4 border-b border-gray-800">
              {monthly_trend.map((t) => {
                const maxEmissions = Math.max(...monthly_trend.map(x => parseFloat(x.emissions_kgco2e) || 1.0));
                const heightPct = ((parseFloat(t.emissions_kgco2e) / maxEmissions) * 100).toFixed(0);

                return (
                  <div key={t.month} className="flex flex-col items-center flex-1 group">
                    <div className="relative w-full flex justify-center">
                      <span className="absolute -top-8 bg-blue-600 text-white text-3xs px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-all pointer-events-none whitespace-nowrap shadow-lg">
                        {parseFloat(t.emissions_kgco2e).toLocaleString()} kg
                      </span>
                      <div 
                        className="w-12 bg-gradient-to-t from-blue-600 to-indigo-400 rounded-t-lg group-hover:from-blue-500 group-hover:to-indigo-300 transition-all duration-300 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
                        style={{ height: `${Math.max(10, heightPct)}%` }}
                      />
                    </div>
                    <span className="text-3xs text-gray-400 mt-2 font-medium">{t.month}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
