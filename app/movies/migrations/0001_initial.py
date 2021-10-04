# Generated by Django 3.2.7 on 2021-10-01 12:33

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Actor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Director',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Genre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=24, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Movie',
            fields=[
                ('imdbid', models.CharField(max_length=20, primary_key=True, serialize=False, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, max_length=32, null=True, unique=True)),
                ('rated', models.CharField(blank=True, max_length=20, null=True)),
                ('released', models.DateField()),
                ('runtime', models.IntegerField(null=True)),
                ('writer', models.CharField(max_length=500)),
                ('plot', models.CharField(max_length=500, null=True)),
                ('language', models.CharField(max_length=40, null=True)),
                ('country', models.CharField(max_length=40, null=True)),
                ('poster_url', models.CharField(max_length=200)),
                ('type_field', models.CharField(db_column='type_', max_length=12, null=True)),
                ('actors', models.ManyToManyField(blank=True, related_name='movie', to='movies.Actor')),
                ('director', models.ManyToManyField(blank=True, related_name='movie', to='movies.Director')),
                ('genre', models.ManyToManyField(blank=True, related_name='movie', to='movies.Genre')),
            ],
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(max_length=50)),
                ('score', models.IntegerField()),
                ('movie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='movies.movie')),
            ],
        ),
        migrations.CreateModel(
            name='OnDemand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service', models.CharField(max_length=50)),
                ('url', models.CharField(max_length=300)),
                ('added', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('movie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ondemand', to='movies.movie')),
            ],
        ),
    ]
