from django.shortcuts import render


def home(request):
    """Homepage with email verification form"""
    return render(request, "index.html")
