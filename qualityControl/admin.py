from django.contrib import admin
from . import models

""" @admin.register(models.TrimAudit)
class TrimAuditAdmin(admin.ModelAdmin):
    '''Admin View for TrimAudit'''

    list_display = ('id','CheckList','Approval','Comments')
    list_filter = ('CheckList',)
    ordering = ('id',) """
