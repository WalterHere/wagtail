# Generated by Django 4.2b1 on 2023-03-21 17:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tests", "0023_snippetchoosermodel_full_featured"),
    ]

    operations = [
        migrations.AddField(
            model_name="fullfeaturedsnippet",
            name="country_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ID", "Indonesia"),
                    ("PH", "Philippines"),
                    ("UK", "United Kingdom"),
                ],
                default="UK",
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name="fullfeaturedsnippet",
            name="some_date",
            field=models.DateField(auto_now=True),
        ),
    ]
