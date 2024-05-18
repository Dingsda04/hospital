from django.contrib import admin

# Register your models here.
from .models import Department, Hospital, Error

admin.site.register(Department)
admin.site.register(Hospital)
admin.site.register(Error)