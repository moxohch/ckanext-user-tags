import ckan.authz as authz
import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit


def _parse_tags(raw):
    return [t.strip() for t in raw.split(",") if t.strip()]


@toolkit.chained_action
def user_update(original_action, context, data_dict):
    raw_tags = data_dict.pop("tags", None)
    result = original_action(context, data_dict)
    # Only a sysadmin may set tags. The form field is hidden from everyone
    # else, but that alone doesn't stop a direct API call from a regular
    # user editing their own profile (which CKAN always allows) - this
    # check is the real enforcement, silently ignoring the field otherwise,
    # matching CKAN's own convention for sysadmin-only fields (plugin_extras'
    # own ignore_not_sysadmin validator).
    if raw_tags is not None and authz.is_sysadmin(context.get("user")):
        tags = _parse_tags(raw_tags)
        _save_tags(result["id"], tags)
        result["tags"] = tags
    return result


@toolkit.chained_action
def user_create(original_action, context, data_dict):
    raw_tags = data_dict.pop("tags", None)
    result = original_action(context, data_dict)
    if raw_tags is not None and authz.is_sysadmin(context.get("user")):
        tags = _parse_tags(raw_tags)
        _save_tags(result["id"], tags)
        result["tags"] = tags
    return result


@toolkit.chained_action
@toolkit.side_effect_free
def user_show(original_action, context, data_dict):
    result = original_action(context, data_dict)
    result["tags"] = _get_tags(result["id"])
    return result


def _save_tags(user_id, tags):
    user = model.User.get(user_id)
    extras = dict(user.plugin_extras or {})
    extras["tags"] = tags
    user.plugin_extras = extras
    user.save()


def _get_tags(user_id):
    user = model.User.get(user_id)
    return (user.plugin_extras or {}).get("tags", []) if user else []


class UserTagsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IActions)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "user_tags")

    # IActions

    def get_actions(self):
        return {
            "user_update": user_update,
            "user_create": user_create,
            "user_show": user_show,
        }
