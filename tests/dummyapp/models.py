from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    in_stock = models.BooleanField(default=True)

    class Meta:
        app_label = "dummyapp"

    def __str__(self):
        return self.name
