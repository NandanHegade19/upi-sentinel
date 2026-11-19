import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { Search, Filter, Clock, CheckCircle, Shield } from 'lucide-react';
import { type RootState } from '../store/opsSlice';


// Define the data structures matching our Python backend
interface ApprovalRequest {
  request_id: number;
  run_id: string;
  action_type: string;
  payload: { txn_id: string; reason: string };
  status: string;
  decided_by: string | null;
  decided_at: string | null;
}

interface AuditEvent {
  user_role: string;
  action_type: string;
  txn_id: string;
  details: any;
  created_at: string;
}

type TabType = 'QUEUE' | 'HISTORY' | 'AUDIT';

export default function UnifiedOpsView() {
  const [activeTab, setActiveTab] = useState<TabType>('QUEUE');
  
  // Filter States
  const [filterTxnId, setFilterTxnId] = useState('');
  const [filterDate, setFilterDate] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  
  // Data States
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { userRole } = useSelector((state: RootState) => state.ops);

  const handleDecision = async (requestId: number, decision: 'APPROVED' | 'REJECTED') => {
    if (userRole !== 'ops_lead') {
      alert("Only an Ops Lead can perform this action.");
      return;
    }

    const reason = prompt(`Please provide a reason for marking this as ${decision}:`);
    if (reason === null) return; // User cancelled

    try {
      const response = await fetch(`https://received-ask-decide-organizing.trycloudflare.com/api/v1/rag/ops/approvals/${requestId}/decision`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole
        },
        body: JSON.stringify({ decision, reason })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to submit decision');
      }

      // Re-fetch the data to clear the row from the pending queue
      fetchData();
    } catch (error: any) {
      alert(`Error: ${error.message}`);
    }
  };

  // Fetch data based on the active tab and applied filters
  const fetchData = async () => {
    setIsLoading(true);
    try {
      const queryParams = new URLSearchParams();
      if (filterTxnId) queryParams.append('txn_id', filterTxnId);
      if (filterDate) queryParams.append('date', filterDate);

      if (activeTab === 'QUEUE' || activeTab === 'HISTORY') {
        // QUEUE shows PENDING. HISTORY shows everything else (or filtered by user)
        const statusOverride = activeTab === 'QUEUE' ? 'PENDING' : filterStatus;
        if (statusOverride) queryParams.append('status', statusOverride);

        const response = await fetch(`https://received-ask-decide-organizing.trycloudflare.com/api/v1/rag/ops/approvals?${queryParams}`);
        const data = await response.json();
        setApprovals(data);
      } else if (activeTab === 'AUDIT') {
        const response = await fetch(`https://received-ask-decide-organizing.trycloudflare.com/api/v1/rag/ops/audit?${queryParams}`);
        const data = await response.json();
        setAuditLogs(data);
      }
    } catch (error) {
      console.error('Failed to fetch ops data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Re-fetch when the tab changes
  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    fetchData();
  };

  const handleClearFilters = () => {
    setFilterTxnId('');
    setFilterDate('');
    setFilterStatus('');
    // State updates are async, so we manually clear the query string for this fetch
    setTimeout(fetchData, 0);
  };

  return (
    <div className="panel flex flex-col" style={{ height: '100%', overflow: 'hidden' }}>
      
        {/* 1. TAB NAVIGATION */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', marginBottom: '16px' }}>
        <button 
          onClick={() => setActiveTab('QUEUE')}
          style={{ 
            padding: '12px 24px', 
            background: activeTab === 'QUEUE' ? 'var(--bg-hover)' : 'transparent', 
            border: 'none', 
            borderBottom: activeTab === 'QUEUE' ? '2px solid #3b82f6' : '2px solid transparent', 
            cursor: 'pointer', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            fontWeight: activeTab === 'QUEUE' ? 'bold' : 'normal',
            color: activeTab === 'QUEUE' ? '#ffffff' : '#94a3b8' 
          }}
        >
          <Clock size={16} /> Approval Queue
        </button>
        <button 
          onClick={() => setActiveTab('HISTORY')}
          style={{ 
            padding: '12px 24px', 
            background: activeTab === 'HISTORY' ? 'var(--bg-hover)' : 'transparent', 
            border: 'none', 
            borderBottom: activeTab === 'HISTORY' ? '2px solid #3b82f6' : '2px solid transparent', 
            cursor: 'pointer', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            fontWeight: activeTab === 'HISTORY' ? 'bold' : 'normal',
            color: activeTab === 'HISTORY' ? '#ffffff' : '#94a3b8' 
          }}
        >
          <CheckCircle size={16} /> Case History
        </button>
        <button 
          onClick={() => setActiveTab('AUDIT')}
          style={{ 
            padding: '12px 24px', 
            background: activeTab === 'AUDIT' ? 'var(--bg-hover)' : 'transparent', 
            border: 'none', 
            borderBottom: activeTab === 'AUDIT' ? '2px solid #3b82f6' : '2px solid transparent', 
            cursor: 'pointer', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            fontWeight: activeTab === 'AUDIT' ? 'bold' : 'normal',
            color: activeTab === 'AUDIT' ? '#ffffff' : '#94a3b8' 
          }}
        >
          <Shield size={16} /> Audit Log
        </button>
      </div>

      {/* 2. UNIFIED FILTER BAR */}
      <form onSubmit={handleApplyFilters} style={{ display: 'flex', gap: '12px', padding: '0 16px 16px 16px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-input)', padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
          <Search size={16} color="#64748b" style={{ marginRight: '8px' }} />
          <input 
            type="text" 
            placeholder="Txn ID..." 
            value={filterTxnId}
            onChange={(e) => setFilterTxnId(e.target.value)}
            style={{ border: 'none', background: 'transparent', outline: 'none', width: '160px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-input)', padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
          <input 
            type="date" 
            value={filterDate}
            onChange={(e) => setFilterDate(e.target.value)}
            style={{ border: 'none', background: 'transparent', outline: 'none', color: '#64748b' }}
          />
        </div>

        {activeTab === 'HISTORY' && (
          <select 
            value={filterStatus} 
            onChange={(e) => setFilterStatus(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'var(--bg-input)' }}
          >
            <option value="">All Statuses</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        )}

        <button type="submit" className="btn-primary" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Filter size={16} /> Filter
        </button>
        
        {(filterTxnId || filterDate || filterStatus) && (
          <button type="button" onClick={handleClearFilters} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '13px' }}>
            Clear Filters
          </button>
        )}
      </form>

      {/* 3. DYNAMIC DATA TABLES */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px' }}>
        {isLoading ? (
          <div style={{ color: '#64748b' }}>Loading records...</div>
        ) : (activeTab === 'QUEUE' || activeTab === 'HISTORY') ? (
          // APPROVALS TABLE
          approvals.length === 0 ? (
            <div style={{ color: '#10b981' }}>No records found.</div>
          ) : (
            <table className="queue-table">
              <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-panel)' }}>
                <tr>
                  <th>Req ID</th>
                  <th>Txn ID</th>
                  <th>Action</th>
                  <th>Reason</th>
                  <th>Status</th>
                  {activeTab === 'HISTORY' && <th>Decided By</th>}
                  {activeTab === 'QUEUE' && <th>Actions</th>}
                </tr>
              </thead>
              
              <tbody>
                {approvals.map((req) => (
                  <tr key={req.request_id}>
                    <td>#{req.request_id}</td>
                    <td style={{ fontFamily: 'monospace' }}>{req.payload.txn_id}</td>
                    <td><strong>{req.action_type}</strong></td>
                    <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={req.payload.reason}>
                      {req.payload.reason}
                    </td>
                    <td>
                      <span className={`badge ${req.status === 'PENDING' ? 'badge-warning' : req.status === 'APPROVED' ? 'badge-success' : 'badge-critical'}`}>
                        {req.status}
                      </span>
                    </td>
                    {activeTab === 'HISTORY' && <td>{req.decided_by || '-'}</td>}
                    
                    {/* NEW: Action Buttons for the Live Queue */}
                    {activeTab === 'QUEUE' && (
                      <td style={{ display: 'flex', gap: '8px' }}>
                        <button 
                          onClick={() => handleDecision(req.request_id, 'APPROVED')}
                          disabled={userRole !== 'ops_lead'}
                          style={{ background: '#10b981', color: 'white', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: userRole === 'ops_lead' ? 'pointer' : 'not-allowed', opacity: userRole === 'ops_lead' ? 1 : 0.5 }}
                        >
                          Approve
                        </button>
                        <button 
                          onClick={() => handleDecision(req.request_id, 'REJECTED')}
                          disabled={userRole !== 'ops_lead'}
                          style={{ background: '#ef4444', color: 'white', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: userRole === 'ops_lead' ? 'pointer' : 'not-allowed', opacity: userRole === 'ops_lead' ? 1 : 0.5 }}
                        >
                          Reject
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          // AUDIT LOG TABLE
          auditLogs.length === 0 ? (
            <div style={{ color: '#10b981' }}>No audit logs found.</div>
          ) : (
            <table className="queue-table">
              <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-panel)' }}>
                <tr>
                  <th>Timestamp</th>
                  <th>Role</th>
                  <th>Action</th>
                  <th>Txn ID</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log, idx) => (
                  <tr key={idx}>
                    <td style={{ whiteSpace: 'nowrap' }}>{log.created_at.substring(0, 19)}</td>
                    <td>{log.user_role}</td>
                    <td><strong>{log.action_type}</strong></td>
                    <td style={{ fontFamily: 'monospace' }}>{log.txn_id || '-'}</td>
                    <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {JSON.stringify(log.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  );
}