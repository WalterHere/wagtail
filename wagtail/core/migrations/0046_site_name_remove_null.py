# Generated by Django 3.0.6 on 2020-05-27 15:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wagtailcore', '0045_assign_unlock_grouppagepermission'),
    ]

    operations = [
        migrations.AlterField(
            model_name='site',
            name='site_name',
            field=models.CharField(blank=True, default='', help_text='Human-readable name for the site.', max_length=255, verbose_name='site name'),
            preserve_default=False,
        ),
    ]
