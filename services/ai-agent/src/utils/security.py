import re

class PIIScrubber:
    # Matches standard UUIDv4 format (e.g., customerId, payeeId)
    UUID_PATTERN = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', re.IGNORECASE)
    
    # Matches UPI VPAs (e.g., name****@okaxis, user@sbi)
    VPA_PATTERN = re.compile(r'[a-zA-Z0-9.\-_*]{2,}@[a-zA-Z]{2,}')
    
    # Matches your specific 12-digit Rail transaction prefixes (e.g., UPI045187718702, IMP727368285014)
    TXN_PATTERN = re.compile(r'\b(UPI|IMP|NEF|RTG|MND)\d{12}\b')

    @classmethod
    def redact(cls, text: str) -> str:
        """Sanitizes strings by replacing sensitive matched patterns with safe tokens."""
        if not text:
            return text
            
        text = cls.UUID_PATTERN.sub('[REDACTED_UUID]', text)
        text = cls.VPA_PATTERN.sub('[REDACTED_VPA]', text)
        text = cls.TXN_PATTERN.sub(r'\1[REDACTED_TXN_ID]', text)
        
        return text

    @classmethod
    def redact_dict(cls, data: dict) -> dict:
        """Recursively sanitizes dictionary payloads (useful for JSON DB records)."""
        scrubbed = {}
        for key, value in data.items():
            if isinstance(value, str):
                scrubbed[key] = cls.redact(value)
            elif isinstance(value, dict):
                scrubbed[key] = cls.redact_dict(value)
            elif isinstance(value, list):
                scrubbed[key] = [cls.redact(v) if isinstance(v, str) else v for v in value]
            else:
                scrubbed[key] = value
        return scrubbed

class PromptGuard:
    # Common prompt injection signatures
    INJECTION_PATTERNS = re.compile(
        r'(ignore all previous|disregard previous|system prompt|you are now|bypass|new instructions|forget your instructions)', 
        re.IGNORECASE
    )

    @classmethod
    def detect_injection(cls, text: str) -> bool:
        """Returns True if a known prompt injection signature is detected."""
        if not text:
            return False
        return bool(cls.INJECTION_PATTERNS.search(text))