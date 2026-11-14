# Django API

Django REST Framework is the control plane for accounts, conversations, API credentials and the OpenAI-compatible inference gateway. Run `python manage.py migrate`, `python manage.py createsuperuser`, then `python manage.py runserver`. Configure `INFERENCE_URL` to the private llama.cpp server. API credentials are stored as SHA-256 hashes; the raw key is returned only once when created.
