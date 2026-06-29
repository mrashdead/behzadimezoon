# reservations/urls.py

from django.urls import path

from .views import (
    reservation_list,
    reservation_archive_list,
    reservation_step_one,
    reservation_create,
    reservation_detail,
    reservation_mark_delivered,
    reservation_mark_returned,
    reservation_mark_laundry,
    reservation_mark_ready,
    reservation_finalize_delivery,
    reservation_edit,
    reservation_archive,
    reservation_cancel,
    reservation_restore,
    reservation_delete_permanent,
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

    # finalize delivery (with payment verification)
    path(
        "<int:pk>/finalize-delivery/",
        reservation_finalize_delivery,
        name="finalize_delivery"
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
        "<int:pk>/archive/",
        reservation_archive,
        name="archive_action"
    ),
    path(
        "<int:pk>/cancel/",
        reservation_cancel,
        name="cancel_action"
    ),
    path(
        "<int:pk>/restore/",
        reservation_restore,
        name="restore"
    ),
    path(
        "<int:pk>/delete-permanent/",
        reservation_delete_permanent,
        name="delete_permanent"
    ),
    path(
        "archive/",
        reservation_archive_list,
        name="archive"
    ),
]
