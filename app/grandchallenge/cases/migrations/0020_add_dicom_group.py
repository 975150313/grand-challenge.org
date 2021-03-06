from django.conf import settings
from django.contrib.auth.models import Group
from django.db import migrations


def create_dicom_group(apps, schema_editor):
    Group.objects.create(name=settings.DICOM_DATA_CREATORS_GROUP_NAME)


def remove_dicom_group(apps, schema_editor):
    try:
        Group.objects.get(
            name=settings.DICOM_DATA_CREATORS_GROUP_NAME
        ).delete()
    except Group.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0019_auto_20200120_0604"),
    ]

    operations = [migrations.RunPython(create_dicom_group, remove_dicom_group)]
