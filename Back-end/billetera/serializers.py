from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile

class UserSerializer(serializers.ModelSerializer): # Today create a new serializer for my new project
    
    class Meta: # and her create model and field for the project 
        model = User
        fields = ['username','email','id']
        
    extra_kwargs = {
        'password': {
            'write_only': True
        }
    }
    


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        
        fields = ['dni', 'telefono']
        
        
    def validate_dni(self,value): # and ther i approbade the sintaxys for the erorrs
        dni_limpio = (value or '').strip()
        
        if not dni_limpio.isdigit() or len(dni_limpio) < 7 :
            raise serializers.ValidationError("Tu dni da error ")
        
        return dni_limpio