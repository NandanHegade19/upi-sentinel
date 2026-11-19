import { useEffect, useState } from 'react';
import ReactFlow, { Background, Controls, MarkerType, type Node, type Edge, Position } from 'reactflow';
import 'reactflow/dist/style.css';
import { useSelector } from 'react-redux';
import { type RootState } from '../store/opsSlice';
import { Loader2 } from 'lucide-react';

export default function NetworkGraph() {
  const activeTxnId = useSelector((state: RootState) => state.ops.activeTxnId);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!activeTxnId) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const fetchNetwork = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`https://received-ask-decide-organizing.trycloudflare.com/api/v1/rag/fraud/${activeTxnId}/network`);
        if (!response.ok) throw new Error('Failed to fetch network data');
        
        const data = await response.json();
        
        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];
        
        // Separate data
        const inboundEdges = data.edges.filter((e: any) => e.direction === 'INBOUND');
        const outboundEdges = data.edges.filter((e: any) => e.direction === 'OUTBOUND');

        // Calculate Totals
        const totalInbound = inboundEdges.reduce((sum: number, e: any) => sum + e.amount, 0);
        const totalOutbound = outboundEdges.reduce((sum: number, e: any) => sum + e.amount, 0);

        const Y_GAP = 55; // Slightly tighter vertical spacing
        const X_GAP = 450; // Horizontal spacing

        // Calculate center Y position based on the largest column
        const maxNodes = Math.max(inboundEdges.length, outboundEdges.length);
        const centerY = (maxNodes * Y_GAP) / 2;

        // 1. Center Node (The Suspected Mule) with built-in totals
        newNodes.push({
          id: data.mule_id,
          data: { 
            label: (
              // Added whiteSpace: 'nowrap' to prevent wrapping
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', whiteSpace: 'nowrap' }}>
                <div style={{ fontSize: '11px', color: '#10b981', background: 'rgba(16, 185, 129, 0.2)', padding: '4px 8px', borderRadius: '4px' }}>
                  + ₹{totalInbound.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </div>
                <div style={{ fontSize: '14px', fontWeight: 'bold' }}>Suspected Mule</div>
                <div style={{ fontSize: '11px', color: '#f59e0b', background: 'rgba(245, 158, 11, 0.2)', padding: '4px 8px', borderRadius: '4px' }}>
                  - ₹{totalOutbound.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </div>
              </div>
            )
          },
          position: { x: X_GAP, y: centerY },
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
          style: { 
            background: '#ef4444', 
            color: 'white', 
            border: 'none', 
            padding: '12px 16px', // Slightly larger padding
            borderRadius: '8px',
            width: 'auto', // Fixes the overflow constraint
            boxShadow: '0 4px 6px -1px rgba(239, 68, 68, 0.3)'
          }
        });

        // 2. Map Inbound Nodes (Left Side)
        const startInboundY = centerY - ((inboundEdges.length * Y_GAP) / 2);
        inboundEdges.forEach((e: any, index: number) => {
          newNodes.push({
            id: `${e.source_id}-in`,
            data: { 
              label: (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                  <span>...${e.source_id.slice(-6)}</span>
                  <span style={{ color: '#10b981', fontWeight: 600 }}>₹{e.amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
                </div>
              )
            },
            position: { x: 0, y: startInboundY + (index * Y_GAP) },
            sourcePosition: Position.Right,
            style: { background: '#1e293b', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '6px', fontSize: '12px', minWidth: '150px' }
          });

          newEdges.push({
            id: `edge-in-${index}`,
            source: `${e.source_id}-in`,
            target: data.mule_id,
            type: 'smoothstep',
            animated: true,
            style: { stroke: '#10b981', strokeWidth: 1.5, opacity: 0.4 }, // Removed edge labels entirely for cleaner lines
            markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' },
          });
        });

        // 3. Map Outbound Nodes (Right Side)
        const startOutboundY = centerY - ((outboundEdges.length * Y_GAP) / 2);
        outboundEdges.forEach((e: any, index: number) => {
          newNodes.push({
            id: `${e.target_id}-out`,
            data: { 
              label: (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                  <span style={{ color: '#f59e0b', fontWeight: 600 }}>₹{e.amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
                  <span>...${e.target_id.slice(-6)}</span>
                </div>
              )
            },
            position: { x: X_GAP * 2.2, y: startOutboundY + (index * Y_GAP) },
            targetPosition: Position.Left,
            style: { background: '#1e293b', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '6px', fontSize: '12px', minWidth: '150px' }
          });

          newEdges.push({
            id: `edge-out-${index}`,
            source: data.mule_id,
            target: `${e.target_id}-out`,
            type: 'smoothstep',
            animated: true,
            style: { stroke: '#f59e0b', strokeWidth: 1.5, opacity: 0.4 },
            markerEnd: { type: MarkerType.ArrowClosed, color: '#f59e0b' },
          });
        });

        setNodes(newNodes);
        setEdges(newEdges);
      } catch (error) {
        console.error('Network graph error:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchNetwork();
  }, [activeTxnId]);

  if (!activeTxnId) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        Select an alert from the queue to view network analysis.
      </div>
    );
  }

  return (
    <div style={{ height: '100%', position: 'relative' }}>
      {isLoading && (
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 10, color: 'var(--accent-blue)' }}>
          <Loader2 size={32} className="spin" />
        </div>
      )}
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="#334155" gap={16} />
        <Controls style={{ background: '#1e293b', fill: 'white' }} />
      </ReactFlow>
    </div>
  );
}