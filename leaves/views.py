from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden
from .forms import LeaveRequestForm
from .models import LeaveRequest


def is_seller(user):
    return user.is_authenticated and user.role == 'SELLER'


def is_manager(user):
    return user.is_authenticated and (user.role == 'MANAGER' or user.is_superuser or user.is_staff)


@login_required
def leave_create(request):
    if not is_seller(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect('leaves:seller-leaves')
    else:
        form = LeaveRequestForm()

    return render(request, 'leaves/submit.html', {'form': form})


@login_required
def seller_leaves(request):
    if not is_seller(request.user):
        return HttpResponseForbidden()

    leaves = LeaveRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'leaves/seller_list.html', {'leaves': leaves})


@login_required
@user_passes_test(is_manager)
def management_list(request):
    leaves = LeaveRequest.objects.select_related('user').order_by('-created_at')
    return render(request, 'leaves/admin_list.html', {'leaves': leaves})


@login_required
@user_passes_test(is_manager)
def approve_leave(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == 'POST':
        leave.status = LeaveRequest.Status.APPROVED
        leave.save()
    return redirect('leaves:management-list')


@login_required
@user_passes_test(is_manager)
def reject_leave(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == 'POST':
        leave.status = LeaveRequest.Status.REJECTED
        leave.save()
    return redirect('leaves:management-list')
