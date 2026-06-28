from django.contrib import admin
from .models import CustomUser, EmailVerificationToken, PasswordResetToken

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)