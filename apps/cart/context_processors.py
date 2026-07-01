def cart_count(request):
    if not request.user.is_authenticated:
        return {'cart_count': 0}
    try:
        return {'cart_count': request.user.cart.get_item_count()}
    except Exception:
        return {'cart_count': 0}
