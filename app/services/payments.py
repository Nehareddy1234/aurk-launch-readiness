from abc import ABC, abstractmethod

class PaymentProvider(ABC):
    @abstractmethod
    def create_order(self, amount, currency, receipt): raise NotImplementedError
    @abstractmethod
    def verify_payment(self, payload): raise NotImplementedError
    @abstractmethod
    def verify_webhook(self, body, signature): raise NotImplementedError

class RazorpayProvider(PaymentProvider):
    def __init__(self, key_id, key_secret, webhook_secret):
        self.key_id = key_id; self.key_secret = key_secret; self.webhook_secret = webhook_secret
    def create_order(self, amount, currency, receipt):
        raise NotImplementedError("Install/configure the Razorpay SDK and credentials before enabling payments.")
    def verify_payment(self, payload):
        raise NotImplementedError
    def verify_webhook(self, body, signature):
        raise NotImplementedError
