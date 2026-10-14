import json
import os
import uuid
from io import BytesIO

from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from reportlab.pdfgen import canvas

from .forms import (
    AdmissionApplicationForm,
    CollegeAdminLoginForm,
    ContactMessageForm,
    CourseForm,
    RegistrationForm,
    StudentLoginForm,
    StudentProfileUpdateForm,
    StudentPasswordChangeForm,
)
from .models import AdmissionApplication, Course, Payment, StudentProfile
from .payment_gateway import (
    PaymentGatewayError,
    capture_payment,
    create_order,
    fetch_payment,
    verify_checkout_signature,
    verify_webhook_signature,
)

REMEMBER_ME_SESSION_AGE = 60 * 60 * 24 * 14
college_admin_required = user_passes_test(
    lambda user: user.is_staff and user.get_username() == settings.COLLEGE_ADMIN_USERNAME,
    login_url="college_admin_login",
)


def course_list(request):
    courses = Course.objects.filter(is_active=True)
    return render(request, "course.html", {"courses": courses})


@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_active=True)
    return render(request, "course_detail.html", {"course": course})


def admission(request):
    return render(request, "adimission.html")


def contact(request):
    if request.method == "POST":
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your message. Our admissions team will be in touch.")
            return redirect("contact")
    else:
        form = ContactMessageForm()
    return render(request, "contact.html", {"form": form})


@login_required
def admission_application(request):
    if request.method == "POST":
        form = AdmissionApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.cleaned_data["course"]
            payment_option = form.cleaned_data["payment_option"]
            if payment_option == "online" and (course.fees is None or course.fees <= 0):
                form.add_error(
                    "payment_option",
                    "Online payment is unavailable for this course. Choose direct payment or contact admissions.",
                )
                return render(request, "admission_application.html", {"form": form})
            application = form.save(commit=False)
            application.applicant = request.user
            application.save()
            if payment_option == "online":
                messages.success(request, "Application submitted. Complete your course-fee payment online.")
                return redirect("payment", application_id=application.pk)
            return redirect("admission_dashboard")
    else:
        form = AdmissionApplicationForm()

    return render(request, "admission_application.html", {"form": form})


@login_required
def admission_dashboard(request):
    applications = AdmissionApplication.objects.filter(applicant=request.user).select_related(
        "course", "payment"
    )
    profile = StudentProfile.objects.filter(user=request.user).first()
    counts = {
        "total": applications.count(),
        "submitted": sum(1 for a in applications if a.status == AdmissionApplication.Status.SUBMITTED),
        "under_review": sum(1 for a in applications if a.status == AdmissionApplication.Status.UNDER_REVIEW),
        "accepted": sum(1 for a in applications if a.status == AdmissionApplication.Status.ACCEPTED),
        "declined": sum(1 for a in applications if a.status == AdmissionApplication.Status.DECLINED),
        "payments_done": sum(
            1
            for a in applications
            if hasattr(a, "payment") and a.payment and a.payment.status == Payment.Status.SUCCESSFUL
        ),
    }
    return render(
        request,
        "admission_dashboard.html",
        {
            "applications": applications,
            "profile": profile,
            "counts": counts,
        },
    )


@login_required
def student_profile(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    applications = AdmissionApplication.objects.filter(applicant=request.user).select_related(
        "course", "payment"
    )

    profile_form = None
    password_form = None
    active_tab = "overview"

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_profile":
            active_tab = "edit-profile"
            profile_form = StudentProfileUpdateForm(request.POST, user=request.user)
            if profile_form.is_valid():
                user = request.user
                user.first_name = profile_form.cleaned_data["first_name"]
                user.last_name = profile_form.cleaned_data["last_name"]
                user.email = profile_form.cleaned_data["email"]
                user.save(update_fields=["first_name", "last_name", "email"])

                mobile = profile_form.cleaned_data["mobile_number"]
                if profile:
                    profile.mobile_number = mobile
                    profile.save(update_fields=["mobile_number"])
                else:
                    profile = StudentProfile.objects.create(
                        user=user,
                        mobile_number=mobile,
                        terms_accepted_at=timezone.now(),
                    )
                messages.success(request, "Your profile details have been updated successfully.")
                return redirect("student_profile")
        elif action == "change_password":
            active_tab = "security"
            password_form = StudentPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password has been changed successfully.")
                return redirect("student_profile")

    if profile_form is None:
        initial_data = {
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "mobile_number": profile.mobile_number if profile else "",
        }
        profile_form = StudentProfileUpdateForm(initial=initial_data, user=request.user)

    if password_form is None:
        password_form = StudentPasswordChangeForm(user=request.user)

    counts = {
        "total": applications.count(),
        "submitted": sum(1 for a in applications if a.status == AdmissionApplication.Status.SUBMITTED),
        "under_review": sum(1 for a in applications if a.status == AdmissionApplication.Status.UNDER_REVIEW),
        "accepted": sum(1 for a in applications if a.status == AdmissionApplication.Status.ACCEPTED),
        "declined": sum(1 for a in applications if a.status == AdmissionApplication.Status.DECLINED),
    }

    return render(
        request,
        "student_profile.html",
        {
            "profile": profile,
            "applications": applications,
            "profile_form": profile_form,
            "password_form": password_form,
            "counts": counts,
            "active_tab": active_tab,
        },
    )



@college_admin_required
def college_dashboard(request):
    applications = AdmissionApplication.objects.select_related(
        "applicant", "course"
    )
    counts = {
        "total": applications.count(),
        "submitted": applications.filter(status=AdmissionApplication.Status.SUBMITTED).count(),
        "under_review": applications.filter(status=AdmissionApplication.Status.UNDER_REVIEW).count(),
        "accepted": applications.filter(status=AdmissionApplication.Status.ACCEPTED).count(),
        "declined": applications.filter(status=AdmissionApplication.Status.DECLINED).count(),
    }
    return render(
        request,
        "clg.html",
        {"applications": applications, "counts": counts},
    )


@college_admin_required
def college_profile(request):
    return render(request, "college_profile.html")


@college_admin_required
def admin_course_list(request):
    courses = Course.objects.all().order_by("-is_active", "name")
    return render(request, "admin_courses.html", {"courses": courses})


@college_admin_required
def admin_course_add(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            messages.success(request, f'Course "{course.name}" has been added successfully.')
            return redirect("admin_course_list")
    else:
        form = CourseForm()
    return render(request, "admin_course_form.html", {"form": form, "page_title": "Add New Course", "is_edit": False})


@college_admin_required
def admin_course_edit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Course "{course.name}" has been updated successfully.')
            return redirect("admin_course_list")
    else:
        form = CourseForm(instance=course)
    return render(request, "admin_course_form.html", {"form": form, "page_title": f'Edit — {course.name}', "is_edit": True, "course": course})


@college_admin_required
@require_POST
def admin_course_delete(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    name = course.name
    try:
        course.delete()
        messages.success(request, f'Course "{name}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete course "{name}": {exc}')
    return redirect("admin_course_list")


@college_admin_required
@require_POST
def college_application_action(request, application_id, action):
    application = get_object_or_404(AdmissionApplication, pk=application_id)
    status_by_action = {
        "approve": AdmissionApplication.Status.ACCEPTED,
        "decline": AdmissionApplication.Status.DECLINED,
    }
    new_status = status_by_action.get(action)
    if new_status is None:
        raise Http404
    if application.status not in (
        AdmissionApplication.Status.SUBMITTED,
        AdmissionApplication.Status.UNDER_REVIEW,
    ):
        messages.error(request, "Only submitted or under-review applications can be decided.")
        return redirect("college_dashboard")

    application.status = new_status
    application.save(update_fields=("status",))
    label = "approved" if action == "approve" else "declined"
    messages.success(request, f"Application {application.application_number} has been {label}.")
    return redirect("college_dashboard")


@college_admin_required
@require_POST
def college_application_delete(request, application_id):
    application = get_object_or_404(AdmissionApplication, pk=application_id)
    app_number = application.application_number
    try:
        application.delete()
        messages.success(request, f"Application {app_number} has been permanently deleted.")
    except Exception as exc:
        messages.error(request, f"Could not delete application {app_number}: {exc}")
    return redirect("college_dashboard")


@login_required
def admission_document(request, application_id, document_field):
    allowed_fields = {
        "passport_photo",
        "student_signature",
        "identity_proof",
        "tenth_certificate",
        "twelfth_certificate",
        "transfer_certificate",
        "conduct_certificate",
        "caste_certificate",
    }
    if document_field not in allowed_fields:
        raise Http404
    application = get_object_or_404(AdmissionApplication, pk=application_id)
    if application.applicant_id != request.user.pk and not request.user.is_staff:
        raise Http404
    document = getattr(application, document_field)
    if not document:
        raise Http404
    return FileResponse(document.open("rb"), as_attachment=True, filename=os.path.basename(document.name))


@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have successfully logged out of your account.")
        return redirect("home")

    return render(request, "logout.html")


@login_required
def payment(request, application_id):
    application = get_object_or_404(
        AdmissionApplication.objects.select_related("course", "applicant"),
        pk=application_id,
        applicant=request.user,
    )
    if application.status == AdmissionApplication.Status.DECLINED:
        messages.info(request, "Course fee payment is unavailable for this application.")
        return redirect("admission_dashboard")
    course_fee = application.course.fees
    if course_fee is None or course_fee < 0:
        messages.error(request, "The course fee is not configured. Please contact admissions.")
        return redirect("admission_dashboard")
    if course_fee == 0:
        messages.info(request, "No course fee is due for this program.")
        return redirect("admission_dashboard")

    payment_record = Payment.objects.filter(application=application).first()
    if payment_record and payment_record.status == Payment.Status.SUCCESSFUL:
        return redirect("payment_receipt", payment_id=payment_record.pk)
    if payment_record and payment_record.status == Payment.Status.REFUNDED:
        messages.info(request, "This course-fee payment was refunded. Please contact admissions for assistance.")
        return redirect("admission_dashboard")
    if payment_record and payment_record.student_id != request.user.pk:
        return HttpResponseBadRequest("Payment applicant does not match the application owner.")

    if request.method == "POST":
        if request.POST.get("action") == "start_online_payment":
            if payment_record is None:
                payment_record = Payment.objects.create(
                    application=application,
                    student=request.user,
                    course_fee=course_fee,
                    other_fees=0,
                    amount=course_fee,
                )
            elif payment_record.amount != course_fee or payment_record.course_fee != course_fee:
                payment_record.course_fee = course_fee
                payment_record.other_fees = 0
                payment_record.amount = course_fee
                payment_record.gateway_order_id = ""
                payment_record.save(
                    update_fields=("course_fee", "other_fees", "amount", "gateway_order_id")
                )

            if payment_record.status == Payment.Status.FAILED or not payment_record.gateway_order_id:
                try:
                    key_id, order_id = create_order(payment_record)
                except PaymentGatewayError as error:
                    messages.error(request, str(error))
                    return redirect("payment", application_id=application.pk)
                payment_record.gateway_order_id = order_id
                payment_record.save(update_fields=("gateway_order_id",))
            else:
                if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
                    messages.error(request, "Online payment is not configured. Please contact admissions.")
                    return redirect("payment", application_id=application.pk)
                key_id = settings.RAZORPAY_KEY_ID
            return render(
                request,
                "payment.html",
                {
                    "application": application,
                    "payment": payment_record,
                    "course_fee": course_fee,
                    "razorpay_key_id": key_id,
                    "payment_amount_paise": int(payment_record.amount * 100),
                    "gateway_configured": bool(key_id and settings.RAZORPAY_KEY_SECRET),
                },
            )

        if request.POST.get("action") != "verify" or payment_record is None:
            messages.error(request, "Choose online payment to start checkout.")
            return redirect("payment", application_id=application.pk)

        payment_id = request.POST.get("razorpay_payment_id", "")
        order_id = request.POST.get("razorpay_order_id", "")
        signature = request.POST.get("razorpay_signature", "")
        try:
            signature_is_valid = (
                bool(payment_id)
                and order_id == payment_record.gateway_order_id
                and verify_checkout_signature(order_id, payment_id, signature)
            )
        except PaymentGatewayError as error:
            messages.error(request, str(error))
            return redirect("payment", application_id=application.pk)
        if not signature_is_valid:
            messages.error(request, "Payment verification failed. No successful payment was recorded.")
            return redirect("payment", application_id=application.pk)
        try:
            gateway_payment = fetch_payment(payment_id)
            if (
                gateway_payment.get("id") == payment_id
                and gateway_payment.get("order_id") == order_id
                and gateway_payment.get("amount") == int(payment_record.amount * 100)
                and gateway_payment.get("currency") == "INR"
                and gateway_payment.get("status") == "authorized"
            ):
                capture_payment(payment_id, payment_record.amount)
                gateway_payment = fetch_payment(payment_id)
        except PaymentGatewayError as error:
            messages.error(request, str(error))
            return redirect("payment", application_id=application.pk)
        if (
            gateway_payment.get("id") != payment_id
            or gateway_payment.get("order_id") != order_id
            or gateway_payment.get("amount") != int(payment_record.amount * 100)
            or gateway_payment.get("currency") != "INR"
            or gateway_payment.get("status") != "captured"
        ):
            messages.error(request, "The gateway has not confirmed a captured payment for this application.")
            return redirect("payment", application_id=application.pk)

        with transaction.atomic():
            payment_record = Payment.objects.select_for_update().get(pk=payment_record.pk)
            if payment_record.status in (Payment.Status.PENDING, Payment.Status.FAILED):
                payment_record.status = Payment.Status.SUCCESSFUL
                payment_record.transaction_id = payment_id
                payment_record.payment_method = gateway_payment.get("method", "")
                payment_record.receipt_number = f"RCP-{uuid.uuid4().hex.upper()}"
                payment_record.paid_at = timezone.now()
                payment_record.save(
                    update_fields=(
                        "status", "transaction_id", "payment_method", "receipt_number", "paid_at"
                    )
                )
        if payment_record.status == Payment.Status.REFUNDED:
            messages.info(request, "This payment has been refunded. Please contact admissions for assistance.")
            return redirect("admission_dashboard")
        messages.success(request, "Course-fee payment verified. Your receipt is ready to download.")
        return redirect("payment_receipt", payment_id=payment_record.pk)

    key_id = (
        settings.RAZORPAY_KEY_ID
        if (
            payment_record
            and payment_record.status == Payment.Status.PENDING
            and payment_record.gateway_order_id
            and settings.RAZORPAY_KEY_ID
            and settings.RAZORPAY_KEY_SECRET
        )
        else ""
    )
    return render(
        request,
        "payment.html",
        {
            "application": application,
            "payment": payment_record,
            "course_fee": course_fee,
            "razorpay_key_id": key_id,
            "payment_amount_paise": int(course_fee * 100),
            "gateway_configured": bool(
                settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET
            ),
        },
    )


@login_required
def payment_receipt(request, payment_id):
    payment_record = get_object_or_404(
        Payment.objects.select_related("application__course", "student"),
        pk=payment_id,
        student=request.user,
        status=Payment.Status.SUCCESSFUL,
    )
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.setTitle(f"Payment receipt {payment_record.receipt_number}")
    document.setFont("Helvetica-Bold", 18)
    document.drawString(72, 760, "Admission Payment Receipt")
    document.setFont("Helvetica", 11)
    rows = (
        ("Receipt number", payment_record.receipt_number),
        ("Student name", payment_record.student.get_full_name() or payment_record.student.get_username()),
        ("Application number", payment_record.application.application_number),
        ("Course", payment_record.application.course.name),
        ("Amount paid", f"INR {payment_record.amount:.2f}"),
        ("Transaction ID", payment_record.transaction_id),
        ("Payment date", timezone.localtime(payment_record.paid_at).strftime("%d %b %Y, %I:%M %p")),
        ("Payment status", payment_record.get_status_display()),
    )
    y = 720
    for label, value in rows:
        receipt_line = f"{label}: {value}".encode("ascii", "replace").decode("ascii")
        document.drawString(72, y, receipt_line)
        y -= 30
    document.save()
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{payment_record.receipt_number}.pdf"'
    return response


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        if not verify_webhook_signature(request.body, signature):
            return HttpResponseBadRequest("Invalid webhook signature.")
        event = json.loads(request.body)
    except (PaymentGatewayError, json.JSONDecodeError):
        return HttpResponseBadRequest("Invalid payment webhook.")

    event_type = event.get("event")
    payload = event.get("payload", {})
    entity = payload.get("payment", {}).get("entity", {})
    if event_type == "refund.processed":
        entity = payload.get("refund", {}).get("entity", {})
        transaction_id = entity.get("payment_id")
        new_status = Payment.Status.REFUNDED
    elif event_type == "payment.captured":
        transaction_id = entity.get("id")
        new_status = Payment.Status.SUCCESSFUL
    elif event_type == "payment.failed":
        transaction_id = entity.get("id")
        new_status = Payment.Status.FAILED
    else:
        return HttpResponse(status=200)

    if not transaction_id:
        return HttpResponseBadRequest("Webhook transaction ID is missing.")
    with transaction.atomic():
        payment_record = Payment.objects.select_for_update().filter(
            transaction_id=transaction_id
        ).first()
        if payment_record is None and event_type in ("payment.captured", "payment.failed"):
            order_id = entity.get("order_id")
            payment_record = Payment.objects.select_for_update().filter(
                gateway_order_id=order_id
            ).first()
            if payment_record:
                payment_record.transaction_id = transaction_id
                payment_record.payment_method = entity.get("method", "")
                if new_status == Payment.Status.SUCCESSFUL:
                    payment_record.receipt_number = f"RCP-{uuid.uuid4().hex.upper()}"
                    payment_record.paid_at = timezone.now()
        if payment_record is None:
            return HttpResponse(status=200)
        if event_type in ("payment.captured", "payment.failed") and (
            entity.get("order_id") != payment_record.gateway_order_id
            or entity.get("amount") != int(payment_record.amount * 100)
            or entity.get("currency") != "INR"
        ):
            return HttpResponseBadRequest("Webhook payment does not match the application.")
        if new_status == Payment.Status.REFUNDED and (
            entity.get("amount") is not None
            and entity.get("amount") < int(payment_record.amount * 100)
        ):
            return HttpResponse(status=200)
        if payment_record.status == Payment.Status.REFUNDED:
            return HttpResponse(status=200)
        if payment_record.status == Payment.Status.SUCCESSFUL and new_status == Payment.Status.FAILED:
            return HttpResponse(status=200)
        if new_status == Payment.Status.REFUNDED and payment_record.status != Payment.Status.SUCCESSFUL:
            return HttpResponse(status=200)
        if new_status == Payment.Status.SUCCESSFUL:
            payment_record.transaction_id = transaction_id
            payment_record.payment_method = entity.get("method", payment_record.payment_method)
            payment_record.receipt_number = payment_record.receipt_number or f"RCP-{uuid.uuid4().hex.upper()}"
            payment_record.paid_at = payment_record.paid_at or timezone.now()
        payment_record.status = new_status
        payment_record.save()
    return HttpResponse(status=200)


def register(request):
    if request.user.is_authenticated:
        return redirect("admission_dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            request.session.set_expiry(REMEMBER_ME_SESSION_AGE)
            return redirect("admission_application")
    else:
        form = RegistrationForm()
    return render(request, "register.html", {"form": form})


class StudentLoginView(LoginView):
    template_name = "login.html"
    authentication_form = StudentLoginForm

    def get_success_url(self):
        if redirect_to := self.get_redirect_url():
            return redirect_to
        return reverse("student_profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(REMEMBER_ME_SESSION_AGE)
        else:
            self.request.session.set_expiry(0)
        return response


class CollegeAdminLoginView(StudentLoginView):
    template_name = "college_admin_login.html"
    authentication_form = CollegeAdminLoginForm

    def get_success_url(self):
        return reverse("college_dashboard")
