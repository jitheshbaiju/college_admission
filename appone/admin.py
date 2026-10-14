from django.contrib import admin
import csv

from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html_join

from .models import AdmissionApplication, ContactMessage, Course, Payment


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "department", "fees", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name", "department")
    ordering = ("name",)


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = ("application_number", "applicant", "course", "status", "submitted_at")
    list_filter = ("status", "course")
    search_fields = ("application_number", "applicant__username", "course__name")
    fields = (
        "application_number", "applicant", "course", "date_of_birth", "category", "phone", "highest_qualification",
        "status", "submitted_at", "documents",
    )
    readonly_fields = ("application_number", "submitted_at", "documents")

    @admin.display(description="Uploaded documents")
    def documents(self, application):
        document_fields = (
            ("Passport photo", "passport_photo"),
            ("Student signature", "student_signature"),
            ("Identity proof", "identity_proof"),
            ("10th certificate", "tenth_certificate"),
            ("12th certificate", "twelfth_certificate"),
            ("Transfer certificate", "transfer_certificate"),
            ("Conduct certificate", "conduct_certificate"),
            ("Caste certificate", "caste_certificate"),
        )
        links = (
            (label, reverse("admission_document", args=(application.pk, field_name)))
            for label, field_name in document_fields
            if getattr(application, field_name)
        )
        return format_html_join(
            " | ",
            '<a href="{}">{}</a>',
            ((url, label) for label, url in links),
        ) or "No documents uploaded"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number", "student", "application", "amount", "payment_method", "status", "created_at", "paid_at"
    )
    list_filter = ("status", "payment_method", "created_at")
    search_fields = (
        "student__username", "student__email", "student__first_name", "student__last_name",
        "application__application_number", "transaction_id", "receipt_number",
    )
    readonly_fields = (
        "student", "application", "amount", "payment_method", "gateway_order_id",
        "transaction_id", "receipt_number", "status", "created_at", "paid_at",
    )
    actions = ("export_payments_csv",)

    @admin.action(description="Export selected payments as CSV")
    def export_payments_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="admission-payments.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ("Receipt", "Student", "Application", "Course", "Amount", "Method", "Transaction", "Status", "Paid at")
        )
        for payment in queryset.select_related("student", "application__course"):
            writer.writerow(
                (
                    payment.receipt_number,
                    payment.student.get_username(),
                    payment.application.application_number,
                    payment.application.course.name,
                    payment.amount,
                    payment.payment_method,
                    payment.transaction_id,
                    payment.get_status_display(),
                    payment.paid_at,
                )
            )
        return response


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "subject", "submitted_at", "is_read")
    list_filter = ("is_read", "submitted_at")
    search_fields = ("full_name", "email", "subject", "message")
    readonly_fields = ("submitted_at",)
