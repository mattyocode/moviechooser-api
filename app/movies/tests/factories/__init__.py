import datetime

import factory
from factory import fuzzy
from faker import Factory as FakerFactory

from movies.models import Genre, Movie, Review

faker = FakerFactory.create()


class ReviewFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: "%03d" % n)
    source = fuzzy.FuzzyText(length=4, suffix="_review")
    score = fuzzy.FuzzyInteger(50, 100)

    class Meta:
        model = Review


class GenreFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: "%s" % n)
    name = factory.LazyAttribute(lambda x: faker.name())

    class Meta:
        model = Genre


class MovieFactory(factory.django.DjangoModelFactory):
    imdbid = factory.Sequence(lambda n: "imdb%s" % n)
    title = factory.Sequence(lambda n: "Tester %s" % n)
    released = fuzzy.FuzzyDate(datetime.date(1930, 1, 1))
    runtime = fuzzy.FuzzyInteger(50, 200)
    writer = fuzzy.FuzzyText(length=10, suffix="writer")
    poster_url = fuzzy.FuzzyText(length=10, prefix="www.", suffix="img.jpg")
    slug = factory.Sequence(lambda n: "slug%s" % n)

    class Meta:
        model = Movie

    @factory.post_generation
    def review(self, create, extracted, **kwargs):
        if not extracted:
            ReviewFactory(movie=self, score=fuzzy.FuzzyInteger(50, 100))
        if extracted:
            for review in extracted:
                if extracted != -1:
                    ReviewFactory(movie=self, score=review)


class MovieWithGenreFactory(MovieFactory):
    @factory.post_generation
    def genre(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for genre in extracted:
                if Genre.objects.filter(name=genre):
                    genre = Genre.objects.get(name=genre).id
                else:
                    genre = GenreFactory(name=genre)
                self.genre.add(genre)
