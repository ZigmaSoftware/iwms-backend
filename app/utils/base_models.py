from django.db import models
from django.conf import settings
from app.utils.cascade_soft_delete import cascade_soft_delete

class Account(models.Model):

    # Use string primary key
    account_id = models.CharField(
        max_length=50,
        primary_key=True,
        editable=False
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    staff = models.OneToOneField(
        "app.StaffcreationOfficeDetails",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        # Auto assign account_id from related model
        if self.user:
            self.account_id = self.user.unique_id
        elif self.staff:
            self.account_id = self.staff.staff_unique_id

        super().save(*args, **kwargs)


class BaseMaster(models.Model):
    """Shared active/deleted flags for most tables."""

    # Declared per-model: a tuple of reverse-relation accessor names whose
    # objects should be soft-deleted along with this one. See
    # app/utils/cascade_soft_delete.py.
    CASCADE_SOFT_DELETE = ()

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)



    created_by_id = models.CharField(max_length=50, null=True, blank=True)
    updated_by_id = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def created_by(self):
        if self.created_by_id:
            return Account.objects.filter(account_id=self.created_by_id).first()
        return None

    @property
    def updated_by(self):
        if self.updated_by_id:
            return Account.objects.filter(account_id=self.updated_by_id).first()
        return None

    def delete(self, *args, updated_by=None, **kwargs):
        cascade_soft_delete(self, updated_by=updated_by)