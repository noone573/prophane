from django.apps import AppConfig


class YourAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'  # Replace with your actual app name
    
    def ready(self):
        # Import models to register signals
        import store  # Replace with your actual app name
