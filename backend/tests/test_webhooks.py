\"\"\"测试Webhook服务。\"\"\"
import pytest
import hmac
import hashlib
import json

from app.core.tools.sandbox import CodeSandbox, SandboxConfig, SandboxLanguage
from app.models.webhook import Webhook, WebhookTriggerLog


class TestWebhookSignature:
    \"\"\"测试Webhook签名验证。\"\"\"
    
    def test_verify_signature_success(self):
        from backend.app.api.v2.webhooks import verify_webhook_signature
        
        secret = \"test_secret\"
        payload = b'{\"event\": \"test\"}'
        computed = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        
        assert verify_webhook_signature(payload, secret, f\"v1={computed}\", \"v1\") is True
    
    def test_verify_signature_invalid(self):
        from backend.app.api.v2.webhooks import verify_webhook_signature
        
        secret = \"test_secret\"
        payload = b'{\"event\": \"test\"}'
        
        assert verify_webhook_signature(payload, secret, \"v1=invalid\", \"v1\") is False
    
    def test_verify_signature_wrong_version(self):
        from backend.app.api.v2.webhooks import verify_webhook_signature
        
        secret = \"test_secret\"
        payload = b'{\"event\": \"test\"}'
        computed = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        
        assert verify_webhook_signature(payload, secret, f\"v1={computed}\", \"v2\") is False
