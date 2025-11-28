from django.db import models
import os, datetime, random, string
from django.conf import settings
from django.utils import timezone
from django.db import connection

def generate_unique_id(prefix):
    year = datetime.datetime.now().strftime("%Y")
    chars = string.ascii_lowercase + string.digits
    rand = ''.join(random.choice(chars) for _ in range(10))
    sec = datetime.datetime.now().strftime("%S")
    return f"{prefix}{year}{rand}{sec}".lower()


def upload_image(image):
    upload_path = os.path.join(settings.MEDIA_ROOT, "waste_collection_images")
    os.makedirs(upload_path, exist_ok=True)

    filename = f"{datetime.datetime.now().timestamp()}_{image.name}"
    fullpath = os.path.join(upload_path, filename)

    with open(fullpath, "wb") as f:
        for chunk in image.chunks(): 
            f.write(chunk)

    return f"uploads/waste_collection_images/{filename}"

class WasteType(models.Model):
    waste_type_name = models.CharField(max_length=255)
    is_delete = models.BooleanField(default=False)

    class Meta:
        db_table = "waste_type_creation_master"

class WasteCollectionSub(models.Model):
    unique_id = models.CharField(max_length=100, unique=True)
    screen_unique_id = models.CharField(max_length=100)
    customer_id = models.CharField(max_length=100)
    waste_type_id = models.CharField(max_length=100)
    image = models.CharField(max_length=255, null=True, blank=True)
    weight = models.FloatField(default=0)
    latitude = models.CharField(max_length=100, null=True, blank=True)
    longitude = models.CharField(max_length=100, null=True, blank=True)
    form_unique_id = models.CharField(max_length=100, null=True, blank=True)
    is_delete = models.BooleanField(default=False)
    date_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "waste_collection_sub"


class WasteCollectionMain(models.Model):
    unique_id = models.CharField(max_length=100, unique=True)
    screen_unique_id = models.CharField(max_length=100)
    collected_time = models.DateTimeField()
    created = models.DateTimeField()
    total_waste_collected = models.FloatField(default=0)
    entry_type = models.CharField(max_length=20, default='app')
    customer_id = models.CharField(max_length=100)
    is_delete = models.BooleanField(default=False)

    class Meta:
        db_table = "waste_collection_main"
