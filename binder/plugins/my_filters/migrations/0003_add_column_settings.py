from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('my_filters', '0002_migrate_jsonfield'),
    ]

    operations = [
        migrations.AddField(
            model_name='MyFilter',
            name='columns',
            field=models.JSONField(default=list, blank=True),
        ),
    ]
