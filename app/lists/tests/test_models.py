import pytest

from accounts.models import CustomUser
from lists.models import List


@pytest.mark.django_db
def test_list_model():
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    _list = List(owner=user, name="test list")
    _list.save()

    print("LIST >", _list.__dict__)
    assert _list.owner == user
    assert _list.name == "test list"
    assert _list.added
    assert _list.updated
    assert str(_list) == "test list"
