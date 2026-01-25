from django.contrib import admin
from .models import Invoice, InvoiceItem, InvoiceSequence


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "formatted_invoice_number",
        "client",
        "issue_date",
        "is_finalized",
    )
    inlines = [InvoiceItemInline]
    readonly_fields = ("invoice_number",)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_finalized:
            return [field.name for field in obj._meta.fields]
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_finalized:
            return False
        return True


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ("invoice", "product", "quantity", "price")


@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(admin.ModelAdmin):
    readonly_fields = ("last_number",)
