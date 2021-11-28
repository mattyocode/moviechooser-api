# Generated by Django 3.2.7 on 2021-11-27 20:05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0002_auto_20211002_0919'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('lists', '0002_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='uid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='item',
            name='_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='list_item', to='lists.list'),
        ),
        migrations.AlterField(
            model_name='item',
            name='movie',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movie_item', to='movies.movie'),
        ),
        migrations.AlterField(
            model_name='list',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='list', to=settings.AUTH_USER_MODEL),
        ),
    ]
