from fastapi import APIRouter, HTTPException, Request, Header, Query
from fastapi.responses import StreamingResponse
import json
from typing import Optional
from pydantic import BaseModel
from src.models.schemas import ( FraudFeedbackRequest, SearchRequest, SearchResult, AskRequest, AskResponse, MuleNetworkResponse)
from src.database.queries import ( search_knowledge, update_fraud_feedback, get_mule_id_from_txn, 
                                  get_mule_network, process_dpdp_deletion, get_live_alerts, 
                                   get_approval_requests, get_audit_logs, resolve_approval_request )
from src.agent.engine import run_agentic_loop


router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

@router.post("/search", response_model=list[SearchResult])
def search_endpoint(req: SearchRequest, request: Request):
    try:
        embedder = request.app.state.embedder
        return search_knowledge(req, embedder)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask")
async def ask_endpoint(req: AskRequest, request: Request, x_user_role: Optional[str] = Header(default="l1_support")):
    print(f"=== INCOMING ROLE: {x_user_role} ===")
    embedder = request.app.state.embedder
    chunks = search_knowledge(SearchRequest(query=req.query, top_k=req.top_k), embedder)
    
    context_text = "\n\n".join([
        f"Source: {c.document_name} (Page {c.page_number})\nText: {c.text}"
        for c in chunks
    ])
    
    citations = list(dict.fromkeys([
        f"{c.document_name} (Page {c.page_number})" for c in chunks
    ]))

    async def event_stream():
        try:
            # Yield initial citations immediately
            yield f"data: {json.dumps({'type': 'citations', 'content': citations})}\n\n"
            
            # NOTE: Your run_agentic_loop must be updated to yield chunks/tool statuses. 
            # Assuming it yields dictionaries like {'type': 'tool', 'content': 'Checking status...'} 
            # or {'type': 'token', 'content': 'The '}
            async for chunk in run_agentic_loop(req.query, context_text, user_role=x_user_role):
                yield f"data: {json.dumps(chunk)}\n\n"
                
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.put("/fraud/{flag_id}/feedback")
def submit_fraud_feedback(flag_id: int, req: FraudFeedbackRequest):
    try:
        result = update_fraud_feedback(flag_id, req.feedback)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fraud/{txn_id}/network", response_model=MuleNetworkResponse)
def get_network_view(txn_id: str):
    try:
        # 1. Translate the UPI string into a User UUID
        mule_id = get_mule_id_from_txn(txn_id)
        
        # 2. Pass the UUID to your network generator
        network_data = get_mule_network(mule_id)
        
        return network_data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/customer/{customer_id}/dpdp")
def request_right_to_be_forgotten(customer_id: str, x_user_role: Optional[str] = Header(default="l1_support")):
    # RBAC Guardrail
    if x_user_role not in ["ops_lead", "compliance_officer"]:
        raise HTTPException(status_code=403, detail="Unauthorized: Only compliance or ops_lead can process DPDP requests.")
    
    result = process_dpdp_deletion(customer_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result

@router.get("/fraud/queue")
def fetch_live_queue(limit: int = Query(10), offset: int = Query(0)):
    try:
        alerts = get_live_alerts(limit=limit, offset=offset)
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ops/approvals")
def fetch_approvals(status: Optional[str] = Query(None), 
                    txn_id: Optional[str] = Query(None),
                    date: Optional[str] = Query(None)):
    try:
        data = get_approval_requests(status=status, txn_id=txn_id, date_filter=date)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ops/audit")
def fetch_audit_log(
    txn_id: Optional[str] = Query(None), 
    date: Optional[str] = Query(None)):
    try:
        data = get_audit_logs(txn_id=txn_id, date_filter=date)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DecisionPayload(BaseModel):
    decision: str
    reason: str = ""

@router.post("/ops/approvals/{request_id}/decision")
def submit_approval_decision(
    request_id: int, 
    payload: DecisionPayload, 
    x_user_role: str = Header(default="l1_support")
):
    if x_user_role != "ops_lead":
        raise HTTPException(status_code=403, detail="UNAUTHORIZED: Only Ops Leads can approve or reject requests.")
    
    result = resolve_approval_request(
        request_id=request_id, 
        decision=payload.decision, 
        decided_by=x_user_role, 
        reason=payload.reason
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result