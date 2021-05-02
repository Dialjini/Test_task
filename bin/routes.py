from views import get_limits, add_limit, update_limit, delete_limit, get_history, add_transfer, delete_history, \
    update_transfer, add_client, update_client, delete_client, get_client


def setup_routes(app):
    app.router.add_route('GET', '/limits', get_limits)
    app.router.add_route('POST', '/limits', add_limit)
    app.router.add_route('DELETE', '/limits', delete_limit)
    app.router.add_route('PUT', '/limits', update_limit)

    app.router.add_route('DELETE', '/history', delete_history)
    app.router.add_route('GET', '/history', get_history)
    
    app.router.add_route('POST', '/transfer', add_transfer)
    app.router.add_route('PUT', '/transfer', update_transfer)

    app.router.add_route('GET', '/client', get_client)
    app.router.add_route('POST', '/client', add_client)
    app.router.add_route('PUT', '/client', update_client)
    app.router.add_route('DELETE', '/client', delete_client)
