from django.db import models

from apparelManagement import models as AppModels

class FabricAudit(models.Model):
    """Model definition for Fabric Audit."""

    # TODO: Define fields here
    pass


class TrimAudit(models.Model):
    """Model definition for Trims Audit."""

    id = models.AutoField(primary_key=True)
    RecInventory = models.ForeignKey(AppModels.RecInventory, on_delete=models.CASCADE)
    CheckList = models.CharField(max_length=15)
    Approval = models.BooleanField(blank=True, null=True)
    Comments = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        """Meta definition for InventoryAudit."""

        indexes = [
            models.Index(fields=['RecInventory',]),
            models.Index(fields=['Approval',])
        ]