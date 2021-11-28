import json

import pytest
from accounts.models import CustomUser

from lists.models import Item, List
from movies.tests.factories import MovieFactory


DEFAULT_LIST = "watch-list"


@pytest.mark.django_db
def test_get_all_list_items(auth_user_client):
    user = CustomUser.objects.get(email="fixture@user.com")
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    _list = List.objects.create(
        owner=user,
        name=DEFAULT_LIST
    )
    Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = auth_user_client.get("/list/")
    assert resp.status_code == 200
    assert resp.data["results"][0]["_list"]["name"] == DEFAULT_LIST
    assert resp.data["results"][0]["watched"] is False
    assert "-tester" in resp.data["results"][0]["movie"]["slug"]


@pytest.mark.django_db
def test_get_all_list_items_no_list_exists(auth_user_client):
    """It returns an empty results array."""
    resp = auth_user_client.get("/list/")
    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_get_all_list_items_not_authorized(client):
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    _list = List.objects.create(
        owner=user,
        name=DEFAULT_LIST
    )
    Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = client.get("/list/")
    assert resp.status_code == 401
    assert resp.data["detail"] == "Authentication credentials were not provided."
    assert DEFAULT_LIST not in json.dumps(resp.data)
    assert "-tester" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_all_list_items_from_authorized_user_only(auth_user_client):
    other_user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    _list = List.objects.create(
        owner=other_user,
        name=DEFAULT_LIST
    )
    Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = auth_user_client.get("/list/")
    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_add_list_item(auth_user_client):
    items = Item.objects.all()
    assert len(items) == 0

    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    data = {
            "movie_slug": movie.slug,
        }
    data = json.dumps(data)
    resp = auth_user_client.post(
        "/list/",
        data,
        content_type="application/json"
    )
    assert resp.status_code == 201

    items = Item.objects.all()
    assert len(items) == 1


@pytest.mark.django_db
def test_add_list_item_unknown_slug(auth_user_client):
    items = Item.objects.all()
    assert len(items) == 0

    MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    data = {
        "movie_slug": "totallymadeupslug",
    }
    data = json.dumps(data)
    resp = auth_user_client.post(
        "/list/",
        data,
        content_type="application/json"
    )
    print("RESP >>", resp.__dict__)
    assert resp.status_code == 400
    assert resp.data["detail"] == "movie does not exist."

    items = Item.objects.all()
    assert len(items) == 0


@pytest.mark.django_db
def test_add_list_item_no_slug(auth_user_client):
    items = Item.objects.all()
    assert len(items) == 0

    MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    data = {}
    data = json.dumps(data)
    resp = auth_user_client.post(
        "/list/",
        data,
        content_type="application/json"
    )
    print("RESP >>", resp.__dict__)
    assert resp.status_code == 400
    assert "This field is required." in resp.data["movie_slug"]

    items = Item.objects.all()
    assert len(items) == 0


@pytest.mark.django_db
def test_add_list_item_user_not_authorized(client):
    items = Item.objects.all()
    assert len(items) == 0

    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    data = {
        "movie_slug": movie.slug,
    }
    data = json.dumps(data)
    resp = client.post(
        "/list/",
        data,
        content_type="application/json"
    )
    assert resp.status_code == 401
    assert resp.data["detail"] == "Authentication credentials were not provided."

    items = Item.objects.all()
    assert len(items) == 0


@pytest.mark.django_db
def test_get_single_list_item(auth_user_client):
    user = CustomUser.objects.get(email="fixture@user.com")
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    _list = List.objects.create(
        owner=user,
        name=DEFAULT_LIST
    )
    item = Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = auth_user_client.get(f"/list/{item.uid}/")
    assert resp.status_code == 200
    assert resp.data["_list"]["name"] == DEFAULT_LIST
    assert resp.data["watched"] is False
    assert resp.data["movie"]["title"] == "Tester"
    assert "-tester" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_list_item_unknown_uid(auth_user_client):
    fake_user_uid = "c2cf96e3-172e-4571-bb1a-71ed0f5ce037"
    resp = auth_user_client.get(f"/list/{fake_user_uid}/")
    assert resp.status_code == 404
    assert resp.data["detail"] == "Not found."


@pytest.mark.django_db
def test_get_single_list_item_not_authorized(client):
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    _list = List.objects.create(
        owner=user,
        name=DEFAULT_LIST
    )
    item = Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = client.get(f"/list/{item.uid}/")
    assert resp.status_code == 401
    assert resp.data["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_delete_single_list_item(auth_user_client):
    user = CustomUser.objects.get(email="fixture@user.com")
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    _list = List.objects.create(
        owner=user,
        name=DEFAULT_LIST
    )
    item = Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = auth_user_client.get(f"/list/{item.uid}/")
    assert resp.status_code == 200
    assert resp.data["movie"]["title"] == "Tester"

    resp_two = auth_user_client.delete(f"/list/{item.uid}/")
    assert resp_two.status_code == 204

    resp_three = auth_user_client.get("/list/")
    assert resp_three.status_code == 200
    assert resp_three.data["results"] == []

    assert "-tester" in json.dumps(resp.data)


@pytest.mark.django_db
def test_delete_single_list_item_unknown_uid(auth_user_client):
    fake_user_uid = "c2cf96e3-172e-4571-bb1a-71ed0f5ce037"
    resp = auth_user_client.delete(f"/list/{fake_user_uid}/")
    assert resp.status_code == 404
    assert resp.data["detail"] == "Not found."