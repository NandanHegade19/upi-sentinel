from pydantic import BaseModel, field_validator

class SearchRequest(BaseModel):
    query: str
    top_k: int = 4

class SearchResult(BaseModel):
    document_name: str
    page_number: int | None
    text: str
    similarity_score: float

class AskRequest(BaseModel):
    query: str
    top_k: int = 4

class AskResponse(BaseModel):
    answer: str
    citations: list[str]

class FraudFeedbackRequest(BaseModel):
    feedback: str

    @field_validator('feedback')
    def validate_feedback(cls, v):
        allowed = {"TRUE_POSITIVE", "FALSE_POSITIVE"}
        if v not in allowed:
            raise ValueError(f"Feedback must be one of {allowed}")
        return v

class NetworkEdge(BaseModel):
    source_id: str
    target_id: str
    amount: float
    timestamp: str
    direction: str

class MuleNetworkResponse(BaseModel):
    mule_id: str
    edges: list[NetworkEdge]