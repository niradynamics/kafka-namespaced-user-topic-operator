from copy import deepcopy


def _copy_object(obj):
    new_obj = deepcopy(obj)
    for key in ["resourceVersion", "selfLink", "uid", "creationTimestamp", "generation"]:
        if key in new_obj["metadata"]:
            del new_obj["metadata"][key]

    return new_obj
