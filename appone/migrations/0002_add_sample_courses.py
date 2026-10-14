from django.db import migrations


COURSES = [
    {
        "name": "Bachelor of Computer Applications",
        "code": "BCA",
        "category": "undergraduate",
        "department": "Computer Applications",
        "duration": "3 Years",
        "eligibility": "12th Pass",
        "description": "Build a strong foundation in computing, programming, and software development.",
    },
    {
        "name": "Bachelor of Commerce",
        "code": "BCOM",
        "category": "undergraduate",
        "department": "Commerce",
        "duration": "3 Years",
        "eligibility": "12th Pass",
        "description": "Explore accounting, business, finance, and the fundamentals of commerce.",
    },
    {
        "name": "B.Sc Computer Science",
        "code": "BSCCS",
        "category": "undergraduate",
        "department": "Computer Science",
        "duration": "3 Years",
        "eligibility": "12th Pass",
        "description": "Study computer science concepts, software, and emerging technologies.",
    },
    {
        "name": "Professional Diploma Programs",
        "code": "DIP",
        "category": "diploma",
        "department": "Professional Studies",
        "duration": "1-2 Years",
        "eligibility": "12th Pass",
        "description": "Develop practical, career-focused skills through professional diploma study.",
    },
]


def add_sample_courses(apps, schema_editor):
    Course = apps.get_model("appone", "Course")
    Course.objects.using(schema_editor.connection.alias).bulk_create(
        Course(**course) for course in COURSES
    )


def remove_sample_courses(apps, schema_editor):
    Course = apps.get_model("appone", "Course")
    Course.objects.using(schema_editor.connection.alias).filter(
        code__in=[course["code"] for course in COURSES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("appone", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_sample_courses, remove_sample_courses),
    ]
