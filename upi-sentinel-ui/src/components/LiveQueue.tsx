import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { type RootState, setActiveTxn } from '../store/opsSlice';

// Define the alert structure
interface Alert {
  id: string;
  amount: number;
  score: number;
  time: string;
}

export default function LiveQueue() {
  const dispatch = useDispatch();
  const activeTxnId = useSelector((state: RootState) => state.ops.activeTxnId);
  
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const LIMIT = 10;

  const fetchAlerts = async (currentOffset: number, isInitial: boolean = false) => {
    if (isInitial) setIsLoading(true);
    else setIsLoadingMore(true);

    try {
      const response = await fetch(`https://received-ask-decide-organizing.trycloudflare.com/api/v1/rag/fraud/queue?limit=${LIMIT}&offset=${currentOffset}`);
      if (!response.ok) throw new Error('Failed to fetch queue');
      
      const data = await response.json();
      
      // If we get fewer items than requested, there are no more left in the database
      if (data.length < LIMIT) {
        setHasMore(false);
      }

      if (isInitial) {
        setAlerts(data);
      } else {
        setAlerts(prev => [...prev, ...data]); // Append new items to the existing list
      }
    } catch (error) {
      console.error("Error fetching live queue:", error);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchAlerts(0, true);
  }, []);

  const handleLoadMore = () => {
    const newOffset = offset + LIMIT;
    setOffset(newOffset);
    fetchAlerts(newOffset);
  };

  return (
    <div className="panel live-queue-panel flex flex-col" style={{ height: '100%', overflow: 'hidden' }}>
      <h2 className="panel-title">Live Fraud Alerts</h2>
      
      {isLoading ? (
        <div style={{ padding: '20px', color: '#94a3b8' }}>Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div style={{ padding: '20px', color: '#10b981' }}>Queue is empty! All caught up.</div>
      ) : (
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          <table className="queue-table">
            <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-panel)', zIndex: 1 }}>
              <tr>
                <th>Time</th>
                <th>Txn ID</th>
                <th>Amount (₹)</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr 
                  key={alert.id}
                  className={activeTxnId === alert.id ? 'active-row' : ''}
                  onClick={() => dispatch(setActiveTxn(alert.id))}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{alert.time}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{alert.id}</td>
                  <td>{alert.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                  <td>
                    <span className={`badge ${alert.score === -1 ? 'badge-critical' : 'badge-warning'}`}>
                      {alert.score}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {/* Pagination Footer */}
          <div style={{ padding: '16px', textAlign: 'center', borderTop: '1px solid var(--border-color)' }}>
            {hasMore ? (
              <button 
                onClick={handleLoadMore}
                disabled={isLoadingMore}
                className="btn-secondary"
                style={{ padding: '6px 16px', fontSize: '13px', cursor: 'pointer' }}
              >
                {isLoadingMore ? 'Loading...' : 'Load More'}
              </button>
            ) : (
              <span style={{ fontSize: '13px', color: '#64748b' }}>No more transaction found.</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}