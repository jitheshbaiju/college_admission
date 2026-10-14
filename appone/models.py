from django.db import models
from django.conf import settings
import uuid


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    mobile_number = models.CharField(max_length=30)
    terms_accepted_at = models.DateTimeField()

    def __str__(self):
        return f"Student profile for {self.user}"


class Course(models.Model):
    class Category(models.TextChoices):
        UNDERGRADUATE = "undergraduate", "Undergraduate"
        POSTGRADUATE = "postgraduate", "Postgraduate"
        DIPLOMA = "diploma", "Diploma"
        CERTIFICATE = "certificate", "Certificate"

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    department = models.CharField(max_length=120)
    duration = models.CharField(max_length=60)
    eligibility = models.CharField(max_length=180)
    description = models.TextField()
    fees = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    available_seats = models.PositiveIntegerField(null=True, blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.code} - {self.name}"


class AdmissionApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    class Category(models.TextChoices):
        GENERAL = "general", "General"
        OBC = "obc", "OBC"
        SC = "sc", "SC"
        ST = "st", "ST"
        OTHER = "other", "Other"

    application_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admission_applications")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="applications")
    phone = models.CharField(max_length=30)
    highest_qualification = models.CharField(max_length=120)
    date_of_birth = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=12, choices=Category.choices, blank=True, default="")
    passport_photo = models.FileField(upload_to="admissions/photos/", blank=True)
    student_signature = models.FileField(upload_to="admissions/signatures/", blank=True)
    identity_proof = models.FileField(upload_to="admissions/identity/", blank=True)
    tenth_certificate = models.FileField(upload_to="admissions/certificates/10th/", blank=True)
    twelfth_certificate = models.FileField(upload_to="admissions/certificates/12th/", blank=True)
    transfer_certificate = models.FileField(upload_to="admissions/certificates/transfer/", blank=True)
    conduct_certificate = models.FileField(upload_to="admissions/certificates/conduct/", blank=True)
    caste_certificate = models.FileField(upload_to="admissions/certificates/caste/", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-submitted_at",)

    def __str__(self):
        return str(self.application_number)


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    application = models.OneToOneField(
        AdmissionApplication, on_delete=models.CASCADE, related_name="payment"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="admission_payments"
    )
    course_fee = models.DecimalField(max_digits=10, decimal_places=2)
    other_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=30, blank=True)
    gateway_order_id = models.CharField(max_length=100, blank=True, db_index=True)
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    receipt_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.application.application_number} — {self.get_status_display()}"


class ContactMessage(models.Model):
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ("-submitted_at",)

    def __str__(self):
        return f"{self.subject} — {self.full_name}"
