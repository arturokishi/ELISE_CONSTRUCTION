from django.http import HttpResponse

def home(request):
    return HttpResponse('ELISE Construction - Home Page')
