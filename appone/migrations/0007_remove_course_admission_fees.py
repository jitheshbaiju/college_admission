from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("appone", "0006_admissionapplication_identity_proof_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="payment",
            old_name="admission_fee",
            new_name="course_fee",
        ),
        migrations.RemoveField(
            model_name="course",
            name="admission_fee",
        ),
        migrations.RemoveField(
            model_name="course",
            name="other_fees",
        ),
    ]
