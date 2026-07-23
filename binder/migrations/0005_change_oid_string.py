from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('binder', '0004_history_changeset_change_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='change',
            name='oid_string',
            field=models.TextField(db_index=True, blank=True),
        ),
    ]
