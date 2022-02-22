# Generated by Django 4.0.2 on 2022-02-22 13:06

import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailcore", "0066_collection_management_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pagerevision",
            name="content_json",
            field=models.JSONField(
                encoder=django.core.serializers.json.DjangoJSONEncoder,
                verbose_name="content JSON",
            ),
        ),
        migrations.RenameField(
            model_name="pagerevision",
            old_name="content_json",
            new_name="content",
        ),
    ]
