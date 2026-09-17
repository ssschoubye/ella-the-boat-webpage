from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def placeholder(request, title, description):
    return render(request, "core/placeholder.html", {"title": title, "description": description})


def logbog(request):
    return placeholder(request, "Logbog", "Her kommer logbogen med ture, vejr og oplevelser på vandet.")


def skader(request):
    return placeholder(request, "Skader", "Her kommer en oversigt over skader og reparationer på Ella.")
