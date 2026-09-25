from gwmultilaunch.models import Account


def test_display_name_priority():
    assert Account(id="1", title="Box", email="a@b.c", password="x", character="Hero").display_name() == "Box"
    assert Account(id="1", title="  ", email="a@b.c", password="x", character="Hero").display_name() == "Hero"
    assert Account(id="1", title="", email="a@b.c", password="x", character="").display_name() == "a@b.c"
    assert Account(id="1", email="", password="x").display_name() == "(unnamed)"


def test_repr_hides_password():
    account = Account(id="1", email="a@b.c", password="super-secret", character="Hero")
    text = repr(account)
    assert "super-secret" not in text
    assert "********" in text
    assert account.password == "super-secret"


def test_from_dict_defaults_and_bool():
    account = Account.from_dict({"email": "a@b.c", "password": "x", "auto_relaunch": "false"})
    assert account.auto_relaunch is False
    assert account.id
    again = Account.from_dict(account.to_dict())
    assert again == account
