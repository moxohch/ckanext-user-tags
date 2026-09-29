import pytest

from ckan.logic import NotAuthorized
from ckan.tests import factories, helpers

from ckanext.user_tags.plugin import _parse_tags


# ---------------------------------------------------------------------------
# _parse_tags: pure function, no CKAN app context needed
# ---------------------------------------------------------------------------

def test_parse_tags_empty_string():
    assert _parse_tags("") == []


def test_parse_tags_single_tag():
    assert _parse_tags("interne") == ["interne"]


def test_parse_tags_multiple_tags():
    assert _parse_tags("interne,partenaire") == ["interne", "partenaire"]


def test_parse_tags_strips_whitespace():
    assert _parse_tags(" interne ,  partenaire  ") == ["interne", "partenaire"]


def test_parse_tags_ignores_empty_entries():
    # trailing/duplicate commas shouldn't produce empty-string tags
    assert _parse_tags("interne,,partenaire,") == ["interne", "partenaire"]


def test_parse_tags_whitespace_only_string():
    assert _parse_tags("   ") == []


# ---------------------------------------------------------------------------
# user_update / user_show: tags round-trip, as a sysadmin
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_user_with_no_tags_shows_empty_list():
    user = factories.User()
    shown = helpers.call_action("user_show", id=user["id"])
    assert shown["tags"] == []


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_sysadmin_sets_single_tag():
    sysadmin = factories.Sysadmin()
    user = factories.User()

    helpers.call_action(
        "user_update",
        context={"user": sysadmin["name"], "ignore_auth": False},
        id=user["id"], name=user["name"], email=user["email"],
        tags="interne",
    )

    shown = helpers.call_action("user_show", id=user["id"])
    assert shown["tags"] == ["interne"]


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_sysadmin_sets_multiple_tags():
    sysadmin = factories.Sysadmin()
    user = factories.User()

    helpers.call_action(
        "user_update",
        context={"user": sysadmin["name"], "ignore_auth": False},
        id=user["id"], name=user["name"], email=user["email"],
        tags="interne, partenaire, vip",
    )

    shown = helpers.call_action("user_show", id=user["id"])
    assert shown["tags"] == ["interne", "partenaire", "vip"]


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_sysadmin_clears_tags():
    sysadmin = factories.Sysadmin()
    user = factories.User()

    helpers.call_action(
        "user_update",
        context={"user": sysadmin["name"], "ignore_auth": False},
        id=user["id"], name=user["name"], email=user["email"],
        tags="interne",
    )
    helpers.call_action(
        "user_update",
        context={"user": sysadmin["name"], "ignore_auth": False},
        id=user["id"], name=user["name"], email=user["email"],
        tags="",
    )

    shown = helpers.call_action("user_show", id=user["id"])
    assert shown["tags"] == []


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_user_create_with_tags_as_sysadmin():
    sysadmin = factories.Sysadmin()

    result = helpers.call_action(
        "user_create",
        context={"user": sysadmin["name"], "ignore_auth": False},
        name="newuser", email="newuser@example.com", password="testpass123",
        tags="interne",
    )

    assert result["tags"] == ["interne"]
    shown = helpers.call_action("user_show", id=result["id"])
    assert shown["tags"] == ["interne"]


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_updating_unrelated_fields_does_not_touch_existing_tags():
    # regression: the user_patch/user_show recursion bug we hit meant an
    # unrelated profile update could silently wipe out a previously-set tag.
    sysadmin = factories.Sysadmin()
    user = factories.User()

    helpers.call_action(
        "user_update",
        context={"user": sysadmin["name"], "ignore_auth": False},
        id=user["id"], name=user["name"], email=user["email"],
        tags="interne",
    )
    # a normal profile update, submitted with no "tags" key at all
    helpers.call_action(
        "user_update",
        context={"user": user["name"], "ignore_auth": False},
        id=user["id"], name=user["name"], email=user["email"],
        fullname="New Full Name",
    )

    shown = helpers.call_action("user_show", id=user["id"])
    assert shown["tags"] == ["interne"]


# ---------------------------------------------------------------------------
# Authorization: only a sysadmin may set tags
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_regular_user_cannot_set_own_tags():
    # regression: a non-sysadmin editing their OWN profile (which CKAN always
    # allows) must not be able to sneak a "tags" value in - the html form
    # hides the field, but that alone doesn't stop a direct API call.
    user = factories.User()

    helpers.call_action(
        "user_update",
        context={"user": user["name"], "ignore_auth": False},
        id=user["id"], name=user["name"], email=user["email"],
        tags="hacked",
    )

    shown = helpers.call_action("user_show", id=user["id"])
    assert shown["tags"] == []


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_regular_user_cannot_set_tags_on_another_user():
    # this is enforced by CKAN's own user_update auth (only self or
    # sysadmin may edit a given profile at all), not by our plugin - kept
    # here as a safety net in case that assumption ever changes.
    editor = factories.User()
    target = factories.User()

    with pytest.raises(NotAuthorized):
        helpers.call_action(
            "user_update",
            context={"user": editor["name"], "ignore_auth": False},
            id=target["id"], name=target["name"], email=target["email"],
            tags="hacked",
        )

    shown = helpers.call_action("user_show", id=target["id"])
    assert shown["tags"] == []


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_editor_role_in_an_organization_is_irrelevant_to_tags():
    # tags are a global-user concept, unrelated to a user's role within any
    # particular organization - being an "editor" of an org grants no
    # special ability to set tags (only global sysadmin status matters).
    org_admin = factories.User()
    organization = factories.Organization(users=[
        {"name": org_admin["name"], "capacity": "admin"},
    ])

    helpers.call_action(
        "user_update",
        context={"user": org_admin["name"], "ignore_auth": False},
        id=org_admin["id"], name=org_admin["name"], email=org_admin["email"],
        tags="hacked",
    )

    shown = helpers.call_action("user_show", id=org_admin["id"])
    assert shown["tags"] == []


# ---------------------------------------------------------------------------
# side_effect_free regression: user_show must remain callable via GET
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_user_show_is_callable_via_get(app):
    # regression: our chained user_show must stay marked side_effect_free,
    # or CKAN starts rejecting GET requests to it with 400 "Please use POST"
    # - which is exactly what silently broke session checks on the portal.
    user = factories.User()
    response = app.get("/api/3/action/user_show", params={"id": user["id"]})
    assert response.status_code == 200
    assert response.json["success"] is True
