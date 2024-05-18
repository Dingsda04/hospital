from django.db import models

# Create your models here.

class Department(models.Model):
    name = models.CharField(max_length=100)
    tel_number = models.CharField(max_length=20)
    leitung = models.CharField(max_length=100, default=None)
    mail = models.EmailField()
    url = models.URLField()

    def __str__(self):
        return self.name

class Hospital(models.Model):
    hospital_id = models.CharField(max_length=100, unique=True, default=None)
    name = models.CharField(max_length=100)
    street = models.CharField(max_length=100)
    number = models.DecimalField(default=0, decimal_places=0, max_digits=256)
    state = models.CharField(max_length=100)
    zipcode = models.DecimalField(default=0, decimal_places=0, max_digits=5)
    city = models.CharField(max_length=100)
    departments = models.ManyToManyField(Department, blank=True)
    url = models.URLField()

    def __str__(self):
        return f'{self.name}: {self.state}'
    
class Error(models.Model):
    hospital_id = models.CharField(max_length=100, null=True, default=None)
    name = models.CharField(max_length=100, null=True)
    street = models.CharField(max_length=100, null=True)
    number = models.DecimalField(default=0, decimal_places=0, max_digits=256, null=True)
    state = models.CharField(max_length=100, null=True)
    zipcode = models.DecimalField(default=0, decimal_places=0, max_digits=5, null=True)
    city = models.CharField(max_length=100, null=True)
    departments = models.ManyToManyField(Department, blank=True)
    url = models.URLField(null=True)
    error = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name 