from views import get_limits, add_limit, update_limit, delete_limit, index, get_history, add_transfer


def setup_routes(app):
    app.router.add_route('GET', '/', index)
    app.router.add_route('GET', '/limits', get_limits)
    app.router.add_route('POST', '/limits', add_limit)
    app.router.add_route('DELETE', '/limits', delete_limit)
    app.router.add_route('PUT', '/limits', update_limit)
    app.router.add_route('GET', '/history', get_history)
    app.router.add_route('POST', '/transfer', add_transfer)
