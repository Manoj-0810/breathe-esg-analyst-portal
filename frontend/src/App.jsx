import React, { useState } from 'react';
import DashboardTab from './components/DashboardTab';
import UploadTab from './components/UploadTab';
import ReviewQueueTab from './components/ReviewQueueTab';
import AuditTrailTab from './components/AuditTrailTab';
import { 
  BarChart3, 
  UploadCloud, 
  ClipboardList, 
  History, 
  Compass, 
  Leaf, 
  User, 
  Calendar 
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  const navigation = [
    { id: 'dashboard', name: 'Analyst Dashboard', icon: <BarChart3 className="w-5 h-5" /> },
    { id: 'upload', name: 'Ingestion Portal', icon: <UploadCloud className="w-5 h-5" /> },
    { id: 'review', name: 'Review Queue', icon: <ClipboardList className="w-5 h-5" /> },
    { id: 'audit', name: 'Audit Trail', icon: <History className="w-5 h-5" /> }
  ];

  return (
    <div className="flex h-screen bg-esg-darker overflow-hidden text-gray-300 antialiased font-sans">
      {/* Sidebar Navigation */}
      <aside className="w-64 glass border-r border-gray-800 flex flex-col justify-between select-none">
        <div>
          {/* Logo */}
          <div className="flex items-center space-x-2.5 px-6 py-6 border-b border-gray-850">
            <div className="p-2 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20">
              <Leaf className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <h1 className="text-md font-extrabold text-white tracking-wider">Breathe ESG</h1>
              <span className="text-3xs text-emerald-400 font-bold uppercase tracking-widest mt-0.5 block">carbon accounting</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="mt-6 px-4 space-y-1">
            {navigation.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                  activeTab === item.id 
                    ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-600/15' 
                    : 'text-gray-400 hover:bg-gray-900/50 hover:text-white'
                }`}
              >
                {item.icon}
                <span>{item.name}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* User Card */}
        <div className="p-4 border-t border-gray-850 bg-gray-950/20">
          <div className="flex items-center space-x-3 p-2 rounded-xl bg-gray-950/40 border border-gray-850/50">
            <div className="w-9 h-9 rounded-full bg-blue-600/10 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <User className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-bold text-white leading-none">Sarah Chen</p>
              <span className="text-3xs text-gray-500 font-medium mt-0.5 block">Senior ESG Analyst</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden bg-esg-darker">
        {/* Top Header */}
        <header className="h-16 border-b border-gray-850 bg-esg-dark flex items-center justify-between px-8 relative z-10">
          <div className="flex items-center space-x-2 text-xs text-gray-400">
            <Compass className="w-4 h-4 text-blue-400" />
            <span className="capitalize font-semibold text-gray-300">
              {navigation.find(n => n.id === activeTab)?.name}
            </span>
          </div>

          <div className="flex items-center space-x-2 text-2xs text-gray-400 bg-gray-950/60 px-3 py-1.5 rounded-xl border border-gray-850/60">
            <Calendar className="w-3.5 h-3.5 text-emerald-400" />
            <span className="font-semibold">{new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
          </div>
        </header>

        {/* Scrollable Tab Container */}
        <div className="flex-1 overflow-y-auto p-8 relative">
          <div className="max-w-6xl mx-auto">
            {activeTab === 'dashboard' && <DashboardTab />}
            {activeTab === 'upload' && <UploadTab />}
            {activeTab === 'review' && <ReviewQueueTab />}
            {activeTab === 'audit' && <AuditTrailTab />}
          </div>
        </div>
      </main>
    </div>
  );
}
