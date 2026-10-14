import json
import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.urls import reverse

from .forms import AdmissionApplicationForm
from .models import AdmissionApplication, ContactMessage, Course, Payment, StudentProfile


class CourseListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = Course.objects.create(
            name="Bachelor of Computer Applications",
            code="TEST-BCA",
            category=Course.Category.UNDERGRADUATE,
            department="Computer Applications",
            duration="3 Years",
            eligibility="12th Pass",
            description="An introduction to computing and software development.",
        )
        Course.objects.create(
            name="Inactive Program",
            code="TEST-INACTIVE",
            category=Course.Category.DIPLOMA,
            department="Professional Studies",
            duration="1 Year",
            eligibility="12th Pass",
            description="An inactive program.",
            is_active=False,
        )

    def test_lists_active_courses_with_details(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.name)
        self.assertContains(response, self.course.code)
        self.assertContains(response, self.course.department)
        self.assertContains(response, f'href="{reverse("course_detail", args=(self.course.pk,))}"')
        self.assertNotContains(response, self.course.description)
        self.assertNotContains(response, self.course.eligibility)
        self.assertNotContains(response, "Inactive Program")
        self.assertTemplateUsed(response, "course.html")
        self.assertContains(response, f'href="{reverse("admission_application")}"')
        self.assertContains(response, f'href="{reverse("contact")}"')

    def test_course_details_require_login_then_return_to_selected_course(self):
        detail_url = reverse("course_detail", args=(self.course.pk,))
        response = self.client.get(detail_url)
        self.assertRedirects(response, f"{reverse('login')}?next={detail_url}")

        get_user_model().objects.create_user(
            username="student",
            email="student@example.edu",
            password="StrongExamplePassword482!",
        )
        response = self.client.post(
            f"{reverse('login')}?next={detail_url}",
            {"username": "student@example.edu", "password": "StrongExamplePassword482!"},
        )
        self.assertRedirects(response, detail_url)

    def test_logged_in_student_can_view_course_details(self):
        user = get_user_model().objects.create_user(
            username="course-viewer",
            email="viewer@example.edu",
            password="safe-pass-123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("course_detail", args=(self.course.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "course_detail.html")
        self.assertContains(response, self.course.description)
        self.assertContains(response, self.course.eligibility)

    def test_empty_course_catalog_shows_helpful_message(self):
        Course.objects.all().delete()

        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Programs are being added")


class AdmissionPageTests(TestCase):
    def setUp(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    @classmethod
    def setUpTestData(cls):
        cls.course = Course.objects.create(
            name="Bachelor of Computer Applications",
            code="ADMISSION-BCA",
            category=Course.Category.UNDERGRADUATE,
            department="Computer Applications",
            duration="3 Years",
            eligibility="12th Pass",
            description="Computing and application development.",
            fees=Decimal("125.00"),
        )
        cls.diploma_course = Course.objects.create(
            name="Diploma in Computer Applications",
            code="ADMISSION-DIPLOMA",
            category=Course.Category.DIPLOMA,
            department="Computer Applications",
            duration="1 Year",
            eligibility="10th Pass",
            description="Diploma course for admission form tests.",
            fees=Decimal("100.00"),
        )

    def test_admission_page_shows_process_documents_and_anonymous_actions(self):
        response = self.client.get(reverse("admission"))

        self.assertEqual(response.status_code, 200)
        for text in (
            "Online Admission",
            "Register Account",
            "Login",
            "Fill Application",
            "Upload Documents",
            "Submit Application",
            "Check Application Status",
            "Passport-size photograph",
            "Identity proof",
            "10th certificate",
            "12th certificate",
            "Transfer certificate",
            "Login &amp; Apply",
            "New Student? Register",
        ):
            self.assertContains(response, text)
        self.assertContains(response, reverse("admission_application"))

    def test_home_and_about_calls_to_action_use_named_destination_routes(self):
        home = self.client.get(reverse("home"))
        about = self.client.get(reverse("about"))

        self.assertEqual(home.status_code, 200)
        self.assertTemplateUsed(home, "home.html")
        self.assertContains(home, f'href="{reverse("admission_application")}"')
        self.assertContains(home, f'href="{reverse("courses")}"')
        self.assertContains(home, f'href="{reverse("about")}"')
        self.assertEqual(about.status_code, 200)
        self.assertContains(about, f'href="{reverse("admission_application")}"')
        self.assertContains(about, f'href="{reverse("courses")}"')

    def test_root_url_opens_public_home_page_for_signed_in_student(self):
        user = get_user_model().objects.create_user(username="home-student")
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertContains(response, "Start Your Educational Journey With Us")

    def test_authenticated_actions_open_application_and_dashboard(self):
        user = get_user_model().objects.create_user(username="applicant", password="safe-pass-123")
        self.client.force_login(user)

        response = self.client.get(reverse("admission"))

        self.assertContains(response, reverse("admission_application"))
        self.assertContains(response, reverse("admission_dashboard"))
        self.assertNotContains(response, "New Student? Register")

    def test_anonymous_application_redirects_to_login_with_return_path(self):
        response = self.client.get(reverse("admission_application"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('admission_application')}",
        )

    def test_login_returns_applicant_to_the_application_form(self):
        user = get_user_model().objects.create_user(username="returning", password="safe-pass-123")

        response = self.client.post(
            f"{reverse('login')}?next={reverse('admission_application')}",
            {"username": user.username, "password": "safe-pass-123"},
        )

        self.assertRedirects(response, reverse("admission_application"))

    def test_registration_creates_account_and_opens_application(self):
        response = self.client.post(
            reverse("register"),
            {
                "full_name": "New Student",
                "email": "student@example.edu",
                "mobile_number": "+91 98765 43210",
                "password1": "StrongExamplePassword482!",
                "password2": "StrongExamplePassword482!",
                "terms_accepted": "on",
            },
        )

        self.assertRedirects(response, reverse("admission_application"))
        user = get_user_model().objects.get(email="student@example.edu")
        self.assertEqual(user.username, "student@example.edu")
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "Student")
        self.assertEqual(user.student_profile.mobile_number, "+91 98765 43210")
        self.assertIsNotNone(user.student_profile.terms_accepted_at)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 14)
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_registration_page_shows_requested_fields_and_login_link(self):
        response = self.client.get(reverse("register"))

        self.assertEqual(response.status_code, 200)
        for text in (
            "Create Your Student Account",
            "Register to start your online admission application.",
            "Full Name",
            "Email",
            "Mobile Number",
            "Password",
            "Confirm Password",
            "Terms &amp; Conditions",
            "Privacy Policy",
            "Create Account",
            "Already have an account?",
            "Login",
        ):
            self.assertContains(response, text)
        self.assertContains(response, f'action="{reverse("register")}"')
        self.assertTemplateUsed(response, "register.html")

    def test_registration_rejects_invalid_fields_and_does_not_create_account(self):
        invalid_data = {
            "full_name": "",
            "email": "not-an-email",
            "mobile_number": "123abc",
            "password1": "short",
            "password2": "different",
        }

        response = self.client.post(reverse("register"), invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.filter(email="not-an-email").count(), 0)
        self.assertContains(response, "This field is required")
        self.assertContains(response, "Enter a valid phone number")
        self.assertContains(response, "You must accept the Terms")

    def test_registration_rejects_duplicate_email(self):
        get_user_model().objects.create_user(
            username="existingstudent",
            email="existing@example.edu",
            password="ExistingPassword482!",
        )

        response = self.client.post(
            reverse("register"),
            {
                "full_name": "New Student",
                "email": "EXISTING@example.edu",
                "mobile_number": "9876543210",
                "password1": "StrongExamplePassword482!",
                "password2": "StrongExamplePassword482!",
                "terms_accepted": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists")
        self.assertEqual(get_user_model().objects.filter(email__iexact="existing@example.edu").count(), 1)

    def test_authenticated_user_can_submit_and_track_application(self):
        user = get_user_model().objects.create_user(username="student")
        self.client.force_login(user)

        response = self.client.post(
            reverse("admission_application"),
            {
                "course": self.course.pk,
                "date_of_birth": "2000-01-02",
                "category": "general",
                "phone": "555-0101",
                "highest_qualification": "12th Pass",
                "payment_option": "direct",
                "passport_photo": SimpleUploadedFile("photo.jpg", b"photo"),
                "student_signature": SimpleUploadedFile("signature.png", b"signature"),
                "identity_proof": SimpleUploadedFile("identity.pdf", b"identity"),
                "tenth_certificate": SimpleUploadedFile("tenth.pdf", b"tenth"),
                "twelfth_certificate": SimpleUploadedFile("twelfth.pdf", b"twelfth"),
                "conduct_certificate": SimpleUploadedFile("conduct.pdf", b"conduct"),
            },
        )

        application = AdmissionApplication.objects.get(applicant=user)
        self.assertRedirects(response, reverse("admission_dashboard"))
        self.assertEqual(application.course, self.course)
        dashboard = self.client.get(reverse("admission_dashboard"))
        self.assertContains(dashboard, "Pending")
        self.assertNotContains(dashboard, str(application.application_number))
        self.assertNotContains(dashboard, self.course.name)
        self.assertNotContains(dashboard, "555-0101")
        self.assertNotContains(dashboard, "Course fee")

    def test_declined_application_shows_only_rejected_status(self):
        user = get_user_model().objects.create_user(username="declined-applicant")
        self.client.force_login(user)
        AdmissionApplication.objects.create(
            applicant=user,
            course=self.course,
            phone="555-0103",
            highest_qualification="12th Pass",
            status=AdmissionApplication.Status.DECLINED,
        )

        response = self.client.get(reverse("admission_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rejected")
        self.assertNotContains(response, "Declined")
        self.assertNotContains(response, self.course.name)
        self.assertNotContains(response, "555-0103")

    def test_accepted_application_shows_only_approved_status(self):
        user = get_user_model().objects.create_user(username="accepted-applicant")
        self.client.force_login(user)
        AdmissionApplication.objects.create(
            applicant=user,
            course=self.course,
            phone="555-0105",
            highest_qualification="12th Pass",
            status=AdmissionApplication.Status.ACCEPTED,
        )

        response = self.client.get(reverse("admission_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved")
        self.assertNotContains(response, "Accepted")
        self.assertNotContains(response, self.course.name)
        self.assertNotContains(response, "555-0105")

    def test_under_review_application_shows_decision_as_pending(self):
        user = get_user_model().objects.create_user(username="review-applicant")
        self.client.force_login(user)
        AdmissionApplication.objects.create(
            applicant=user,
            course=self.course,
            phone="555-0104",
            highest_qualification="12th Pass",
            status=AdmissionApplication.Status.UNDER_REVIEW,
        )

        response = self.client.get(reverse("admission_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending")
        self.assertNotContains(response, "Under review")
        self.assertNotContains(response, self.course.name)

    def test_sc_applicant_can_submit_and_download_caste_certificate(self):
        user = get_user_model().objects.create_user(username="sc-applicant")
        self.client.force_login(user)

        response = self.client.post(
            reverse("admission_application"),
            {
                "course": self.course.pk,
                "date_of_birth": "2000-01-02",
                "category": "sc",
                "phone": "555-0106",
                "highest_qualification": "12th Pass",
                "payment_option": "direct",
                "passport_photo": SimpleUploadedFile("photo.jpg", b"photo"),
                "student_signature": SimpleUploadedFile("signature.png", b"signature"),
                "identity_proof": SimpleUploadedFile("identity.pdf", b"identity"),
                "tenth_certificate": SimpleUploadedFile("tenth.pdf", b"tenth"),
                "twelfth_certificate": SimpleUploadedFile("twelfth.pdf", b"twelfth"),
                "conduct_certificate": SimpleUploadedFile("conduct.pdf", b"conduct"),
                "caste_certificate": SimpleUploadedFile("caste.pdf", b"caste"),
            },
        )

        application = AdmissionApplication.objects.get(applicant=user)
        self.assertRedirects(response, reverse("admission_dashboard"))
        self.assertEqual(application.category, AdmissionApplication.Category.SC)
        self.assertTrue(application.caste_certificate)

        dashboard = self.client.get(reverse("admission_dashboard"))
        self.assertContains(dashboard, "Pending")
        self.assertNotContains(dashboard, "Caste certificate")
        document = self.client.get(
            reverse("admission_document", args=(application.pk, "caste_certificate"))
        )
        self.assertEqual(document.status_code, 200)
        self.assertEqual(b"".join(document.streaming_content), b"caste")

    def test_diploma_application_does_not_require_twelfth_certificate(self):
        user = get_user_model().objects.create_user(username="diploma-applicant")
        self.client.force_login(user)

        response = self.client.post(
            reverse("admission_application"),
            {
                "course": self.diploma_course.pk,
                "date_of_birth": "2001-02-03",
                "category": "general",
                "phone": "555-0102",
                "highest_qualification": "10th Pass",
                "payment_option": "direct",
                "passport_photo": SimpleUploadedFile("photo.jpg", b"photo"),
                "student_signature": SimpleUploadedFile("signature.png", b"signature"),
                "identity_proof": SimpleUploadedFile("identity.pdf", b"identity"),
                "tenth_certificate": SimpleUploadedFile("tenth.pdf", b"tenth"),
                "conduct_certificate": SimpleUploadedFile("conduct.pdf", b"conduct"),
            },
        )

        application = AdmissionApplication.objects.get(applicant=user)
        self.assertRedirects(response, reverse("admission_dashboard"))
        self.assertEqual(application.course, self.diploma_course)
        self.assertFalse(application.twelfth_certificate)

    def test_non_diploma_application_still_requires_twelfth_certificate(self):
        user = get_user_model().objects.create_user(username="undergraduate-applicant")
        self.client.force_login(user)

        response = self.client.post(
            reverse("admission_application"),
            {
                "course": self.course.pk,
                "date_of_birth": "2000-03-04",
                "category": "general",
                "phone": "555-0103",
                "highest_qualification": "12th Pass",
                "payment_option": "direct",
                "passport_photo": SimpleUploadedFile("photo.jpg", b"photo"),
                "student_signature": SimpleUploadedFile("signature.png", b"signature"),
                "identity_proof": SimpleUploadedFile("identity.pdf", b"identity"),
                "tenth_certificate": SimpleUploadedFile("tenth.pdf", b"tenth"),
                "conduct_certificate": SimpleUploadedFile("conduct.pdf", b"conduct"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertFalse(AdmissionApplication.objects.filter(applicant=user).exists())

    def test_application_form_shows_both_course_fee_payment_choices(self):
        user = get_user_model().objects.create_user(
            username="payment-choice-student",
            password="safe-pass-123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admission_application"))

        self.assertContains(response, "Pay online")
        self.assertContains(response, "Pay directly at the college")
        self.assertContains(response, 'class="application-payment-option-list"')
        self.assertContains(response, "no separate admission registration or service charge")
        self.assertContains(response, "Course fee: INR 125.00")
        for text in ("Date of birth", "Category", "Student signature", "Conduct certificate", "Caste certificate"):
            self.assertContains(response, text)
        self.assertContains(response, 'data-caste-certificate-categories="sc,st"')

    def test_application_status_page_hides_details_and_profile_retains_payment_actions(self):
        user = get_user_model().objects.create_user(username="pending-payment-student")
        application = AdmissionApplication.objects.create(
            applicant=user,
            course=self.course,
            phone="555-0180",
            highest_qualification="12th Pass",
            date_of_birth="2000-08-09",
            category=AdmissionApplication.Category.GENERAL,
        )
        payment = Payment.objects.create(
            application=application,
            student=user,
            course_fee=self.course.fees,
            other_fees=Decimal("0.00"),
            amount=self.course.fees,
            status=Payment.Status.PENDING,
        )
        self.client.force_login(user)
        payment_url = reverse("payment", args=(application.pk,))

        status_page = self.client.get(reverse("admission_dashboard"))
        self.assertContains(status_page, "Pending")
        self.assertNotContains(status_page, "555-0180")
        self.assertNotContains(status_page, "Aug 9, 2000")
        self.assertNotContains(status_page, "12th Pass")
        self.assertNotContains(status_page, "INR 125.00")
        self.assertNotContains(status_page, "Continue online payment")

        profile_page = self.client.get(reverse("student_profile"))
        self.assertContains(profile_page, "555-0180")
        self.assertContains(profile_page, "Aug 9, 2000")
        self.assertContains(profile_page, "12th Pass")
        self.assertContains(profile_page, "INR 125.00")
        self.assertContains(profile_page, f'href="{payment_url}">Continue online payment</a>')

    def test_sc_and_st_applicants_must_upload_a_caste_certificate(self):
        for category in ("sc", "st"):
            with self.subTest(category=category):
                form = AdmissionApplicationForm(
                    data={
                        "course": self.course.pk,
                        "date_of_birth": "2000-01-02",
                        "category": category,
                        "phone": "555-0104",
                        "highest_qualification": "12th Pass",
                        "payment_option": "direct",
                    },
                    files={
                        "passport_photo": SimpleUploadedFile("photo.jpg", b"photo"),
                        "student_signature": SimpleUploadedFile("signature.png", b"signature"),
                        "identity_proof": SimpleUploadedFile("identity.pdf", b"identity"),
                        "tenth_certificate": SimpleUploadedFile("tenth.pdf", b"tenth"),
                        "twelfth_certificate": SimpleUploadedFile("twelfth.pdf", b"twelfth"),
                        "conduct_certificate": SimpleUploadedFile("conduct.pdf", b"conduct"),
                    },
                )

                self.assertFalse(form.is_valid())
                self.assertIn("caste_certificate", form.errors)

    def test_non_sc_st_applicants_do_not_need_a_caste_certificate(self):
        form = AdmissionApplicationForm(
            data={
                "course": self.course.pk,
                "date_of_birth": "2000-01-02",
                "category": "general",
                "phone": "555-0105",
                "highest_qualification": "12th Pass",
                "payment_option": "direct",
            },
            files={
                "passport_photo": SimpleUploadedFile("photo.jpg", b"photo"),
                "student_signature": SimpleUploadedFile("signature.png", b"signature"),
                "identity_proof": SimpleUploadedFile("identity.pdf", b"identity"),
                "tenth_certificate": SimpleUploadedFile("tenth.pdf", b"tenth"),
                "twelfth_certificate": SimpleUploadedFile("twelfth.pdf", b"twelfth"),
                "conduct_certificate": SimpleUploadedFile("conduct.pdf", b"conduct"),
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_non_sc_st_applicants_cannot_submit_a_caste_certificate(self):
        form = AdmissionApplicationForm(
            data={
                "course": self.course.pk,
                "date_of_birth": "2000-01-02",
                "category": "general",
                "phone": "555-0105",
                "highest_qualification": "12th Pass",
                "payment_option": "direct",
            },
            files={
                "passport_photo": SimpleUploadedFile("photo.jpg", b"photo"),
                "student_signature": SimpleUploadedFile("signature.png", b"signature"),
                "identity_proof": SimpleUploadedFile("identity.pdf", b"identity"),
                "tenth_certificate": SimpleUploadedFile("tenth.pdf", b"tenth"),
                "twelfth_certificate": SimpleUploadedFile("twelfth.pdf", b"twelfth"),
                "conduct_certificate": SimpleUploadedFile("conduct.pdf", b"conduct"),
                "caste_certificate": SimpleUploadedFile("caste.pdf", b"caste"),
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("only be submitted by SC or ST", str(form.errors["caste_certificate"]))


class CollegeDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = Course.objects.create(
            name="College Dashboard Course",
            code="COLLEGE-DASH",
            category=Course.Category.UNDERGRADUATE,
            department="Admissions",
            duration="3 Years",
            eligibility="12th Pass",
            description="Course for college dashboard tests.",
        )
        cls.student = get_user_model().objects.create_user(
            username="college-dashboard-student",
            email="student-dashboard@example.edu",
            password="safe-pass-123",
            first_name="Student",
        )
        cls.application = AdmissionApplication.objects.create(
            applicant=cls.student,
            course=cls.course,
            phone="555-0111",
            highest_qualification="12th Pass",
        )

    def test_dashboard_requires_authenticated_college_staff(self):
        response = self.client.get(reverse("college_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('college_admin_login')}?next={reverse('college_dashboard')}",
        )

        self.client.force_login(self.student)
        self.assertRedirects(
            self.client.get(reverse("college_dashboard")),
            f"{reverse('college_admin_login')}?next={reverse('college_dashboard')}",
        )

    def test_staff_dashboard_shows_counts_and_decision_actions(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("college_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["counts"]["total"], 1)
        self.assertEqual(response.context["counts"]["submitted"], 1)
        self.assertContains(response, str(self.application.application_number))
        self.assertContains(response, self.application.phone)
        self.assertContains(response, self.application.highest_qualification)
        self.assertContains(response, "No documents uploaded")
        self.assertContains(response, "Approve")
        self.assertContains(response, "Decline")
        self.assertContains(response, "College Information")
        self.assertContains(response, "Student Applications")
        self.assertContains(response, "Django Admin")
        self.assertContains(response, f'href="{reverse("admin:index")}"')
        self.assertContains(response, "Logout")
        self.assertNotContains(response, "Student Dashboard")
        self.assertNotContains(response, "My Application")

    def test_college_profile_is_staff_only(self):
        profile_url = reverse("college_profile")
        self.assertRedirects(
            self.client.get(profile_url),
            f"{reverse('college_admin_login')}?next={profile_url}",
        )

        other_staff = get_user_model().objects.create_user(
            username="unapproved-college-staff",
            password="SafeStaffPassword482!",
            is_staff=True,
        )
        self.client.force_login(other_staff)
        self.assertRedirects(
            self.client.get(reverse("college_dashboard")),
            f"{reverse('college_admin_login')}?next={reverse('college_dashboard')}",
        )

        self.client.logout()
        self.client.force_login(self.student)
        self.assertRedirects(
            self.client.get(profile_url),
            f"{reverse('college_admin_login')}?next={profile_url}",
        )

        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
            email="admin@example.edu",
        )
        self.client.force_login(staff)
        response = self.client.get(profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin@example.edu")

    def test_staff_can_approve_but_students_cannot_change_application_status(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse("college_application_action", args=(self.application.pk, "approve"))
        )

        self.assertRedirects(response, reverse("college_dashboard"))
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, AdmissionApplication.Status.ACCEPTED)

        self.client.force_login(self.student)
        denied = self.client.post(
            reverse("college_application_action", args=(self.application.pk, "decline"))
        )
        self.assertEqual(denied.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, AdmissionApplication.Status.ACCEPTED)

    def test_college_admin_button_is_only_at_bottom_of_home_page(self):
        anonymous_page = self.client.get(reverse("home"))
        self.assertEqual(anonymous_page.status_code, 200)
        self.assertTemplateUsed(anonymous_page, "home.html")
        self.assertNotContains(anonymous_page, "College Applications")
        self.assertContains(anonymous_page, "College Admin Login")
        self.assertContains(anonymous_page, f'href="{reverse("college_admin_login")}"')
        self.assertGreater(
            anonymous_page.content.index(b"College Admin Login"),
            anonymous_page.content.index(b"Admissions Open for 2026"),
        )

        self.client.force_login(self.student)
        student_home = self.client.get(reverse("home"))
        self.assertContains(student_home, "College Admin Login")
        student_page = self.client.get(reverse("admission_dashboard"))
        self.assertNotContains(student_page, "College Admin Login")
        self.assertNotContains(student_page, "College Applications")

        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
        )
        self.client.force_login(staff)
        staff_home = self.client.get(reverse("home"))
        self.assertContains(staff_home, "College Admin Login")
        self.assertNotContains(staff_home, "Student Dashboard")
        staff_other_page = self.client.get(reverse("courses"))
        self.assertNotContains(staff_other_page, "College Applications")

    def test_college_admin_can_delete_application(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff)
        course = Course.objects.create(
            name="App Delete Course",
            code="APP-DEL",
            category=Course.Category.UNDERGRADUATE,
            department="Arts",
            duration="3 Years",
            eligibility="12th Pass",
            description="Course for delete app test.",
        )
        app = AdmissionApplication.objects.create(
            applicant=self.student,
            course=course,
            phone="555-0999",
            highest_qualification="12th Pass",
        )
        Payment.objects.create(
            application=app,
            student=self.student,
            course_fee=Decimal("120.00"),
            amount=Decimal("120.00"),
        )
        delete_url = reverse("college_application_delete", args=(app.pk,))
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("college_dashboard"))
        self.assertFalse(AdmissionApplication.objects.filter(pk=app.pk).exists())
        self.assertFalse(Payment.objects.filter(application_id=app.pk).exists())

    def test_college_admin_can_delete_course_with_applications(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff)
        course = Course.objects.create(
            name="Delete Me Course",
            code="DEL-ME",
            category=Course.Category.UNDERGRADUATE,
            department="Science",
            duration="3 Years",
            eligibility="12th Pass",
            description="Course to be deleted.",
        )
        AdmissionApplication.objects.create(
            applicant=self.student,
            course=course,
            phone="555-0888",
            highest_qualification="12th Pass",
        )
        delete_url = reverse("admin_course_delete", args=(course.pk,))
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("admin_course_list"))
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())

    def test_admin_course_edit_page_contains_delete_button(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff)
        edit_url = reverse("admin_course_edit", args=(self.course.pk,))
        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Course")

    def test_college_admin_has_django_admin_access(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="safe-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Courses")
        self.assertContains(response, "Admission applications")


class AdmissionPaymentTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.student = get_user_model().objects.create_user(
            username="payment-student",
            email="payment@example.edu",
            password="SafeStudentPassword482!",
            first_name="Test Student",
        )
        self.course = Course.objects.create(
            name="Payment Test Course",
            code="PAYMENT-TEST",
            category=Course.Category.UNDERGRADUATE,
            department="Testing",
            duration="3 Years",
            eligibility="12th Pass",
            description="Payment test course.",
            fees=Decimal("135.00"),
        )
        self.application = AdmissionApplication.objects.create(
            applicant=self.student,
            course=self.course,
            phone="555-0101",
            highest_qualification="12th Pass",
            status=AdmissionApplication.Status.ACCEPTED,
        )
        self.client.force_login(self.student)
        self.payment_url = reverse("payment", args=(self.application.pk,))

    @patch("appone.views.create_order", return_value=("rzp_test_key", "order_test_123"))
    def test_payment_charges_only_the_course_fee(self, create_order_mock):
        self.application.status = AdmissionApplication.Status.SUBMITTED
        self.application.save(update_fields=("status",))
        response = self.client.post(
            self.payment_url,
            {"action": "start_online_payment"},
        )

        payment = Payment.objects.get(application=self.application)
        self.assertEqual(payment.course_fee, Decimal("135.00"))
        self.assertEqual(payment.amount, Decimal("135.00"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["payment_amount_paise"], 13500)
        self.assertContains(response, "Course fee")
        self.assertNotContains(response, "Other applicable fees")
        create_order_mock.assert_called_once_with(payment)

    def test_unconfigured_course_fee_has_no_payment_option(self):
        self.course.fees = None
        self.course.save(update_fields=("fees",))

        response = self.client.get(self.payment_url, follow=True)

        self.assertRedirects(response, reverse("admission_dashboard"))
        self.assertContains(response, "The course fee is not configured.")
        self.assertFalse(Payment.objects.filter(application=self.application).exists())

    def test_successful_historical_payment_receipt_remains_available(self):
        payment = Payment.objects.create(
            application=self.application,
            student=self.student,
            course_fee=Decimal("110.00"),
            other_fees=Decimal("25.00"),
            amount=Decimal("135.00"),
            transaction_id="legacy_transaction",
            receipt_number="RCP-LEGACY",
            status=Payment.Status.SUCCESSFUL,
            paid_at=timezone.now(),
        )

        dashboard = self.client.get(reverse("admission_dashboard"))
        self.assertNotContains(dashboard, "Download course-fee receipt")
        receipt = self.client.get(reverse("payment_receipt", args=(payment.pk,)))
        self.assertEqual(receipt["Content-Type"], "application/pdf")

    @patch("appone.views.verify_webhook_signature", return_value=True)
    def test_signed_gateway_webhooks_update_failed_captured_and_refunded_statuses(
        self, signature_mock
    ):
        payment = Payment.objects.create(
            application=self.application,
            student=self.student,
            course_fee=Decimal("135.00"),
            amount=Decimal("135.00"),
            gateway_order_id="order_test_123",
        )
        failure_event = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_123",
                        "order_id": "order_test_123",
                        "amount": 13500,
                        "currency": "INR",
                    }
                }
            },
        }
        response = self.client.post(
            reverse("razorpay_webhook"),
            json.dumps(failure_event),
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="signed",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

        captured_event = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_456",
                        "order_id": "order_test_123",
                        "amount": 13500,
                        "currency": "INR",
                        "method": "upi",
                    }
                }
            },
        }
        response = self.client.post(
            reverse("razorpay_webhook"),
            json.dumps(captured_event),
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="signed",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESSFUL)
        self.assertIsNotNone(payment.receipt_number)

        refund_event = {
            "event": "refund.processed",
            "payload": {
                "refund": {
                    "entity": {
                        "payment_id": "pay_test_456",
                        "amount": 13500,
                    }
                }
            },
        }
        response = self.client.post(
            reverse("razorpay_webhook"),
            json.dumps(refund_event),
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="signed",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(signature_mock.call_count, 3)


class ContactPageTests(TestCase):
    def test_contact_page_shows_details_and_required_fields(self):
        response = self.client.get(reverse("contact"))

        self.assertEqual(response.status_code, 200)
        for text in (
            "Contact Us",
            "Have questions about admission?",
            "Institution address",
            "+91 1234567890",
            "admission@gmail.com",
            "Monday – Saturday",
            "9:00 AM – 5:00 PM",
            "Full Name",
            "Email",
            "Phone Number",
            "Subject",
            "Message",
            "Send Message",
        ):
            self.assertContains(response, text)
        self.assertTemplateUsed(response, "contact.html")

    def test_valid_message_is_saved_and_confirmation_is_shown(self):
        response = self.client.post(
            reverse("contact"),
            {
                "full_name": "Riya Student",
                "email": "riya@example.com",
                "phone_number": "+91 9876543210",
                "subject": "Admission question",
                "message": "Please share the application dates.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("contact"))
        message = ContactMessage.objects.get(email="riya@example.com")
        self.assertEqual(message.full_name, "Riya Student")
        self.assertEqual(message.subject, "Admission question")
        confirmation = self.client.get(response["Location"])
        self.assertContains(confirmation, "Thank you for your message")

    def test_invalid_contact_message_is_not_saved(self):
        response = self.client.post(
            reverse("contact"),
            {
                "full_name": "",
                "email": "not-an-email",
                "phone_number": "",
                "subject": "",
                "message": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertContains(response, "This field is required")


class StudentLoginPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="loginstudent",
            email="loginstudent@example.edu",
            password="SafeStudentPassword482!",
        )

    def test_login_page_shows_student_login_options(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        for text in ("Student Login", "Email / Username", "Password", "Remember Me", "Forgot Password?", "Create New Account"):
            self.assertContains(response, text)
        self.assertContains(response, reverse("register"))
        self.assertContains(response, reverse("password_reset"))
        self.assertTemplateUsed(response, "login.html")

    def test_college_admin_login_page_is_linked_and_has_staff_login_form(self):
        home = self.client.get(reverse("home"))
        self.assertContains(
            home,
            f'href="{reverse("college_admin_login")}"',
        )

        response = self.client.get(reverse("college_admin_login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "college_admin_login.html")
        self.assertContains(response, "College Admin Login")
        self.assertNotContains(response, f'href="{reverse("admin:index")}"')
        self.assertNotContains(response, ">Admin</a>")
        self.assertNotContains(response, ">Student login</a>")

    def test_college_admin_login_only_accepts_the_configured_admin(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="SafeStaffPassword482!",
            is_staff=True,
        )
        response = self.client.post(
            reverse("college_admin_login"),
            {"username": staff.username, "password": "SafeStaffPassword482!"},
        )

        self.assertRedirects(response, reverse("college_dashboard"))

        self.client.logout()
        other_staff = get_user_model().objects.create_user(
            username="other-college-staff",
            password="SafeStaffPassword482!",
            is_staff=True,
        )
        response = self.client.post(
            reverse("college_admin_login"),
            {"username": other_staff.username, "password": "SafeStaffPassword482!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account does not have college administrator access.")
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.post(
            reverse("college_admin_login"),
            {"username": self.user.username, "password": "SafeStudentPassword482!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account does not have college administrator access.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_student_nav_has_the_four_requested_links(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))
        primary_nav_start = response.content.index(b'<nav class="primary-nav"')
        primary_nav_end = response.content.index(b"</nav>", primary_nav_start)
        primary_nav = response.content[primary_nav_start:primary_nav_end]

        for label, url_name in (
            ("Profile", "student_profile"),
            ("New Application", "admission_application"),
            ("Application Status", "admission_dashboard"),
            ("Logout", "logout"),
        ):
            with self.subTest(label=label):
                self.assertIn(f'href="{reverse(url_name)}"'.encode(), primary_nav)
                self.assertIn(f">{label}</a>".encode(), primary_nav)
        for label in ("Home</a>", "About</a>", "Courses</a>", "Admission</a>", "Contact</a>"):
            self.assertNotIn(label.encode(), primary_nav)

    def test_student_can_login_with_username_and_remember_session(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "SafeStudentPassword482!", "remember_me": "on"},
        )

        self.assertRedirects(response, reverse("student_profile"))
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 14)

    def test_student_can_login_with_email_and_session_expires_on_browser_close(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "SafeStudentPassword482!"},
        )

        self.assertRedirects(response, reverse("student_profile"))
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_college_staff_login_returns_to_college_dashboard(self):
        staff = get_user_model().objects.create_user(
            username="admin123",
            password="SafeStaffPassword482!",
            is_staff=True,
        )
        dashboard_url = reverse("college_dashboard")

        response = self.client.get(dashboard_url)
        self.assertRedirects(response, f"{reverse('college_admin_login')}?next={dashboard_url}")
        self.assertEqual(self.client.get(response.url).status_code, 200)

        response = self.client.post(
            f"{reverse('login')}?next={dashboard_url}",
            {"username": staff.username, "password": "SafeStaffPassword482!"},
        )

        self.assertRedirects(response, dashboard_url)
        self.assertEqual(self.client.get(dashboard_url).status_code, 200)

    def test_profile_page_shows_logged_in_user_details(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "SafeStudentPassword482!"},
        )

        self.assertRedirects(response, reverse("student_profile"))
        profile = self.client.get(reverse("student_profile"))
        self.assertContains(profile, "My Profile")
        self.assertContains(profile, self.user.username)
        self.assertContains(profile, self.user.email)
        self.assertContains(profile, "No application details yet")

    def test_application_status_page_does_not_show_personal_details(self):
        self.user.first_name = "Jamie"
        self.user.last_name = "Student"
        self.user.save(update_fields=("first_name", "last_name"))
        StudentProfile.objects.create(
            user=self.user,
            mobile_number="+91 98765 43210",
            terms_accepted_at=timezone.now(),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("admission_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Jamie Student")
        self.assertNotContains(response, self.user.email)
        self.assertNotContains(response, "+91 98765 43210")

    def test_profile_shows_only_current_users_submitted_application_details(self):
        own_course = Course.objects.create(
            name="Profile Test Course",
            code="PROFILE-COURSE",
            category=Course.Category.UNDERGRADUATE,
            department="Admissions",
            duration="3 Years",
            eligibility="12th Pass",
            description="Course for student profile test.",
        )
        AdmissionApplication.objects.create(
            applicant=self.user,
            course=own_course,
            phone="555-0199",
            highest_qualification="12th Pass",
            date_of_birth="2001-04-05",
            category=AdmissionApplication.Category.SC,
        )
        another_user = get_user_model().objects.create_user(username="another-profile-student")
        private_course = Course.objects.create(
            name="Private Application Course",
            code="PRIVATE-COURSE",
            category=Course.Category.DIPLOMA,
            department="Admissions",
            duration="1 Year",
            eligibility="10th Pass",
            description="Another student's private application.",
        )
        AdmissionApplication.objects.create(
            applicant=another_user,
            course=private_course,
            phone="555-0188",
            highest_qualification="10th Pass",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("student_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile Test Course")
        self.assertContains(response, "555-0199")
        self.assertContains(response, "Apr 5, 2001")
        self.assertContains(response, "SC")
        self.assertContains(response, "12th Pass")
        self.assertNotContains(response, "Private Application Course")
        self.assertNotContains(response, "555-0188")

    def test_logout_ends_persistent_login_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.client.get(reverse("admission_application")),
            f"{reverse('login')}?next={reverse('admission_application')}",
        )

    def test_next_parameter_is_preserved_during_login(self):
        response = self.client.post(
            f"{reverse('login')}?next={reverse('admission_application')}",
            {"username": self.user.username, "password": "SafeStudentPassword482!"},
        )

        self.assertRedirects(response, reverse("admission_application"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_forgot_password_sends_reset_email(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password reset requested")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset/", mail.outbox[0].body)

    def test_student_can_update_profile_details(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("student_profile"),
            {
                "action": "update_profile",
                "first_name": "Alexander",
                "last_name": "Hamilton",
                "email": "alex.hamilton@example.edu",
                "mobile_number": "+91 91234 56789",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your profile details have been updated successfully.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alexander")
        self.assertEqual(self.user.last_name, "Hamilton")
        self.assertEqual(self.user.email, "alex.hamilton@example.edu")
        self.assertEqual(self.user.student_profile.mobile_number, "+91 91234 56789")

    def test_student_profile_update_rejects_duplicate_email(self):
        get_user_model().objects.create_user(
            username="other-student-dup",
            email="taken@example.edu",
            password="SafePassword123!",
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("student_profile"),
            {
                "action": "update_profile",
                "first_name": "Alex",
                "last_name": "H",
                "email": "taken@example.edu",
                "mobile_number": "+91 91234 56789",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")

    def test_student_can_change_password_from_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("student_profile"),
            {
                "action": "change_password",
                "old_password": "SafeStudentPassword482!",
                "new_password1": "BrandNewSafePass999!",
                "new_password2": "BrandNewSafePass999!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your password has been changed successfully.")
        # Verify user can log in with new password
        self.client.logout()
        login_res = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "BrandNewSafePass999!"},
        )
        self.assertRedirects(login_res, reverse("student_profile"))
