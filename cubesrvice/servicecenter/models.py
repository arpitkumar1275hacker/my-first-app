from django.db import models
import random

class ServiceCompletion(models.Model):
    order = models.OneToOneField("users.MyOrder", on_delete=models.CASCADE)
    service_center_id = models.IntegerField()
    
    old_image = models.ImageField(upload_to="service_old/")
    new_image = models.ImageField(upload_to="service_new/")
    
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_verified = models.BooleanField(default=False)
    
    completed_at = models.DateTimeField(auto_now_add=True)

    def generate_otp(self):
        self.otp = str(random.randint(100000, 999999))
        self.save()