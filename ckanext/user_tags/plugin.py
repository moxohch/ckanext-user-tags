import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit


@toolkit.chained_action
def user_update(original_action, context, data_dict):
    tag = data_dict.pop("tag", None)
    result = original_action(context, data_dict)
    if tag is not None:
        _save_tag(result["id"], tag)
        result["tag"] = tag
    return result


@toolkit.chained_action
def user_create(original_action, context, data_dict):
    tag = data_dict.pop("tag", None)
    result = original_action(context, data_dict)
    if tag is not None:
        _save_tag(result["id"], tag)
        result["tag"] = tag
    return result


@toolkit.chained_action
@toolkit.side_effect_free
def user_show(original_action, context, data_dict):
    result = original_action(context, data_dict)
    result["tag"] = _get_tag(result["id"])
    return result


def _save_tag(user_id, tag):
    user = model.User.get(user_id)
    extras = dict(user.plugin_extras or {})
    extras["tag"] = tag
    user.plugin_extras = extras
    user.save()


def _get_tag(user_id):
    user = model.User.get(user_id)
    return (user.plugin_extras or {}).get("tag", "") if user else ""


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
