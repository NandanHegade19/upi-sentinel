import { useState } from 'react';
import { Panel, Group, Separator } from 'react-resizable-panels';
import { LayoutDashboard, ShieldCheck, UserCircle, BarChart3 } from 'lucide-react';
import { useDispatch, useSelector, Provider } from 'react-redux';
import NetworkGraph from './components/NetworkGraph';
import LiveQueue from './components/LiveQueue';
import Copilot from './components/Copilot';
import UnifiedOpsView from './components/UnifiedOpsView';
import { AdminBIDashboard } from './components/AdminBIDashboard';
import { store, type RootState, setUserRole } from './store/opsSlice';

type ViewState = 'DASHBOARD' | 'OPS_CONSOLE' | 'ADMIN_BI';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

function MainLayout() {
  const [activeView, setActiveView] = useState<ViewState>('DASHBOARD');
  const dispatch = useDispatch();
  const { userRole } = useSelector((state: RootState) => state.ops);

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: 'var(--bg-dark)' }}>
      
      {/* SIDEBAR NAVIGATION */}
      <div style={{ 
        width: '240px', 
        backgroundColor: 'var(--bg-panel)', 
        borderRight: '1px solid var(--border-color)', 
        display: 'flex', 
        flexDirection: 'column' 
      }}>
        <div style={{ padding: '20px', fontSize: '18px', fontWeight: 'bold', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldCheck color="#3b82f6" />
          UPI Sentinel
        </div>
        
        <div style={{ flex: 1, padding: '16px 8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button 
            onClick={() => setActiveView('DASHBOARD')}
            style={{ 
              display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 16px', 
              borderRadius: '8px', border: 'none', cursor: 'pointer', textAlign: 'left',
              backgroundColor: activeView === 'DASHBOARD' ? 'var(--bg-hover)' : 'transparent',
              color: activeView === 'DASHBOARD' ? '#3b82f6' : '#e2e8f0',
              fontWeight: activeView === 'DASHBOARD' ? 'bold' : 'normal'
            }}
          >
            <LayoutDashboard size={18} /> Copilot Dashboard
          </button>
          
          <button 
            onClick={() => setActiveView('OPS_CONSOLE')}
            style={{ 
              display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 16px', 
              borderRadius: '8px', border: 'none', cursor: 'pointer', textAlign: 'left',
              backgroundColor: activeView === 'OPS_CONSOLE' ? 'var(--bg-hover)' : 'transparent',
              color: activeView === 'OPS_CONSOLE' ? '#3b82f6' : '#e2e8f0',
              fontWeight: activeView === 'OPS_CONSOLE' ? 'bold' : 'normal'
            }}
          >
            <ShieldCheck size={18} /> Ops & Approvals
          </button>

          <button 
            onClick={() => setActiveView('ADMIN_BI')}
            style={{ 
              display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 16px', 
              borderRadius: '8px', border: 'none', cursor: 'pointer', textAlign: 'left',
              backgroundColor: activeView === 'ADMIN_BI' ? 'var(--bg-hover)' : 'transparent',
              color: activeView === 'ADMIN_BI' ? '#3b82f6' : '#e2e8f0',
              fontWeight: activeView === 'ADMIN_BI' ? 'bold' : 'normal'
            }}
          >
            <BarChart3 size={18} /> Admin & BI
          </button>
        </div>

        {/* GLOBAL ROLE SELECTOR */}
        <div style={{ padding: '20px', borderTop: '1px solid var(--border-color)', backgroundColor: 'rgba(0,0,0,0.2)' }}>
          <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <UserCircle size={14} /> Active Session Role
          </div>
          <select 
            value={userRole} 
            onChange={(e) => dispatch(setUserRole(e.target.value as 'l1_support' | 'ops_lead'))}
            style={{ 
              width: '100%', background: 'var(--bg-dark)', color: 'white', 
              padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)',
              outline: 'none'
            }}
          >
            <option value="l1_support">L1 Support (Read-Only)</option>
            <option value="ops_lead">Ops Lead (Write Access)</option>
          </select>
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div style={{ flex: 1, padding: '16px', overflow: 'hidden' }}>
        {activeView === 'DASHBOARD' ? (
          <Group orientation="horizontal" style={{ height: '100%' }}>
            
            {/* Panel 1: Live Fraud Queue */}
            <Panel defaultSize={25} minSize={20} className="panel">
              <div className="panel-header">Live Alerts</div>
              <div className="panel-content" style={{ flex: 1, overflow: 'hidden' }}>
                <LiveQueue />
              </div>
            </Panel>

            <Separator className="resize-divider" />

            {/* Panel 2: Agentic Copilot */}
            <Panel defaultSize={45} minSize={30} className="panel">
              <div className="panel-header">Agent Workspace</div>
              <div className="panel-content" style={{ flex: 1, position: 'relative', minHeight: 0, padding: 0 }}>
                <Copilot />
              </div>
            </Panel>

            <Separator className="resize-divider" />

            {/* Panel 3: Mule Network Graph */}
            <Panel defaultSize={30} minSize={20} className="panel">
              <div className="panel-header">Network Analysis</div>
              <div className="panel-content" style={{ flex: 1, position: 'relative', minHeight: 0 }}>
                <NetworkGraph />
              </div>
            </Panel>

          </Group>
        ) : activeView === 'OPS_CONSOLE' ? (
          /* FULL SCREEN OPS VIEW */
          <div style={{ height: '100%', padding: '0 20px' }}>
            <UnifiedOpsView />
          </div>
        ) : (
          /* ADMIN & BI ANALYTICS VIEW */
          <div style={{ height: '100%', overflowY: 'auto' }}>
            <AdminBIDashboard apiBaseUrl={API_BASE_URL} userRole={userRole} />
          </div>
        )}
      </div>

    </div>
  );
}

export default function App() {
  return (
    <Provider store={store}>
      <MainLayout />
    </Provider>
  );
}