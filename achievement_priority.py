def install():
    import bot

    observer = getattr(getattr(bot, 'dp', None), 'callback_query', None)
    if observer is None or not hasattr(observer, 'handlers'):
        return

    # achievements.install_sync() appends its handler. Put that handler first so
    # the existing catch-all callback cannot consume achievement buttons first.
    for index in range(len(observer.handlers) - 1, -1, -1):
        handler = observer.handlers[index]
        callback = getattr(handler, 'callback', None)
        if getattr(callback, '__name__', '') == 'achievement_callback':
            if index != 0:
                observer.handlers.insert(0, observer.handlers.pop(index))
            break
