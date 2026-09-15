from . import service


def cart_data(request):
    """Make cart state available in every template:
    badge count, sidebar lines/totals, wishlist dish ids."""
    try:
        lines, totals = service.get_lines(request)
    except Exception:          # never break a page because of the cart badge
        lines, totals = [], {'count': 0, 'total': 0, 'is_empty': True}
    return {
        'cart_count': totals['count'],
        'cart_lines': lines,
        'cart_totals': totals,
        'wishlist_ids': service.wishlist_ids_for(request),
    }
