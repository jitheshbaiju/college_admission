# Course fee payments

Apply the current database schema with `.\.project\Scripts\python.exe manage.py migrate`.

Admission registration and application submission are free. Applicants choose online payment or direct payment at the college before submitting their application. They pay only the selected course fee configured in Django admin; there is no separate admission, service, or other applicable fee. Direct payments are instructions only and are not recorded or verified by this website. Historical successful-payment receipts remain available.

Create Razorpay API keys and use test keys until the complete flow has been tested. Configure the credentials as environment variables; never commit live keys or webhook secrets:

```powershell
$env:RAZORPAY_KEY_ID = "rzp_test_..."
$env:RAZORPAY_KEY_SECRET = "your_test_key_secret"
$env:RAZORPAY_WEBHOOK_SECRET = "your_webhook_secret"
```

The checkout uses Razorpay-hosted fields. The server verifies the checkout signature and transaction/order/amount/currency/captured status before issuing a receipt. Register `/payments/razorpay/webhook/` in the Razorpay dashboard with the same webhook secret and subscribe to `payment.captured`, `payment.failed`, and `refund.processed`.

Set each course's **Fees** in Django admin. A course without a configured fee does not offer online payment.

Students submit an application with a passport photo, identity proof, 10th certificate, and 12th certificate (PDF/JPG/PNG, maximum 5 MB each). The transfer certificate is optional. In admin, move the application status to **Accepted** to update the student dashboard.

Uploaded documents are private: students can access only their own files, and staff can access them while signed into Django admin. Do not serve the `media` directory as public static content.
