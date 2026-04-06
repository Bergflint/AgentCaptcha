from rest_framework import serializers

class TestRequestSerializer(serializers.Serializer):
    url = serializers.URLField(
        required=True, 
        help_text="Enter the URL of the website to test."
    )
    email = serializers.EmailField(
        required=True, 
        help_text="Enter your email address for login."
    )
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        help_text="Enter your password for login."
    )
    isCertified = serializers.BooleanField(
        required=False, 
        help_text="Check this box if you are a certified agent."
    )

class CheckResultSerializer(serializers.Serializer):
    check_name = serializers.CharField()
    passed = serializers.BooleanField()

class TestResultSerializer(serializers.Serializer):
    url = serializers.URLField()
    email = serializers.EmailField()
    checks = CheckResultSerializer(many=True)
    status = serializers.ChoiceField(choices=["success", "error"])
    error_message = serializers.CharField(allow_blank=True, required=False)
