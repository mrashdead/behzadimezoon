# reservations/urls.py

from django.urls import path

from .views import (
    reservation_list,
    reservation_step_one,
    reservation_create,
    reservation_detail,
    reservation_mark_delivered,
    reservation_mark_returned,
    reservation_mark_laundry,
    reservation_mark_ready,
    reservation_edit,
    reservation_delete,
    check_availability,
)

app_name = "reservations"

urlpatterns = [

    # list page
    path(
        "",
        reservation_list,
        name="list"
    ),

    # step one validation
    path(
        "step-one/",
        reservation_step_one,
        name="step_one"
    ),

    # create reservation
    path(
        "create/",
        reservation_create,
        name="create"
    ),

    # ajax check availability
    path(
        "check-availability/",
        check_availability,
        name="check_availability"
    ),

    # detail modal
    path(
        "<int:pk>/detail/",
        reservation_detail,
        name="detail"
    ),

    # edit reservation
    path(
        "<int:pk>/edit/",
        reservation_edit,
        name="edit"
    ),

    # mark delivered
    path(
        "<int:pk>/delivered/",
        reservation_mark_delivered,
        name="delivered"
    ),

    # mark returned
    path(
        "<int:pk>/returned/",
        reservation_mark_returned,
        name="returned"
    ),

    # send to laundry
    path(
        "<int:pk>/laundry/",
        reservation_mark_laundry,
        name="laundry"
    ),

    # approve laundry completion
    path(
        "<int:pk>/ready/",
        reservation_mark_ready,
        name="ready"
    ),

    # cancel reservation
    path(
        "<int:pk>/delete/",
        reservation_delete,
        name="delete"
    ),
]
