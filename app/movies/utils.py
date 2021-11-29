from django.db.models import Avg
from django.core.exceptions import ObjectDoesNotExist

from lists.models import Item, List


def annotate_object_if_auth(request, movie):
    movie.avg_rating = movie.reviews.aggregate(avg_score=Avg("score"))["avg_score"]
    movie.on_list = False

    if request.user.is_authenticated:
        try:
            _list = List.objects.get(owner=request.user)
            items = Item.objects.filter(_list=_list)
            if items.filter(movie=movie).exists():
                movie.on_list = True
        except ObjectDoesNotExist:
            pass

    return movie
