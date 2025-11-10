from django.db import models
from .mainuserscreen import MainUserScreen
from .utils.comfun import generate_unique_id

def generate_userscreen_id():
    return f"USCRN{generate_unique_id()}"

class UserScreen(models.Model):
    unique_id = models.CharField(max_length=30, unique=True, default=generate_userscreen_id)
    mainscreen = models.ForeignKey(MainUserScreen, on_delete=models.PROTECT, related_name="userscreens", default=1)
    screen_name = models.CharField(max_length=150)
    folder_name = models.CharField(max_length=100, null=True, blank=True)
    order_no = models.PositiveIntegerField(default=1)
    icon = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)
    permissions = models.JSONField(default=dict)

    class Meta:
        ordering = ["order_no"]

    def __str__(self):
        return f"{self.screen_name} ({self.mainscreen.mainscreen})"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_delete = True
        self.save(update_fields=["is_active", "is_delete"])
