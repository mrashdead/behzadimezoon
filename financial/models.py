from django.db import models
from django.conf import settings


class Transaction(models.Model):
	class Type(models.TextChoices):
		PAYMENT = 'PAYMENT', 'پرداخت'
		REFUND = 'REFUND', 'مرجوع'
		DISCOUNT = 'DISCOUNT', 'تخفیف'
		DAMAGE = 'DAMAGE', 'خسارت'
		ADJUSTMENT = 'ADJUSTMENT', 'تعدیل دستی'

	reservation = models.ForeignKey(
		'reservations.Reservation',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='transactions'
	)
	amount = models.BigIntegerField()
	type = models.CharField(max_length=20, choices=Type.choices)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name='transactions'
	)
	created_at = models.DateTimeField(auto_now_add=True)
	note = models.TextField(blank=True)
	reference = models.CharField(max_length=200, blank=True, null=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['type']),
			models.Index(fields=['created_at']),
			models.Index(fields=['reservation']),
		]

	def __str__(self):
		return f"{self.get_type_display()} {self.amount} ({self.created_at})"
