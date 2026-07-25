from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def pagination_url(context, request, page_number):
    params = request.GET.copy()
    params['page'] = page_number
    return f"?{params.urlencode()}"


@register.simple_tag(takes_context=True)
def compact_pagination(context, page_obj, paginator):
    request = context.get('request')
    current = page_obj.number
    total = paginator.num_pages

    def build_url(page_number):
        if request is None:
            return f"?page={page_number}"
        params = request.GET.copy()
        params['page'] = page_number
        return f"?{params.urlencode()}"

    if total <= 7:
        return [
            {'label': num, 'url': build_url(num), 'is_current': num == current, 'is_ellipsis': False}
            for num in range(1, total + 1)
        ]

    items = []

    def add_page(num):
        items.append({
            'label': num,
            'url': build_url(num),
            'is_current': num == current,
            'is_ellipsis': False,
        })

    def add_ellipsis():
        items.append({'label': '...', 'url': '', 'is_current': False, 'is_ellipsis': True})

    add_page(1)

    if current <= 4:
        add_page(2)
        add_page(3)
        add_page(4)
        add_page(5)
        add_ellipsis()
        add_page(total - 1)
        add_page(total)
    elif current >= total - 3:
        add_ellipsis()
        add_page(total - 4)
        add_page(total - 3)
        add_page(total - 2)
        add_page(total - 1)
        add_page(total)
    else:
        add_ellipsis()
        add_page(current - 1)
        add_page(current)
        add_page(current + 1)
        add_ellipsis()
        add_page(total - 1)
        add_page(total)

    return items
