from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('my_filters', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='MyFilter',
            name='params',
            field=models.JSONField(),
        ),
    ]
