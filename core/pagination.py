def resolve_page_number(page_number_or_callable):
    if callable(page_number_or_callable):
        try:
            return page_number_or_callable()
        except Exception:
            return None
    return page_number_or_callable


def build_pagination_url(request, page_number):
    page_number = resolve_page_number(page_number)

    if page_number is None:
        return ""

    if request is None:
        return f"?page={page_number}"

    params = request.GET.copy()
    params['page'] = page_number
    return f"?{params.urlencode()}"


def build_pagination_items(page_obj, paginator, request=None):
    current_page = page_obj.number
    total_pages = paginator.num_pages

    def build_url(page_number):
        return build_pagination_url(request, page_number)

    def add_page(page_number):
        return {
            'label': str(page_number),
            'url': build_url(page_number),
            'is_current': page_number == current_page,
            'is_ellipsis': False,
        }

    def add_ellipsis():
        return {'label': '...', 'url': '', 'is_current': False, 'is_ellipsis': True}

    if total_pages <= 1:
        return [add_page(1)]

    if total_pages <= 4:
        return [add_page(page_number) for page_number in range(1, total_pages + 1)]

    items = [add_page(1)]

    if current_page <= 2:
        items.extend([add_page(2), add_page(3), add_ellipsis(), add_page(total_pages)])
    elif current_page >= total_pages - 1:
        items.extend([add_ellipsis(), add_page(total_pages - 2), add_page(total_pages - 1), add_page(total_pages)])
    else:
        items.extend([add_ellipsis(), add_page(current_page), add_ellipsis(), add_page(total_pages)])

    return items
