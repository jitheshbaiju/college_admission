import re
import uuid

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import AdmissionApplication, ContactMessage, Course, StudentProfile


class StudentProfileUpdateForm(forms.Form):
    first_name = forms.CharField(
        label="First Name",
        max_length=150,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "First name",
                "autocomplete": "given-name",
            }
        ),
    )
    last_name = forms.CharField(
        label="Last Name",
        max_length=150,
        required=False,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Last name",
                "autocomplete": "family-name",
            }
        ),
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "you@example.com",
                "autocomplete": "email",
            }
        ),
    )
    mobile_number = forms.CharField(
        label="Mobile Number",
        max_length=30,
        strip=True,
        widget=forms.TelInput(
            attrs={
                "class": "form-control",
                "placeholder": "+91 98765 43210",
                "autocomplete": "tel",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        user_model = get_user_model()
        matches = user_model._default_manager.filter(email__iexact=email)
        if self.user:
            matches = matches.exclude(pk=self.user.pk)
        if matches.exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean_mobile_number(self):
        mobile_number = self.cleaned_data["mobile_number"].strip()
        digits = re.sub(r"\D", "", mobile_number)
        if (
            not re.fullmatch(r"\+?[0-9][0-9\s().-]*", mobile_number)
            or not 8 <= len(digits) <= 15
        ):
            raise forms.ValidationError("Enter a valid phone number with 8 to 15 digits.")
        return mobile_number


class StudentPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})



class RegistrationForm(UserCreationForm):
    full_name = forms.CharField(
        label="Full Name",
        max_length=150,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": "student-register-control",
                "autocomplete": "name",
                "placeholder": "Enter your full name",
            }
        ),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "student-register-control",
                "autocomplete": "email",
                "placeholder": "you@example.com",
            }
        ),
    )
    mobile_number = forms.CharField(
        label="Mobile Number",
        max_length=30,
        strip=True,
        widget=forms.TelInput(
            attrs={
                "class": "student-register-control",
                "autocomplete": "tel",
                "placeholder": "+91 98765 43210",
                "inputmode": "tel",
                "title": "Enter a valid phone number with 8 to 15 digits.",
            }
        ),
    )
    terms_accepted = forms.BooleanField(
        label="I agree to the Terms & Conditions and Privacy Policy.",
        error_messages={"required": "You must accept the Terms & Conditions and Privacy Policy."},
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "student-register-control",
                "autocomplete": "new-password",
                "placeholder": "Create a password",
                "minlength": 8,
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "student-register-control",
                "autocomplete": "new-password",
                "placeholder": "Enter your password again",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if get_user_model()._default_manager.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean_mobile_number(self):
        mobile_number = self.cleaned_data["mobile_number"]
        digits = re.sub(r"\D", "", mobile_number)
        if (
            not re.fullmatch(r"\+?[0-9][0-9\s().-]*", mobile_number)
            or not 8 <= len(digits) <= 15
        ):
            raise forms.ValidationError("Enter a valid phone number with 8 to 15 digits.")
        return mobile_number

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data["full_name"]
        user.first_name, _, user.last_name = full_name.partition(" ")
        user.email = self.cleaned_data["email"]
        username_limit = user._meta.get_field("username").max_length
        user.username = user.email if len(user.email) <= username_limit else uuid.uuid4().hex
        if get_user_model()._default_manager.filter(username__iexact=user.username).exists():
            user.username = uuid.uuid4().hex[:username_limit]

        if commit:
            user.save()
            StudentProfile.objects.create(
                user=user,
                mobile_number=self.cleaned_data["mobile_number"],
                terms_accepted_at=timezone.now(),
            )
            self.save_m2m()
        return user


class StudentLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email / Username",
        widget=forms.TextInput(
            attrs={
                "class": "student-login-control",
                "autocomplete": "username",
                "placeholder": "Enter your email or username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "student-login-control",
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
    )
    remember_me = forms.BooleanField(required=False, label="Remember Me")

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password and "@" in username:
            user_model = get_user_model()
            matches = user_model._default_manager.filter(email__iexact=username)
            if matches.count() == 1:
                self.cleaned_data["username"] = matches.get().get_username()
        return super().clean()


class CollegeAdminLoginForm(StudentLoginForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff or user.get_username() != settings.COLLEGE_ADMIN_USERNAME:
            raise forms.ValidationError(
                "This account does not have college administrator access.",
                code="not_college_admin",
            )


class CourseChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, course):
        if course.fees is None:
            return f"{course.name} - Course fee unavailable"
        return f"{course.name} - Course fee: INR {course.fees:.2f}"


class AdmissionApplicationForm(forms.ModelForm):
    course = CourseChoiceField(
        queryset=Course.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    category = forms.ChoiceField(
        choices=AdmissionApplication.Category.choices,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "data-caste-certificate-categories": "sc,st",
            }
        ),
    )
    payment_option = forms.ChoiceField(
        label="Course fee payment option",
        choices=(
            ("online", "Pay online"),
            ("direct", "Pay directly at the college"),
        ),
        widget=forms.RadioSelect(attrs={"class": "application-payment-option-list"}),
    )

    class Meta:
        model = AdmissionApplication
        fields = (
            "course",
            "date_of_birth",
            "category",
            "phone",
            "highest_qualification",
            "passport_photo",
            "student_signature",
            "identity_proof",
            "tenth_certificate",
            "twelfth_certificate",
            "transfer_certificate",
            "conduct_certificate",
            "caste_certificate",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "phone": forms.TelInput(attrs={"class": "form-control", "autocomplete": "tel"}),
            "highest_qualification": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. 12th grade / bachelor's degree"}
            ),
            "passport_photo": forms.FileInput(attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.pdf"}),
            "student_signature": forms.FileInput(
                attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png"}
            ),
            "identity_proof": forms.FileInput(attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.pdf"}),
            "tenth_certificate": forms.FileInput(attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.pdf"}),
            "twelfth_certificate": forms.FileInput(attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.pdf"}),
            "transfer_certificate": forms.FileInput(attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.pdf"}),
            "conduct_certificate": forms.FileInput(
                attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.pdf"}
            ),
            "caste_certificate": forms.FileInput(
                attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.pdf"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        courses = Course.objects.filter(is_active=True)
        self.fields["course"].queryset = courses
        diploma_course_ids = tuple(
            str(course_id)
            for course_id in courses.filter(category=Course.Category.DIPLOMA).values_list("pk", flat=True)
        )
        self.fields["course"].widget.attrs["data-diploma-course-ids"] = ",".join(diploma_course_ids)
        self.fields["date_of_birth"].required = True
        self.fields["category"].required = True
        selected_course_id = self.data.get("course") or self.initial.get("course")
        is_diploma_course = bool(
            selected_course_id
            and courses.filter(pk=selected_course_id, category=Course.Category.DIPLOMA).exists()
        )
        selected_category = self.data.get("category") or self.initial.get("category", "")
        for field_name in (
            "passport_photo",
            "student_signature",
            "identity_proof",
            "tenth_certificate",
            "conduct_certificate",
        ):
            self.fields[field_name].required = True
        self.fields["twelfth_certificate"].required = not is_diploma_course
        self.fields["transfer_certificate"].required = False
        self.fields["caste_certificate"].required = selected_category in (
            AdmissionApplication.Category.SC,
            AdmissionApplication.Category.ST,
        )

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        if cleaned_data.get("caste_certificate") and category not in (
            AdmissionApplication.Category.SC,
            AdmissionApplication.Category.ST,
        ):
            self.add_error(
                "caste_certificate",
                "A caste certificate can only be submitted by SC or ST applicants.",
            )

        allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf"}
        for field_name in (
            "passport_photo",
            "student_signature",
            "identity_proof",
            "tenth_certificate",
            "twelfth_certificate",
            "transfer_certificate",
            "conduct_certificate",
            "caste_certificate",
        ):
            uploaded = cleaned_data.get(field_name)
            if uploaded:
                extension = uploaded.name.lower().rsplit(".", 1)[-1] if "." in uploaded.name else ""
                file_allowed_extensions = (
                    {".jpg", ".jpeg", ".png"}
                    if field_name == "student_signature"
                    else allowed_extensions
                )
                if f".{extension}" not in file_allowed_extensions:
                    error_message = (
                        "Upload a JPG or PNG image for the student signature."
                        if field_name == "student_signature"
                        else "Upload a JPG, PNG, or PDF file."
                    )
                    self.add_error(field_name, error_message)
                if uploaded.size > 5 * 1024 * 1024:
                    self.add_error(field_name, "Each document must be 5 MB or smaller.")
        return cleaned_data

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data["date_of_birth"]
        if date_of_birth > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return date_of_birth


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("full_name", "email", "phone_number", "subject", "message")
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "contact-control", "autocomplete": "name", "placeholder": "Your full name"}),
            "email": forms.EmailInput(attrs={"class": "contact-control", "autocomplete": "email", "placeholder": "you@example.com"}),
            "phone_number": forms.TelInput(attrs={"class": "contact-control", "autocomplete": "tel", "placeholder": "+91"}),
            "subject": forms.TextInput(attrs={"class": "contact-control", "placeholder": "How can we help?"}),
            "message": forms.Textarea(attrs={"class": "contact-control", "rows": 5, "placeholder": "Write your message here..."}),
        }


class CourseForm(forms.ModelForm):
    """Form for admin to add or edit a course."""

    class Meta:
        model = Course
        fields = (
            "name",
            "code",
            "category",
            "department",
            "duration",
            "eligibility",
            "description",
            "fees",
            "available_seats",
            "image_url",
            "is_active",
        )
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "adm-form-control",
                "placeholder": "e.g. Bachelor of Computer Science",
            }),
            "code": forms.TextInput(attrs={
                "class": "adm-form-control",
                "placeholder": "e.g. BCS101",
            }),
            "category": forms.Select(attrs={"class": "adm-form-control"}),
            "department": forms.TextInput(attrs={
                "class": "adm-form-control",
                "placeholder": "e.g. Computer Science",
            }),
            "duration": forms.TextInput(attrs={
                "class": "adm-form-control",
                "placeholder": "e.g. 3 Years",
            }),
            "eligibility": forms.TextInput(attrs={
                "class": "adm-form-control",
                "placeholder": "e.g. 10+2 with 50% aggregate",
            }),
            "description": forms.Textarea(attrs={
                "class": "adm-form-control",
                "rows": 4,
                "placeholder": "Brief description of the course…",
            }),
            "fees": forms.NumberInput(attrs={
                "class": "adm-form-control",
                "placeholder": "e.g. 45000.00",
                "step": "0.01",
                "min": "0",
            }),
            "available_seats": forms.NumberInput(attrs={
                "class": "adm-form-control",
                "placeholder": "e.g. 60",
                "min": "0",
            }),
            "image_url": forms.URLInput(attrs={
                "class": "adm-form-control",
                "placeholder": "https://…",
            }),
            "is_active": forms.CheckboxInput(attrs={"class": "adm-form-check"}),
        }
        labels = {
            "name": "Course Name",
            "code": "Course Code",
            "category": "Category",
            "department": "Department",
            "duration": "Duration",
            "eligibility": "Eligibility Criteria",
            "description": "Description",
            "fees": "Course Fee (INR)",
            "available_seats": "Available Seats",
            "image_url": "Cover Image URL",
            "is_active": "Active (visible to students)",
        }

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        qs = Course.objects.filter(code__iexact=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A course with this code already exists.")
        return code
