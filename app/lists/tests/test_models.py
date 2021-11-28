import pytest

from accounts.models import CustomUser
from lists.models import Item, List
from movies.tests.factories import MovieFactory


@pytest.mark.django_db
def test_list_model():
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    _list = List(owner=user, name="test list")
    _list.save()

    assert _list.owner == user
    assert _list.name == "test list"
    assert _list.added
    assert _list.updated
    assert str(_list) == _list.name


@pytest.mark.django_db
def test_item_model():
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    _list = List(owner=user, name="test list")
    _list.save()
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    item = Item.objects.create(
        movie=movie,
        _list=_list,
    )

    assert item._list == _list
    assert item.movie == movie
    assert item.watched is False
    assert item.added
    assert item.updated
    assert str(item) == f"{item.movie} on {item._list}"
