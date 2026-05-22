from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='staff')
    Group.objects.get_or_create(name='doctor')


def delete_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['staff', 'doctor']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0005_doctor_user_link_and_groups'),
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
