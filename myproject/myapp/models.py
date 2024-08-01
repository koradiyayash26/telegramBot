# myapp/models.py
from django.db import models
from django.contrib.auth.models import User


class Purchase(models.Model):
    # user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token_id = models.CharField(max_length=255, default="", null=False)
    vs_token = models.CharField(max_length=255, default="", null=False)
    buy_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, null=False)
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, null=False)
    swap_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, null=False)
    datetime = models.DateTimeField(auto_now_add=True)
    open = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.token_id} - {self.vs_token} - {self.id}'