import hashlib
import hmac
import json
from base64 import b64encode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class PaymentGatewayError(Exception):
    pass


def _credentials():
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise PaymentGatewayError("Online payment is not configured. Please contact admissions.")
    return key_id, key_secret


def create_order(payment):
    key_id, key_secret = _credentials()
    payload = json.dumps(
        {
            "amount": int(payment.amount * 100),
            "currency": "INR",
            "receipt": f"application-{payment.application_id}",
            "notes": {"application_number": str(payment.application.application_number)},
        }
    ).encode("utf-8")
    request = Request(
        "https://api.razorpay.com/v1/orders",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    request.add_header("Authorization", "Basic " + b64encode(f"{key_id}:{key_secret}".encode()).decode())
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise PaymentGatewayError("Could not start the payment with the gateway. Please try again.") from error
    if not result.get("id") or result.get("amount") != int(payment.amount * 100):
        raise PaymentGatewayError("The payment gateway returned an invalid order.")
    return key_id, result["id"]


def verify_checkout_signature(order_id, payment_id, signature):
    _, key_secret = _credentials()
    expected = hmac.new(
        key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def fetch_payment(payment_id):
    key_id, key_secret = _credentials()
    request = Request(f"https://api.razorpay.com/v1/payments/{payment_id}")
    request.add_header("Authorization", "Basic " + b64encode(f"{key_id}:{key_secret}".encode()).decode())
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise PaymentGatewayError("Could not verify the transaction with the payment gateway.") from error


def capture_payment(payment_id, amount):
    key_id, key_secret = _credentials()
    payload = json.dumps({"amount": int(amount * 100), "currency": "INR"}).encode("utf-8")
    request = Request(
        f"https://api.razorpay.com/v1/payments/{payment_id}/capture",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    request.add_header("Authorization", "Basic " + b64encode(f"{key_id}:{key_secret}".encode()).decode())
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise PaymentGatewayError("Could not capture the authorized payment with the gateway.") from error


def verify_webhook_signature(body, signature):
    secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        raise PaymentGatewayError("The payment webhook is not configured.")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
