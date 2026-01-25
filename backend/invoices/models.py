from django.db import models
from decimal import Decimal
from clients.models import Client
from products.models import Product


class InvoiceSequence(models.Model):
    """
    Tracks the last issued invoice number.
    Only ONE row should ever exist.
    """
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Last invoice number: {self.last_number}"


class Invoice(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    invoice_number = models.PositiveIntegerField(unique=True, editable=False)
    issue_date = models.DateField(auto_now_add=True)
    is_finalized = models.BooleanField(default=False)

    def __str__(self):
        return self.formatted_invoice_number()

    def formatted_invoice_number(self):
        return f"INV-{self.invoice_number:06d}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            seq, _ = InvoiceSequence.objects.get_or_create(id=1)

            max_existing = Invoice.objects.aggregate(
                models.Max("invoice_number")
            )["invoice_number__max"]

            if max_existing is None:
                next_number = 1
            elif max_existing == seq.last_number:
                next_number = seq.last_number + 1
            else:
                # latest invoice was deleted → reuse last number
                next_number = seq.last_number

            self.invoice_number = next_number
            seq.last_number = next_number
            seq.save()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        seq = InvoiceSequence.objects.first()
        if seq and self.invoice_number == seq.last_number:
            seq.last_number -= 1
            seq.save()
        super().delete(*args, **kwargs)

    def subtotal(self):
        return sum(
            (item.quantity * item.price for item in self.items.all()),
            Decimal("0.00")
        )

    def total_gst(self):
        return sum(
            (
                (item.quantity * item.price)
                * (item.product.gst_rate / Decimal("100"))
                for item in self.items.all()
            ),
            Decimal("0.00")
        )

    def total_amount(self):
        return self.subtotal() + self.total_gst()


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice, related_name="items", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.invoice.formatted_invoice_number()} - {self.product.name}"

    def line_total(self):
        return self.quantity * self.price
