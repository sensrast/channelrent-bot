def conv_set(context, key, value):
    context.user_data[key] = value

def conv_get(context, key, default=None):
    return context.user_data.get(key, default)

def conv_clear(context, *keys):
    if not keys:
        context.user_data.clear()
        return
    for k in keys:
        context.user_data.pop(k, None)
