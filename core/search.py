from functools import reduce
from operator import and_, or_

from django.db.models import Q


def build_token_search_query(search_text, fields):
    """Match every search token in at least one of the supplied fields."""
    token_queries = [
        reduce(
            or_,
            (Q(**{f'{field}__icontains': token}) for field in fields),
            Q(),
        )
        for token in search_text.split()
    ]
    return reduce(and_, token_queries, Q())
