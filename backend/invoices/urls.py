from django.urls import path
from .views import invoice_pdf

urlpatterns = [
    path("<int:invoice_id>/pdf/", invoice_pdf, name="invoice_pdf"),
]
