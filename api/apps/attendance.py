from django.db import models

class Employee(models.Model):
    emp_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    image_path = models.CharField(max_length=255)
    qr_code_path = models.CharField(max_length=255, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["emp_id"]),
        ]

class Recognized(models.Model):
    emp_id = models.CharField(max_length=50)
    emp_id_raw = models.CharField(max_length=50, null=True)
    name = models.CharField(max_length=100)
    records = models.DateTimeField()
    captured_image_path = models.CharField(max_length=255)
    similarity_score = models.FloatField()
    latitude = models.CharField(max_length=50)
    longitude = models.CharField(max_length=50)
    recognition_date = models.DateField()
    recognition_time = models.TimeField()

    class Meta:
        indexes = [
            models.Index(fields=["emp_id"])
        ]
