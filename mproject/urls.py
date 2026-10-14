"""
URL configuration for mproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from appone.views import (
    admission,
    admission_application,
    admission_dashboard,
    admission_document,
    admin_course_list,
    admin_course_add,
    admin_course_edit,
    admin_course_delete,
    college_application_action,
    college_application_delete,
    college_dashboard,
    CollegeAdminLoginView,
    college_profile,
    course_detail,
    contact,
    course_list,
    logout_view,
    payment,
    payment_receipt,
    razorpay_webhook,
    register,
    student_profile,
    StudentLoginView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
    path('courses/', course_list, name='courses'),
    path('courses/<int:course_id>/', course_detail, name='course_detail'),
    path('admission/', admission, name='admission'),
    path('admission/apply/', admission_application, name='admission_application'),
    path('admission/dashboard/', admission_dashboard, name='admission_dashboard'),
    path('college/applications/', college_dashboard, name='college_dashboard'),
    path('college/login/', CollegeAdminLoginView.as_view(), name='college_admin_login'),
    path('college/applications/<int:application_id>/delete/', college_application_delete, name='college_application_delete'),
    path('college/applications/<int:application_id>/<str:action>/', college_application_action, name='college_application_action'),
    path('college/profile/', college_profile, name='college_profile'),
    path('college/courses/', admin_course_list, name='admin_course_list'),
    path('college/courses/add/', admin_course_add, name='admin_course_add'),
    path('college/courses/<int:course_id>/edit/', admin_course_edit, name='admin_course_edit'),
    path('college/courses/<int:course_id>/delete/', admin_course_delete, name='admin_course_delete'),
    path('profile/', student_profile, name='student_profile'),
    path('admission/<int:application_id>/documents/<str:document_field>/', admission_document, name='admission_document'),
    path('contact/', contact, name='contact'),
    path('login/', StudentLoginView.as_view(), name='login'),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.txt',
        subject_template_name='registration/password_reset_subject.txt',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
    ), name='password_reset_confirm'),
    path('reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('logout/', logout_view, name='logout'),
    path('register/', register, name='register'),
    path('admission/<int:application_id>/payment/', payment, name='payment'),
    path('payments/<int:payment_id>/receipt/', payment_receipt, name='payment_receipt'),
    path('payments/razorpay/webhook/', razorpay_webhook, name='razorpay_webhook'),
]
