# Generated by Django 3.2.7 on 2021-11-10 17:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_alter_customuser_email"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="username",
            field=models.CharField(max_length=24, null=True, unique=True),
        ),
    ]
